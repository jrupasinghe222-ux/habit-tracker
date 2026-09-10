"""Verify Supabase access tokens using its asymmetric public signing keys."""
from functools import lru_cache
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientConnectionError, PyJWKClientError

from backend.config import supabase_url

bearer = HTTPBearer(auto_error=False)


@lru_cache
def jwks_client() -> PyJWKClient:
    return PyJWKClient(
        f"{supabase_url()}/auth/v1/.well-known/jwks.json",
        cache_jwk_set=True, lifespan=300, timeout=5,
    )


def verify_access_token(token: str) -> UUID:
    if len(token) > 16384:
        raise HTTPException(401, "Invalid or expired session.")
    try:
        issuer = f"{supabase_url()}/auth/v1"
    except ValueError:
        raise HTTPException(503, "Authentication is not configured.") from None
    try:
        # Pin supported asymmetric algorithms before any remote key lookup.
        header = jwt.get_unverified_header(token)
        if header.get("alg") not in {"ES256", "RS256"} or not header.get("kid"):
            raise InvalidTokenError()
        key = jwks_client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token, key, algorithms=["ES256", "RS256"],
            audience="authenticated", issuer=issuer,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
        if claims.get("role") != "authenticated" or claims.get("is_anonymous", False):
            raise InvalidTokenError()
        return UUID(claims["sub"])
    except PyJWKClientConnectionError:
        raise HTTPException(503, "Sign-in verification is temporarily unavailable.") from None
    except (InvalidTokenError, PyJWKClientError, ValueError, TypeError, AttributeError):
        raise HTTPException(
            401, "Invalid or expired session.", headers={"WWW-Authenticate": "Bearer"}
        ) from None


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> UUID:
    if credentials is None:
        raise HTTPException(401, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
    return verify_access_token(credentials.credentials)
