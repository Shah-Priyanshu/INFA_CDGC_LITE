from __future__ import annotations

import os
import json
import time
from typing import Any, Dict, Optional
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import httpx
import jwt
from jwt import PyJWKClient


bearer_scheme = HTTPBearer(auto_error=False)


class User:
    def __init__(self, sub: str, upn: Optional[str] = None, roles: Optional[list[str]] = None):
        self.sub = sub
        self.upn = upn
        self.roles = roles or []


async def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> User | None:
    # If auth is disabled or not configured, allow anonymous
    if os.getenv("AUTH_DISABLED") == "1" or not (os.getenv("OIDC_ISSUER") and os.getenv("OIDC_AUDIENCE")):
        return None

    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = creds.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")

    issuer = os.getenv("OIDC_ISSUER")
    audience = os.getenv("OIDC_AUDIENCE")

    # Prefer JWKS URL from issuer; fallback to a static PEM in env PUBLIC_JWT_KEY_PEM
    jwks_url = issuer.rstrip("/") + "/v2.0/.well-known/openid-configuration"
    try:
        # Fetch OpenID configuration and JWKS URI
        with httpx.Client(timeout=5.0) as client:
            oidc_conf = client.get(jwks_url).json()
            jwks_uri = oidc_conf.get("jwks_uri")
            if not jwks_uri:
                # Azure may expose keys at a known path; attempt direct JWKS if config resolution fails
                jwks_uri = issuer.rstrip("/") + "/discovery/v2.0/keys"
    except Exception:
        jwks_uri = issuer.rstrip("/") + "/discovery/v2.0/keys"

    try:
        jwk_client = PyJWKClient(jwks_uri)
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "RS384", "RS512"],
            audience=audience,
            issuer=issuer,
        )
    except Exception:
        # Fallback to PUBLIC_JWT_KEY_PEM for dev testing
        pub_pem = os.getenv("PUBLIC_JWT_KEY_PEM")
        if not pub_pem:
            raise HTTPException(status_code=401, detail="Token verification failed")
        try:
            decoded = jwt.decode(
                token,
                pub_pem,
                algorithms=["RS256", "RS384", "RS512"]
            )
            # Validate iss/aud if present
            if audience and decoded.get("aud") not in ([audience] if isinstance(decoded.get("aud"), str) else decoded.get("aud", [])):
                raise HTTPException(status_code=401, detail="Invalid audience")
            if issuer and decoded.get("iss") != issuer:
                raise HTTPException(status_code=401, detail="Invalid issuer")
        except Exception:
            raise HTTPException(status_code=401, detail="Token verification failed")

    # Roles may come under 'roles', 'groups', or scopes; normalize to roles list
    roles = []
    for key in ("roles", "groups", "scp", "scope"):
        val = decoded.get(key)
        if isinstance(val, list):
            roles.extend([str(v) for v in val])
        elif isinstance(val, str):
            roles.extend(val.split())

    return User(
        sub=decoded.get("sub") or decoded.get("oid") or "unknown",
        upn=decoded.get("upn") or decoded.get("preferred_username"),
        roles=roles,
    )


# Simple /me helper for smoke testing auth
from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def me(user: User | None = Depends(get_current_user)):
    if user is None:
        return {"authenticated": False}
    return {"authenticated": True, "sub": user.sub, "upn": user.upn, "roles": user.roles}


# RBAC helpers
from fastapi import Request


def _is_auth_disabled() -> bool:
    return os.getenv("AUTH_DISABLED") == "1" or not (os.getenv("OIDC_ISSUER") and os.getenv("OIDC_AUDIENCE"))


def require_writer(user: User | None = Depends(get_current_user)) -> User | None:
    """Require a 'writer' role. Configurable via WRITER_ROLES env, space/comma-separated.
    When auth is disabled, allow passthrough.
    """
    if _is_auth_disabled():
        return user
    allowed = os.getenv("WRITER_ROLES", "writer editors contributors").replace(",", " ").split()
    roles = set((user.roles if user else []))
    if roles.intersection(allowed):
        return user
    raise HTTPException(status_code=403, detail="Insufficient role: writer required")


def require_admin(user: User | None = Depends(get_current_user)) -> User | None:
    if _is_auth_disabled():
        return user
    allowed = os.getenv("ADMIN_ROLES", "admin owners").replace(",", " ").split()
    roles = set((user.roles if user else []))
    if roles.intersection(allowed):
        return user
    raise HTTPException(status_code=403, detail="Insufficient role: admin required")
