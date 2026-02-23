import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx
from jose import JWTError, jwt

from app.core.config import get_settings


@dataclass(frozen=True)
class ClerkIdentity:
    clerk_user_id: str
    email: str | None
    full_name: str | None


class ClerkTokenError(ValueError):
    pass


class ClerkConfigError(ClerkTokenError):
    pass


_JWKS_CACHE_LOCK = asyncio.Lock()
_JWKS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _normalize_optional_str(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _normalize_email(value: Any) -> str | None:
    email = _normalize_optional_str(value)
    return email.lower() if email else None


def _extract_email_claim(claims: dict[str, Any]) -> str | None:
    for field in ("email", "email_address"):
        candidate = _normalize_email(claims.get(field))
        if candidate:
            return candidate

    email_addresses = claims.get("email_addresses")
    if isinstance(email_addresses, list):
        for entry in email_addresses:
            if isinstance(entry, dict):
                candidate = _normalize_email(
                    entry.get("email_address") or entry.get("email")
                )
            else:
                candidate = _normalize_email(entry)
            if candidate:
                return candidate

    return None


def _extract_full_name(claims: dict[str, Any]) -> str | None:
    name = _normalize_optional_str(claims.get("name"))
    if name:
        return name

    first_name = _normalize_optional_str(claims.get("first_name"))
    last_name = _normalize_optional_str(claims.get("last_name"))
    full_name = " ".join(part for part in [first_name, last_name] if part).strip()
    return full_name or None


def _resolve_clerk_config() -> tuple[str, str, list[str], str | None, int]:
    settings = get_settings()
    if not settings.clerk_enabled:
        raise ClerkConfigError("Clerk auth is not enabled on this API.")

    issuer = _normalize_optional_str(settings.clerk_issuer)
    if not issuer:
        raise ClerkConfigError("CLERK_ISSUER is required when Clerk auth is enabled.")

    normalized_issuer = issuer.rstrip("/")
    jwks_url = _normalize_optional_str(settings.clerk_jwks_url)
    if not jwks_url:
        jwks_url = f"{normalized_issuer}/.well-known/jwks.json"

    audience = _normalize_optional_str(settings.clerk_jwt_audience)
    cache_ttl = max(int(settings.clerk_jwks_cache_ttl_seconds), 60)
    return (
        normalized_issuer,
        jwks_url,
        settings.clerk_authorized_party_list,
        audience,
        cache_ttl,
    )


async def _get_jwks(jwks_url: str, cache_ttl_seconds: int) -> dict[str, Any]:
    now = time.time()
    cached = _JWKS_CACHE.get(jwks_url)
    if cached and cached[0] > now:
        return cached[1]

    async with _JWKS_CACHE_LOCK:
        cached = _JWKS_CACHE.get(jwks_url)
        if cached and cached[0] > time.time():
            return cached[1]

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(jwks_url)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise ClerkTokenError("Unable to fetch Clerk signing keys.") from exc

        keys = payload.get("keys")
        if not isinstance(keys, list) or not keys:
            raise ClerkTokenError("Invalid Clerk JWKS response.")

        _JWKS_CACHE[jwks_url] = (time.time() + cache_ttl_seconds, payload)
        return payload


def _select_signing_key(token: str, jwks: dict[str, Any]) -> dict[str, Any]:
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise ClerkTokenError("Invalid Clerk session token.") from exc

    keys = jwks.get("keys")
    if not isinstance(keys, list) or not keys:
        raise ClerkTokenError("Invalid Clerk JWKS response.")

    token_kid = unverified_header.get("kid")
    if token_kid:
        for key in keys:
            if isinstance(key, dict) and key.get("kid") == token_kid:
                return key
        raise ClerkTokenError("Unable to find matching Clerk signing key.")

    if len(keys) == 1 and isinstance(keys[0], dict):
        return keys[0]

    raise ClerkTokenError("Clerk token is missing key id.")


def _validate_authorized_party(
    claims: dict[str, Any], authorized_parties: list[str]
) -> None:
    if not authorized_parties:
        return

    azp = _normalize_optional_str(claims.get("azp"))
    if azp not in authorized_parties:
        raise ClerkTokenError("Invalid Clerk token authorized party.")


async def verify_clerk_session_token(token: str) -> ClerkIdentity:
    normalized_token = _normalize_optional_str(token)
    if not normalized_token:
        raise ClerkTokenError("Missing Clerk session token.")

    issuer, jwks_url, authorized_parties, audience, cache_ttl_seconds = (
        _resolve_clerk_config()
    )
    jwks = await _get_jwks(jwks_url, cache_ttl_seconds)
    signing_key = _select_signing_key(normalized_token, jwks)

    options = {
        "verify_aud": bool(audience),
        "verify_iss": False,
    }
    try:
        claims = jwt.decode(
            normalized_token,
            signing_key,
            algorithms=["RS256"],
            audience=audience,
            options=options,
        )
    except JWTError as exc:
        raise ClerkTokenError("Invalid Clerk session token.") from exc

    token_issuer = _normalize_optional_str(claims.get("iss"))
    if not token_issuer or token_issuer.rstrip("/") != issuer:
        raise ClerkTokenError("Invalid Clerk token issuer.")

    _validate_authorized_party(claims, authorized_parties)

    clerk_user_id = _normalize_optional_str(claims.get("sub"))
    if not clerk_user_id:
        raise ClerkTokenError("Invalid Clerk token subject.")

    return ClerkIdentity(
        clerk_user_id=clerk_user_id,
        email=_extract_email_claim(claims),
        full_name=_extract_full_name(claims),
    )
