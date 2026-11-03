"""Authentication port. Infrastructure decides how tokens are verified (e.g. Supabase JWKS)."""

from typing import Protocol

from app.domain.errors import DomainError
from app.domain.user import User


class AuthenticationError(DomainError):
    """The caller's credentials are missing, malformed, expired or not trusted."""


class AuthUnavailableError(DomainError):
    """Credentials cannot be checked right now (misconfiguration or provider outage)."""


class TokenVerifier(Protocol):
    def verify(self, token: str) -> User:
        """Return the user a bearer token belongs to, or raise AuthenticationError."""
        ...


class UnconfiguredTokenVerifier:
    """Used when no auth provider is configured: every protected request fails closed."""

    def verify(self, token: str) -> User:
        raise AuthUnavailableError("Authentication is not configured: set SUPABASE_URL")
