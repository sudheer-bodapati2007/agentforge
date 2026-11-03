import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    """An authenticated person. Identity is owned by the auth provider (Supabase Auth)."""

    id: uuid.UUID
    email: str | None = None
    name: str | None = None
    avatar_url: str | None = None
