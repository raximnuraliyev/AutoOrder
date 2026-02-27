"""
Send notifications to the user via Telegram (Saved Messages).

Saved Messages = sending to yourself. Works with user-session Telethon.
Each notification call checks the per-type toggle in settings.
"""

from __future__ import annotations

from telethon import TelegramClient
from logger import log
import settings


# Cache the user entity to avoid repeated get_me() calls
_me_cache = None


async def _send(client: TelegramClient, text: str) -> None:
    """Low-level: send a message to Saved Messages (always)."""
    global _me_cache
    try:
        if _me_cache is None:
            _me_cache = await client.get_me()
        await client.send_message(_me_cache.id, text)
    except Exception as exc:
        _me_cache = None  # reset cache on failure
        log.error(f"Failed to send notification: {exc}")


async def notify(client: TelegramClient, text: str) -> None:
    """Send unconditionally (used by command replies)."""
    await _send(client, text)


async def notify_success(client: TelegramClient, msg: str) -> None:
    """Notify user about a successful order (type: success)."""
    if not settings.is_notify_enabled("success"):
        return
    await _send(client, f"✅ **AutoOrder**\n\n{msg}")


async def notify_error(client: TelegramClient, error_msg: str, *, kind: str = "failure") -> None:
    """
    Notify user about an error.

    Args:
        kind: notification type for toggle check.
              "failure"  — order failed after retries
              "crash"    — unexpected exception
              "window"   — outside ordering window
              "bot_down" — bot not responding
    """
    if not settings.is_notify_enabled(kind):
        return
    await _send(client, f"⚠️ **AutoOrder Error**\n\n{error_msg}")


async def notify_info(client: TelegramClient, msg: str) -> None:
    """Inform the user (type: startup)."""
    if not settings.is_notify_enabled("startup"):
        return
    await _send(client, f"ℹ️ **AutoOrder**\n\n{msg}")
