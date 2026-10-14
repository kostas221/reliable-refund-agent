"""Sign-in and sessions (plan section 7: an established mechanism, secure cookies, protected state changes).

Passwords are checked with argon2 (argon2-cffi). A session is a random token in an HttpOnly, SameSite=Strict cookie;
the database keeps only its SHA-256, with the user, a CSRF token and the expiry, so a session survives a restart and
a sign-out ends it for good. Session times come from the real clock, never from the business clock of a scenario.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import Engine, text

SESSION_COOKIE = "refund_session"
CSRF_HEADER = "X-CSRF-Token"
SESSION_LIFETIME = timedelta(hours=8)

_HASHER = PasswordHasher()
# Checked for an unknown email too, so a wrong email and a wrong password take the same time.
_NOBODY = _HASHER.hash(secrets.token_urlsafe(16))


@dataclass(frozen=True)
class SignedIn:
    user_id: str
    role: Literal["customer", "staff"]
    display_name: str
    csrf_token: str


def set_password(owner: Engine, user_id: str, password: str) -> None:
    """Seeding only, as refund_owner: the application role cannot change users."""
    with owner.begin() as conn:
        conn.execute(
            text("UPDATE users SET password_hash = :hash WHERE id = :id"),
            {"hash": _HASHER.hash(password), "id": user_id},
        )


def _session_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def sign_in(engine: Engine, email: str, password: str, now: datetime) -> tuple[str, SignedIn] | None:
    """A new session token and its user, or None. The answer does not say whether the email exists."""
    with engine.begin() as conn:
        user = (
            conn.execute(
                text("SELECT id, role, display_name, password_hash FROM users WHERE email = :email"), {"email": email}
            )
            .mappings()
            .first()
        )
        stored = user["password_hash"] if user and user["password_hash"] else _NOBODY
        try:
            _HASHER.verify(stored, password)
        except VerificationError:
            return None
        if stored is _NOBODY:
            return None
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        conn.execute(
            text(
                "INSERT INTO sessions (id, user_id, csrf_token, created_at, expires_at) "
                "VALUES (:id, :user, :csrf, :now, :expires)"
            ),
            {"id": _session_id(token), "user": user["id"], "csrf": csrf, "now": now, "expires": now + SESSION_LIFETIME},
        )
    return token, SignedIn(user["id"], user["role"], user["display_name"], csrf)


def session_user(engine: Engine, token: str, now: datetime) -> SignedIn | None:
    """The user of a live session: not signed out and not expired. The role is read from the user, every time."""
    with engine.connect() as conn:
        row = (
            conn.execute(
                text(
                    "SELECT u.id, u.role, u.display_name, s.csrf_token FROM sessions s "
                    "JOIN users u ON u.id = s.user_id WHERE s.id = :id AND s.revoked_at IS NULL AND s.expires_at > :now"
                ),
                {"id": _session_id(token), "now": now},
            )
            .mappings()
            .first()
        )
    return None if row is None else SignedIn(row["id"], row["role"], row["display_name"], row["csrf_token"])


def sign_out(engine: Engine, token: str, now: datetime) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE sessions SET revoked_at = :now WHERE id = :id AND revoked_at IS NULL"),
            {"id": _session_id(token), "now": now},
        )


def csrf_matches(signed_in: SignedIn, sent: str | None) -> bool:
    return sent is not None and secrets.compare_digest(sent, signed_in.csrf_token)
