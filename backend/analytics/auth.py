from __future__ import annotations

import os


def is_admin_username(username: str) -> bool:
    """Return True if username is in the AI_TUTOR_ADMIN_USERNAMES allowlist."""
    raw = os.environ.get("AI_TUTOR_ADMIN_USERNAMES", "")
    admins = {u.strip() for u in raw.split(",") if u.strip()}
    return username in admins


def check_admin_password(password: str) -> bool:
    """Return True if password matches AI_TUTOR_ADMIN_PASSWORD."""
    expected = os.environ.get("AI_TUTOR_ADMIN_PASSWORD", "")
    return bool(expected) and password == expected
