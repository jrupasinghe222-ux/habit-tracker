import asyncio
import time
from types import SimpleNamespace
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from backend import auth
from backend.config import supabase_url
from backend.main import app


@pytest.fixture
def identity(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://testproject.supabase.co")
    supabase_url.cache_clear()
    key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(auth, "jwks_client", lambda: SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())))
    claims = {
        "sub": str(uuid4()), "iss": "https://testproject.supabase.co/auth/v1",
        "aud": "authenticated", "role": "authenticated",
        "iat": int(time.time()) - 1, "exp": int(time.time()) + 300,
    }
    yield key, claims
    supabase_url.cache_clear()


def request(token=None, path="/api/me"):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            return await client.get(path, headers=headers)
    return asyncio.run(run())


def signed(key, claims):
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": "test-key"})


def test_valid_identity_is_verified(identity):
    key, claims = identity
    response = request(signed(key, claims))
    assert response.status_code == 200
    assert response.json() == {"id": claims["sub"]}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("path", ["/api/me", "/api/habits"])
def test_no_token_is_rejected(path):
    assert request(path=path).status_code == 401


@pytest.mark.parametrize("change", [
    {"exp": 1}, {"iss": "https://other.supabase.co/auth/v1"},
    {"aud": "wrong-app"}, {"role": "service_role"},
    {"sub": "not-a-uuid"}, {"is_anonymous": True},
    {"iat": int(time.time()) + 86400},
])
def test_invalid_claims_are_rejected(identity, change):
    key, claims = identity
    assert request(signed(key, claims | change)).status_code == 401


def test_missing_expiry_is_rejected(identity):
    key, claims = identity
    del claims["exp"]
    assert request(signed(key, claims)).status_code == 401


def test_forged_signature_is_rejected(identity):
    _, claims = identity
    wrong_key = ec.generate_private_key(ec.SECP256R1())
    assert request(signed(wrong_key, claims)).status_code == 401


def test_unsigned_token_is_rejected(identity):
    _, claims = identity
    token = jwt.encode(claims, "", algorithm="none", headers={"kid": "test-key"})
    assert request(token).status_code == 401


def test_malformed_token_is_rejected(identity):
    assert request("not-a-token").status_code == 401


def test_auth_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    supabase_url.cache_clear()
    assert request("placeholder").status_code == 503
    supabase_url.cache_clear()
