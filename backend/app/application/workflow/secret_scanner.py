"""Deterministic hardcoded-secret detection. Pure function: runs anywhere, no sandbox needed."""

import re

from app.domain.enums import FindingSeverity, FindingSource
from app.domain.review import Finding

_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("Stripe secret key", re.compile(r"\bsk_live_[0-9A-Za-z]{20,}\b")),
    ("Supabase secret key", re.compile(r"\bsb_secret_[0-9A-Za-z_-]{20,}\b")),
    (
        "Hardcoded credential",
        re.compile(
            r"""(?i)\b(password|passwd|secret|api_key|apikey|access_token|auth_token|secret_key)\b\s*[:=]\s*["']([^"'\s]{8,})["']"""
        ),
    ),
)

# Obvious placeholders are not secrets.
_PLACEHOLDER = re.compile(r"(?i)(change[-_]?me|example|placeholder|your[-_]|dummy|test|xxx+|\*{3,}|<[^>]+>)")


def scan_for_secrets(files: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(files):
        if path.startswith("tests/"):
            continue  # test fixtures commonly contain fake credentials
        for line_no, line in enumerate(files[path].splitlines(), start=1):
            for title, pattern in _RULES:
                match = pattern.search(line)
                if not match:
                    continue
                value = match.group(match.lastindex or 0)
                if title == "Hardcoded credential" and _PLACEHOLDER.search(value):
                    continue
                findings.append(
                    Finding(
                        severity=FindingSeverity.CRITICAL,
                        category="secrets",
                        title=f"{title} in source code",
                        description="A credential appears to be hardcoded. Anyone with the code can use it.",
                        source=FindingSource.TOOL,
                        file_path=path,
                        line=line_no,
                        suggestion="Load it from an environment variable or secret manager and rotate the exposed value.",
                        tool_name="secret-scanner",
                    )
                )
                break
    return findings
