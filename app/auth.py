"""Role-based access control as a FastAPI dependency.

Three moving parts, kept small on purpose:

* :class:`UserContext` — who is calling, as a frozen dataclass. It is a value, not
  a session: nothing here can be mutated by a request handler, and nothing here
  reaches back into the database.
* :func:`require` — the dependency factory. ``Depends(require("admin"))`` on a
  route means "an active user whose role carries ``can_admin``, or a 401/403".
* :func:`auth_enabled` — the opt-in switch. ``API_AUTH_ENABLED`` defaults to
  false, so an existing deployment (and the whole existing test suite) behaves
  exactly as before.

How the opt-in flag is applied
------------------------------
FastAPI resolves dependencies when the app is imported, so "only guard the route
when the flag is on" cannot be a decoration-time decision — the flag is read from
the environment per request. The dependency is therefore always attached and
short-circuits to an anonymous context when ``API_AUTH_ENABLED`` is false. The
observable behaviour is identical to an unguarded route (no key needed, no 401),
and flipping the environment variable takes effect on the next request instead of
requiring a re-import. That is the whole reason :func:`require` is a factory
rather than a decorator.

Status codes: 401 for a missing or unknown key (the caller may retry with a key),
403 for a known caller whose role is too weak (retrying will not help), and 503
when the user store itself is unreachable — a database outage must not be
reported as a bad credential.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Header, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.db import get_database

__all__ = ["UserContext", "ANONYMOUS", "require", "auth_enabled", "ROLE_LEVELS"]


@dataclass(frozen=True)
class UserContext:
    """The authenticated caller.

    Frozen: a request handler receives the facts about who is calling and cannot
    rewrite them. ``role`` is the role *name* (``"admin"``, ``"reviewer"`` or
    ``"viewer"``); the three booleans are the capabilities that role carries, read
    from the ``roles`` table rather than hard-coded here, so changing a role's
    permissions is a database change and not a code change.
    """

    user_id: int
    username: str
    role: str
    can_review: bool
    can_post: bool
    can_admin: bool


#: What an unauthenticated request looks like when ``API_AUTH_ENABLED`` is false.
#: It carries no capabilities: routes are open, but the context never claims a
#: privilege it was not granted, so a handler that ever consults it stays honest.
ANONYMOUS = UserContext(
    user_id=0,
    username="anonymous",
    role="anonymous",
    can_review=False,
    can_post=False,
    can_admin=False,
)

#: Accepted ``level`` names for :func:`require` -> the ``UserContext`` field that
#: must be true. ``"viewer"`` means "any authenticated user" and has no capability
#: to check, so it is handled separately below.
ROLE_LEVELS: dict[str, str] = {
    "reviewer": "can_review",
    "poster": "can_post",
    "admin": "can_admin",
}


def auth_enabled(settings: Settings | None = None) -> bool:
    """Whether API-key authentication is switched on.

    Args:
        settings: Loaded settings; ``None`` reads them from the environment.

    Returns:
        ``True`` only when ``API_AUTH_ENABLED`` is set. Off by default: the
        reviewer is a demo that must answer with zero configuration.
    """
    resolved = settings or Settings()
    return bool(resolved.api_auth_enabled)


def require(level: str) -> Callable[..., UserContext]:
    """Build a FastAPI dependency that enforces a minimum role.

    Args:
        level: ``"viewer"`` (any authenticated user), ``"reviewer"`` (may run
            reviews), ``"poster"`` (may publish to GitHub) or ``"admin"`` (may
            manage users). Case-insensitive.

    Returns:
        A dependency callable that reads the ``X-API-Key`` header, resolves it
        through :meth:`app.db.Database.authenticate`, and returns the caller's
        :class:`UserContext`. When ``API_AUTH_ENABLED`` is false it returns
        :data:`ANONYMOUS` without touching the database, which is how the opt-in
        flag leaves existing routes unaffected.

    Raises:
        ValueError: At decoration time, when ``level`` is not a known level — a
            typo in a route must fail loudly at import, not silently allow
            everyone through.
        HTTPException: 401 when the header is missing or the key is unknown or
            belongs to a deactivated user; 403 when the caller's role lacks the
            capability; 503 when the user store cannot be reached.
    """
    wanted = (level or "").strip().lower()
    if wanted != "viewer" and wanted not in ROLE_LEVELS:
        raise ValueError(
            f"unknown auth level {level!r}; expected 'viewer', 'reviewer', 'poster' or 'admin'"
        )
    capability = ROLE_LEVELS.get(wanted)

    def dependency(
        x_api_key: Annotated[
            str | None,
            Header(
                alias="X-API-Key",
                description="API key issued by POST /users; hashed before comparison.",
            ),
        ] = None,
    ) -> UserContext:
        settings = Settings()
        if not auth_enabled(settings):
            return ANONYMOUS
        if not x_api_key or not x_api_key.strip():
            raise HTTPException(
                status_code=401,
                detail="missing X-API-Key header",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        try:
            context: Any = get_database(settings).authenticate(x_api_key)
        except (SQLAlchemyError, RuntimeError, OSError) as exc:
            # A store that cannot be read is an outage, not a bad credential.
            raise HTTPException(
                status_code=503,
                detail=f"authentication store unavailable: {type(exc).__name__}",
            ) from exc
        if context is None:
            raise HTTPException(
                status_code=401,
                detail="unknown or inactive API key",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        if capability is not None and not getattr(context, capability):
            raise HTTPException(
                status_code=403,
                detail=f"role {context.role!r} lacks the {capability} permission",
            )
        return context

    return dependency
