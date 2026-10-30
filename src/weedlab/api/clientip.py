"""Work out which address a request really came from."""

from __future__ import annotations

from collections.abc import Mapping

MAX_KEY_LENGTH = 64


def client_key(peer: str | None, headers: Mapping[str, str], trusted_hops: int) -> str:
    """Return the address to rate limit on.

    With trusted_hops = 0 the address of the connection itself is used. With N > 0
    the Nth entry from the right of X-Forwarded-For is used. Every trusted proxy
    appends the address it saw, so entries a visitor invents sit to the left of
    it and are ignored. If the header is missing or too short, the connection's
    own address is used instead.
    """
    fallback = peer or "unknown"
    if trusted_hops < 1:
        return fallback
    parts = [p.strip() for p in headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if len(parts) < trusted_hops:
        return fallback
    return parts[-trusted_hops][:MAX_KEY_LENGTH]
