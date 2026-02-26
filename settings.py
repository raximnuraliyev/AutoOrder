"""
Persistent user settings stored as JSON.
Falls back to config.py defaults when no settings file exists.
"""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

import config
from logger import log

_SETTINGS_PATH = Path(__file__).resolve().parent / "user_settings.json"
_lock = Lock()

# ── Notification types ───────────────────────────────────────────
NOTIFY_TYPES: dict[str, str] = {
    "success":  "✅ Order placed successfully",
    "failure":  "⚠️ Order failed (after retries)",
    "crash":    "💥 Unexpected crash / exception",
    "startup":  "ℹ️ Daemon started",
    "window":   "🕐 Outside ordering window",
    "bot_down": "🤖 Bot not responding",
}

# ── Defaults (derived from config.py) ────────────────────────────
_DEFAULTS: dict = {
    "schedule_hours": config.SCHEDULE_HOURS,          # e.g. [8, 14, 17]
    "selected_meals": list(config.MEAL_BUTTONS),      # e.g. ["Nonushta", "Tushlik", "Kechki ovqat"]
    "enabled": True,                                   # master switch
    "notifications": {                                 # per-type toggles
        "success":  True,
        "failure":  True,
        "crash":    True,
        "startup":  True,
        "window":   False,   # noisy — off by default
        "bot_down": True,
    },
}

# Friendly aliases → real meal button names
MEAL_ALIASES: dict[str, str] = {
    "breakfast":  "Nonushta",
    "lunch":      "Tushlik",
    "dinner":     "Kechki ovqat",
    "nonushta":   "Nonushta",
    "tushlik":    "Tushlik",
    "kechki":     "Kechki ovqat",
}

ALL_MEALS: list[str] = list(config.MEAL_BUTTONS)  # canonical order


def _load_raw() -> dict:
    """Load JSON from disk; return empty dict on any error."""
    if not _SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning(f"Corrupted settings file, using defaults: {exc}")
        return {}


def _save_raw(data: dict) -> None:
    """Atomically write settings to disk."""
    _SETTINGS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ─── Public API ──────────────────────────────────────────────────
def get() -> dict:
    """Return merged settings (defaults + user overrides)."""
    with _lock:
        raw = _load_raw()
        merged = {**_DEFAULTS, **raw}
        return merged


def set_schedule_hours(hours: list[int]) -> list[int]:
    """Set which hours (0-23) the daemon checks for orders."""
    hours = sorted(set(h for h in hours if 0 <= h <= 23))
    if not hours:
        raise ValueError("At least one valid hour (0-23) is required.")
    with _lock:
        data = _load_raw()
        data["schedule_hours"] = hours
        _save_raw(data)
    return hours


def set_selected_meals(meal_keys: list[str]) -> list[str]:
    """
    Set which meals to order.
    Accepts friendly names (breakfast/lunch/dinner) or Uzbek names.
    Returns the canonical meal names that were set.
    """
    resolved: list[str] = []
    unknown: list[str] = []
    for key in meal_keys:
        canon = MEAL_ALIASES.get(key.lower().strip())
        if canon and canon not in resolved:
            resolved.append(canon)
        elif key.strip() in ALL_MEALS and key.strip() not in resolved:
            resolved.append(key.strip())
        else:
            if key.lower().strip() not in [r.lower() for r in resolved]:
                unknown.append(key)

    if not resolved:
        raise ValueError(
            f"No valid meals found. Use: breakfast, lunch, dinner "
            f"(or Uzbek: Nonushta, Tushlik, Kechki ovqat).\n"
            f"Unknown: {unknown}"
        )

    # Preserve canonical order
    ordered = [m for m in ALL_MEALS if m in resolved]

    with _lock:
        data = _load_raw()
        data["selected_meals"] = ordered
        _save_raw(data)
    return ordered


def set_enabled(enabled: bool) -> bool:
    """Enable or disable auto-ordering."""
    with _lock:
        data = _load_raw()
        data["enabled"] = enabled
        _save_raw(data)
    return enabled


def get_schedule_hours() -> list[int]:
    return get()["schedule_hours"]


def get_selected_meals() -> list[str]:
    return get()["selected_meals"]


def is_enabled() -> bool:
    return get()["enabled"]


# ─── Notification settings ───────────────────────────────────────
def get_notifications() -> dict[str, bool]:
    """Return the notifications dict (merged with defaults)."""
    s = get()
    defaults = _DEFAULTS["notifications"]
    raw = s.get("notifications", {})
    return {**defaults, **raw}


def is_notify_enabled(notify_type: str) -> bool:
    """Check if a specific notification type is enabled."""
    return get_notifications().get(notify_type, True)


def set_notification(notify_type: str, enabled: bool) -> None:
    """Toggle a single notification type on/off."""
    if notify_type not in NOTIFY_TYPES:
        raise ValueError(
            f"Unknown notification type: {notify_type}. "
            f"Valid: {', '.join(NOTIFY_TYPES.keys())}"
        )
    with _lock:
        data = _load_raw()
        notifs = data.get("notifications", {})
        notifs[notify_type] = enabled
        data["notifications"] = notifs
        _save_raw(data)


def set_all_notifications(enabled: bool) -> None:
    """Turn all notification types on or off."""
    with _lock:
        data = _load_raw()
        data["notifications"] = {k: enabled for k in NOTIFY_TYPES}
        _save_raw(data)
