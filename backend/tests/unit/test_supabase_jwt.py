"""Real cryptographic verification of Supabase-style tokens, with locally generated keys."""

import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.application.auth import AuthenticationError, AuthUnavailableError
from app.infrastructure.auth.supabase_jwt import SupabaseJwtVerifier

SUPABASE_URL = "https://example-ref.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"
USER_ID = uuid.uuid4()


class StaticKeySource:
    """Stands in for the JWKS endpoint with one known public key."""

    def __init__(self, private_key, kid="key-1"):
        self.kid = kid
        self.public_jwk = jwt.PyJWK.from_dict(
            {**jwt.algorithms.ECAlgorithm.to_jwk(private_key.public_key(), as_dict=True), "kid": kid, "alg": "ES256"}
        )

    def get_signing_key_from_jwt(self, token):
        if jwt.get_unverified_header(token).get("kid") != self.kid:
            raise jwt.PyJWKClientError("Unable to find a signing key that matches")
        return self.public_jwk


class UnreachableKeySource:
    def get_signing_key_from_jwt(self, token):
        raise jwt.PyJWKClientConnectionError("network down")


@pytest.fixture(scope="module")
def private_key():
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def verifier(private_key):
    return SupabaseJwtVerifier(SUPABASE_URL, key_source=StaticKeySource(private_key))


def make_token(private_key, *, kid="key-1", algorithm="ES256", **overrides):
    now = int(time.time())
    claims = {
        "sub": str(USER_ID),
        "aud": "authenticated",
        "iss": ISSUER,
        "iat": now,
        "exp": now + 3600,
        "role": "authenticated",
        "email": "ada@example.com",
        "user_metadata": {"full_name": "Ada Lovelace", "avatar_url": "https://example.com/a.png"},
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, private_key, algorithm=algorithm, headers={"kid": kid})


def test_valid_token_yields_user(verifier, private_key):
    user = verifier.verify(make_token(private_key))
    assert user.id == USER_ID
    assert user.email == "ada@example.com"
    assert user.name == "Ada Lovelace"
    assert user.avatar_url == "https://example.com/a.png"


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": int(time.time()) - 3600},  # expired (beyond leeway)
        {"aud": "something-else"},  # wrong audience
        {"iss": "https://evil.example.com/auth/v1"},  # another Supabase project / issuer
        {"role": "anon"},  # anon key token, not a signed-in user
        {"sub": "not-a-uuid"},
        {"sub": None},  # missing required claim
    ],
)
def test_untrusted_claims_are_rejected(verifier, private_key, overrides):
    with pytest.raises(AuthenticationError):
        verifier.verify(make_token(private_key, **overrides))


def test_token_signed_by_another_key_is_rejected(verifier):
    attacker_key = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(AuthenticationError):
        verifier.verify(make_token(attacker_key))


def test_unknown_key_id_is_rejected(verifier, private_key):
    with pytest.raises(AuthenticationError):
        verifier.verify(make_token(private_key, kid="unknown"))


def test_symmetric_algorithm_is_rejected(verifier):
    # alg-confusion: an HS256 token must never be accepted, whatever the key.
    now = int(time.time())
    token = jwt.encode(
        {"sub": str(USER_ID), "aud": "authenticated", "iss": ISSUER, "iat": now, "exp": now + 60, "role": "authenticated"},
        "a" * 32,
        algorithm="HS256",
        headers={"kid": "key-1"},
    )
    with pytest.raises(AuthenticationError):
        verifier.verify(token)


def test_garbage_is_rejected(verifier):
    with pytest.raises(AuthenticationError):
        verifier.verify("not.a.jwt")


def test_unreachable_jwks_is_reported_as_unavailable(private_key):
    verifier = SupabaseJwtVerifier(SUPABASE_URL, key_source=UnreachableKeySource())
    with pytest.raises(AuthUnavailableError):
        verifier.verify(make_token(private_key))
