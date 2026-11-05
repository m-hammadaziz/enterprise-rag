"""API-key authentication -> user + groups.

Keys are stored as SHA-256 hashes. In production you would put this behind your
SSO / OIDC gateway and map IdP groups to ``user_groups``; the rest of the system
only needs ``CurrentUser.groups``.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

from app.db import get_pool


@dataclass
class CurrentUser:
    id: int
    name: str
    groups: list[str]
    is_admin: bool


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_api_key() -> str:
    return "erk_" + secrets.token_urlsafe(24)


def get_user_by_key(api_key: str) -> CurrentUser | None:
    with get_pool().connection() as conn:
        row = conn.execute(
            """SELECT u.id, u.name, u.is_admin,
                      coalesce(array_agg(g.group_name) FILTER (WHERE g.group_name IS NOT NULL), '{}') AS groups
               FROM users u LEFT JOIN user_groups g ON g.user_id = u.id
               WHERE u.api_key_hash = %s GROUP BY u.id""",
            (hash_key(api_key),),
        ).fetchone()
    if not row:
        return None
    return CurrentUser(row["id"], row["name"], sorted(row["groups"]), row["is_admin"])


def get_user_groups(name: str) -> list[str]:
    with get_pool().connection() as conn:
        rows = conn.execute(
            "SELECT g.group_name FROM users u JOIN user_groups g ON g.user_id=u.id WHERE u.name=%s",
            (name,),
        ).fetchall()
    return sorted(r["group_name"] for r in rows)


def upsert_user(name: str, groups: list[str], is_admin: bool = False, api_key: str | None = None) -> str:
    """Create/update a user, replace their groups, (re)issue an API key. Returns the key."""
    api_key = api_key or new_api_key()
    groups = sorted({g.strip().lower() for g in groups if g.strip()})
    with get_pool().connection() as conn, conn.transaction():
        uid = conn.execute(
            """INSERT INTO users (name, api_key_hash, is_admin) VALUES (%s,%s,%s)
               ON CONFLICT (name) DO UPDATE SET api_key_hash=EXCLUDED.api_key_hash, is_admin=EXCLUDED.is_admin
               RETURNING id""",
            (name, hash_key(api_key), is_admin),
        ).fetchone()["id"]
        conn.execute("DELETE FROM user_groups WHERE user_id=%s", (uid,))
        for g in groups:
            conn.execute("INSERT INTO user_groups (user_id, group_name) VALUES (%s,%s)", (uid, g))
    return api_key


def current_user(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> CurrentUser:
    if not x_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-API-Key header")
    user = get_user_by_key(x_api_key)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    return user


def admin_user(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user
