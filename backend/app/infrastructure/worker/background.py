"""In-process worker pool that drains the run queue.

Each thread loops: claim (compare-and-set) -> execute -> repeat, sleeping on an Event
between polls so new runs start immediately when `notify()` is called. While a run
executes, a heartbeat thread proves liveness; a recovery loop re-queues runs whose
heartbeat went stale (their worker crashed), and they resume from their checkpoint.

The same class can run in a dedicated worker process (`python -m app.worker`) when the
API and workers should scale independently.
"""

import logging
import os
import socket
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from app.application.runs.models import ClaimedRun
from app.application.runs.ports import WorkflowEngine
from app.application.runs.processor import RunProcessor
from app.infrastructure.persistence.run_repository import SqlAlchemyRunRepository

logger = logging.getLogger("agentforge.worker")

HEARTBEAT_SECONDS = 15


class BackgroundWorker:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        engine_factory: Callable[[], WorkflowEngine],
        concurrency: int = 2,
        poll_seconds: float = 1.0,
        heartbeat_timeout_seconds: int = 120,
    ) -> None:
        self._session_factory = session_factory
        self._engine_factory = engine_factory
        self._concurrency = concurrency
        self._poll = poll_seconds
        self._stale_after = timedelta(seconds=heartbeat_timeout_seconds)
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._prefix = f"{socket.gethostname()[:20]}-{os.getpid()}"

    # ------------------------------------------------------------------ lifecycle

    def start(self) -> None:
        for index in range(self._concurrency):
            thread = threading.Thread(target=self._loop, args=(f"{self._prefix}-{index}",), daemon=True, name=f"run-worker-{index}")
            thread.start()
            self._threads.append(thread)
        recovery = threading.Thread(target=self._recovery_loop, daemon=True, name="run-recovery")
        recovery.start()
        self._threads.append(recovery)
        logger.info("started %d run worker(s)", self._concurrency)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        for thread in self._threads:
            thread.join(timeout)

    def notify(self) -> None:
        self._wake.set()

    # ------------------------------------------------------------------ loops

    def run_once(self, worker_id: str = "inline") -> bool:
        """Claim and fully process one run synchronously (used by tests and the CLI)."""
        claim = self._claim(worker_id)
        if claim is None:
            return False
        self._process(claim, worker_id)
        return True

    def _loop(self, worker_id: str) -> None:
        while not self._stop.is_set():
            try:
                if self.run_once(worker_id):
                    continue
            except Exception:  # never let one bad run kill the worker thread
                logger.exception("worker %s crashed while processing a run", worker_id)
            self._wake.wait(self._poll)
            self._wake.clear()

    def _recovery_loop(self) -> None:
        while not self._stop.wait(30):
            try:
                with self._session_factory() as session:
                    count = SqlAlchemyRunRepository(session).requeue_stale(datetime.now(UTC) - self._stale_after)
                if count:
                    logger.warning("re-queued %d run(s) whose worker stopped heartbeating", count)
                    self._wake.set()
            except Exception:
                logger.exception("stale-run recovery failed")

    # ------------------------------------------------------------------ work

    def _claim(self, worker_id: str) -> ClaimedRun | None:
        with self._session_factory() as session:
            return SqlAlchemyRunRepository(session).claim_next(worker_id)

    def _process(self, claim: ClaimedRun, worker_id: str) -> None:
        done = threading.Event()

        def beat() -> None:
            while not done.wait(HEARTBEAT_SECONDS):
                try:
                    with self._session_factory() as session:
                        SqlAlchemyRunRepository(session).heartbeat(claim.run.id, worker_id)
                except Exception:
                    logger.exception("heartbeat failed for run %s", claim.run.id)

        heartbeat = threading.Thread(target=beat, daemon=True, name=f"heartbeat-{claim.run.id}")
        heartbeat.start()
        try:
            with self._session_factory() as session:
                status = RunProcessor(SqlAlchemyRunRepository(session), self._engine_factory()).process(claim)
            logger.info("run=%s -> %s", claim.run.id, status)
        finally:
            done.set()
            heartbeat.join(1)
