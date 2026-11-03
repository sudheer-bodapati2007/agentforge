"""Embedding column: pgvector's `vector` on PostgreSQL, JSON text on SQLite (tests).

No fixed dimension, so different embedders can coexist (each chunk records its embedder
and searches only compare vectors from the same one). The trade-off: no ANN index, so
search is exact, which is fine for per-project knowledge bases of a few thousand chunks.
"""

import json

from sqlalchemy.dialects.postgresql.base import ischema_names
from sqlalchemy.types import Text, TypeDecorator, UserDefinedType


class PgVector(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **_: object) -> str:
        return "vector"


# Let reflection (alembic check) recognise the column instead of warning about it.
ischema_names.setdefault("vector", PgVector)


class Vector(TypeDecorator):
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(PgVector() if dialect.name == "postgresql" else Text())

    def process_bind_param(self, value: list[float] | None, dialect) -> str | None:
        if value is None:
            return None
        # pgvector's text format is the same as a JSON array of numbers.
        return json.dumps([float(x) for x in value], separators=(",", ":"))

    def process_result_value(self, value: str | None, dialect) -> list[float] | None:
        return None if value is None else [float(x) for x in json.loads(value)]
