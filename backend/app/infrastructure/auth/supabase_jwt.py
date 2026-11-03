"""Verifies Supabase Auth access tokens (JWTs) against the project's public signing keys.

Supabase signs tokens with an asymmetric key (ES256/RS256) and publishes the public half
at `<SUPABASE_URL>/auth/v1/.well-known/jwks.json`, so no Supabase secret is needed here.
Symmetric algorithms are rejected outright, which rules out alg-confusion attacks.
"""

import logging
import uuid
from typing import Protocol

import jwt

from app.application.auth import AuthenticationError, AuthUnavailableError
from app.domain.user import User

logger = logging.getLogger("agentforge.auth")

ALLOWED_ALGORITHMS = ["ES256", "RS256"]
AUTHENTICATED_ROLE = "authenticated"


class SigningKeySource(Protocol):
    """The subset of `jwt.PyJWKClient` this verifier uses (lets tests supply local keys)."""

    def get_signing_key_from_jwt(self, token: str) -> jwt.PyJWK: ...


class SupabaseJwtVerifier:
    def __init__(
        self,
        supabase_url: str,
        *,
        audience: str = "authenticated",
        leeway_seconds: int = 30,
        key_source: SigningKeySource | None = None,
    ) -> None:
        self._issuer = f"{supabase_url.rstrip('/')}/auth/v1"
        self._audience = audience
        self._leeway = leeway_seconds
        self._keys = key_source or jwt.PyJWKClient(
            f"{self._issuer}/.well-known/jwks.json",
            cache_keys=True,
            lifespan=600,  # re-fetch at most every 10 minutes (handles key rotation)
            timeout=5,
        )

    def verify(self, token: str) -> User:
        try:
            signing_key = self._keys.get_signing_key_from_jwt(token)
        except jwt.PyJWKClientConnectionError as exc:
            logger.warning("Could not fetch Supabase signing keys: %s", exc)
            raise AuthUnavailableError("Authentication provider is unreachable") from exc
        except (jwt.PyJWKClientError, jwt.DecodeError) as exc:
            raise AuthenticationError("Invalid access token") from exc

        try:
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=ALLOWED_ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("Access token has expired") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("Invalid access token") from exc

        if claims.get("role") != AUTHENTICATED_ROLE:
            raise AuthenticationError("Token is not for a signed-in user")
        try:
            user_id = uuid.UUID(claims["sub"])
        except (ValueError, TypeError) as exc:
            raise AuthenticationError("Invalid access token") from exc

        metadata = claims.get("user_metadata") or {}
        return User(
            id=user_id,
            email=claims.get("email"),
            name=metadata.get("full_name") or metadata.get("name"),
            avatar_url=metadata.get("avatar_url") or metadata.get("picture"),
        )
