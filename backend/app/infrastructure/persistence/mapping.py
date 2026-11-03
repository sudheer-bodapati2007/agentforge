"""Row -> read-model mapping.

Read models are frozen dataclasses whose field names match ORM attributes, so one
generic function replaces hand-written field-by-field copying. Fields the row does not
have (computed or joined values) are passed explicitly as overrides.
"""

from dataclasses import fields
from typing import TypeVar

V = TypeVar("V")


def to_view(view_cls: type[V], row: object, **overrides: object) -> V:
    values = {
        f.name: getattr(row, f.name)
        for f in fields(view_cls)  # type: ignore[arg-type]
        if f.name not in overrides and hasattr(row, f.name)
    }
    return view_cls(**values, **overrides)
