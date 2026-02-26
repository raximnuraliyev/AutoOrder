"""
Telegram command handler for AutoOrder.

The user controls the bot by sending commands to their own
**Saved Messages** (the chat with yourself in Telegram).

Commands:
  /help                — show this help
  /status              — current schedule, meals, and state
  /schedule 8 14 17    — set check hours (Tashkent time)
  /meals               — show current meal selection
  /meals breakfast lunch dinner — set which meals to order
  /order               — force an immediate order right now
  /on                  — enable auto-ordering
  /off                 — disable auto-ordering
  /notify              — show notification settings
  /notify success on   — toggle a notification type
  /notify all off      — turn all notifications off
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Callable, Awaitable

from telethon import TelegramClient, events

import config
import settings
from logger import log
from notifier import notify

# Type alias for the force-order callback
ForceOrderCallback = Callable[[TelegramClient], Awaitable[bool]]

# Meal display names for pretty output
_MEAL_DISPLAY = {
    "Nonushta": "🍳 Nonushta (Breakfast)",
    "Tushlik": "🍛 Tushlik (Lunch)",
    "Kechki ovqat": "🌙 Kechki ovqat (Dinner)",
}


def _meal_label(meal: str) -> str:
    return _MEAL_DISPLAY.get(meal, meal)


# ─── Command implementations ────────────────────────────────────

async def _cmd_help(client: TelegramClient, _args: str, **_kw) -> str:
    return (
        "🤖 **AutoOrder Commands**\n"
        "\n"
        "/help — show this help\n"
        "/status — current schedule & meal config\n"
        "/schedule `8 14 17` — set check hours (Tashkent)\n"
        "/meals — show current meal selection\n"
        "/meals `breakfast lunch dinner` — set meals\n"
        "    ↳ aliases: breakfast, lunch, dinner\n"
        "    ↳ or Uzbek: Nonushta, Tushlik, Kechki ovqat\n"
        "/order — force an order right now\n"
        "/on — enable auto-ordering\n"
        "/off — disable auto-ordering\n"
        "/notify — show notification settings\n"
        "/notify `success on` — toggle a type\n"
        "/notify `all off` — turn all off/on\n"
    )


async def _cmd_status(client: TelegramClient, _args: str, **kw) -> str:
    s = settings.get()
    now = datetime.now(tz=config.TIMEZONE)
    hours_str = ", ".join(f"{h}:00" for h in s["schedule_hours"])
    meals_str = "\n".join(f"  • {_meal_label(m)}" for m in s["selected_meals"])
    enabled_str = "✅ Enabled" if s["enabled"] else "❌ Disabled"
    last_order = kw.get("last_order_date", "—")

    # Notification summary
    notifs = settings.get_notifications()
    on_count = sum(1 for v in notifs.values() if v)
    total = len(notifs)
    notif_str = f"{on_count}/{total} types enabled"

    return (
        f"📊 **AutoOrder Status**\n"
        f"\n"
        f"**State:** {enabled_str}\n"
        f"**Schedule:** {hours_str} (Tashkent)\n"
        f"**Meals:**\n{meals_str}\n"
        f"**Notifications:** {notif_str} (use /notify)\n"
        f"**Last order date:** {last_order}\n"
        f"**Current time:** {now.strftime('%Y-%m-%d %H:%M')} Tashkent\n"
        f"**Order window:** {config.WINDOW_START_HOUR}:00–{config.WINDOW_END_HOUR}:00\n"
    )


async def _cmd_schedule(client: TelegramClient, args: str, **_kw) -> str:
    if not args.strip():
        hours = settings.get_schedule_hours()
        hours_str = ", ".join(f"{h}:00" for h in hours)
        return (
            f"⏰ **Current schedule:** {hours_str}\n"
            f"\nTo change: `/schedule 8 14 17`"
        )

    parts = args.strip().split()
    try:
        hours = [int(p) for p in parts]
    except ValueError:
        return "❌ Invalid hours. Use numbers 0-23.\nExample: `/schedule 8 14 17`"

    invalid = [h for h in hours if h < 0 or h > 23]
    if invalid:
        return f"❌ Invalid hours: {invalid}. Must be 0-23."

    result = settings.set_schedule_hours(hours)
    hours_str = ", ".join(f"{h}:00" for h in result)
    return f"✅ Schedule updated: **{hours_str}** (Tashkent time)"


async def _cmd_meals(client: TelegramClient, args: str, **_kw) -> str:
    if not args.strip():
        current = settings.get_selected_meals()
        all_meals = settings.ALL_MEALS
        lines = []
        for m in all_meals:
            check = "☑️" if m in current else "⬜"
            lines.append(f"  {check} {_meal_label(m)}")
        return (
            "🍽️ **Current meal selection:**\n"
            + "\n".join(lines)
            + "\n\nTo change: `/meals breakfast lunch dinner`\n"
              "Aliases: breakfast, lunch, dinner"
        )

    parts = args.strip().split()
    try:
        result = settings.set_selected_meals(parts)
    except ValueError as e:
        return f"❌ {e}"

    lines = [f"  ☑️ {_meal_label(m)}" for m in result]
    return "✅ **Meals updated:**\n" + "\n".join(lines)


async def _cmd_order(client: TelegramClient, _args: str, **kw) -> str:
    force_order = kw.get("force_order_callback")
    if force_order is None:
        return "❌ Force-order not available in this mode."

    await notify(client, "🔄 Starting manual order…")

    try:
        success = await force_order(client)
        if success:
            return "✅ Manual order completed successfully!"
        else:
            return "⚠️ Manual order finished but may not have succeeded. Check logs."
    except Exception as exc:
        return f"❌ Manual order failed: {exc}"


async def _cmd_on(client: TelegramClient, _args: str, **_kw) -> str:
    settings.set_enabled(True)
    return "✅ Auto-ordering is now **enabled**."


async def _cmd_off(client: TelegramClient, _args: str, **_kw) -> str:
    settings.set_enabled(False)
    return "⚠️ Auto-ordering is now **disabled**. Orders will NOT run until you `/on` again."


async def _cmd_notify(client: TelegramClient, args: str, **_kw) -> str:
    """Show or toggle notification settings."""
    if not args.strip():
        # Show current notification settings
        notifs = settings.get_notifications()
        lines = []
        for key, desc in settings.NOTIFY_TYPES.items():
            state = "🔔" if notifs.get(key, True) else "🔕"
            lines.append(f"  {state} **{key}** — {desc}")
        return (
            "🔔 **Notification Settings**\n\n"
            + "\n".join(lines)
            + "\n\n"
            "Toggle: `/notify success off`\n"
            "All at once: `/notify all on` or `/notify all off`\n"
            "\n"
            "Types: success, failure, crash, startup, window, bot_down"
        )

    parts = args.strip().lower().split()
    if len(parts) < 2:
        return (
            "❌ Usage: `/notify <type> <on|off>`\n"
            "Example: `/notify crash on`\n"
            "Or: `/notify all off`"
        )

    ntype, state = parts[0], parts[1]

    if state not in ("on", "off"):
        return "❌ Second argument must be `on` or `off`."

    enabled = state == "on"

    if ntype == "all":
        settings.set_all_notifications(enabled)
        emoji = "🔔" if enabled else "🔕"
        return f"{emoji} All notifications turned **{state}**."

    if ntype not in settings.NOTIFY_TYPES:
        valid = ", ".join(settings.NOTIFY_TYPES.keys())
        return f"❌ Unknown type: `{ntype}`\nValid types: {valid}, all"

    try:
        settings.set_notification(ntype, enabled)
    except ValueError as e:
        return f"❌ {e}"

    emoji = "🔔" if enabled else "🔕"
    desc = settings.NOTIFY_TYPES[ntype]
    return f"{emoji} **{ntype}** notifications turned **{state}**.\n({desc})"


# ─── Command router ─────────────────────────────────────────────
_COMMANDS = {
    "/help": _cmd_help,
    "/status": _cmd_status,
    "/schedule": _cmd_schedule,
    "/meals": _cmd_meals,
    "/order": _cmd_order,
    "/on": _cmd_on,
    "/off": _cmd_off,
    "/notify": _cmd_notify,
}


async def _handle_command(
    event: events.NewMessage.Event,
    client: TelegramClient,
    **context,
) -> None:
    """Parse and dispatch a command from Saved Messages."""
    text = (event.raw_text or "").strip()
    if not text.startswith("/"):
        return  # ignore non-commands

    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    handler = _COMMANDS.get(cmd)
    if handler is None:
        response = (
            f"❓ Unknown command: `{cmd}`\n"
            f"Send /help to see available commands."
        )
    else:
        response = await handler(client, args, **context)

    await event.reply(response)


def register_commands(
    client: TelegramClient,
    force_order_callback: ForceOrderCallback | None = None,
    get_last_order_date: Callable[[], str | None] | None = None,
) -> None:
    """
    Register the Saved Messages event handler on the client.

    Args:
        client: Connected TelegramClient.
        force_order_callback: async fn(client) -> bool for /order.
        get_last_order_date: fn() -> str|None for /status.
    """

    @client.on(events.NewMessage(
        # Only handle messages from self → self (Saved Messages)
        outgoing=True,
        incoming=False,
    ))
    async def _on_saved_message(event: events.NewMessage.Event):
        # Only react to messages in Saved Messages (chat with self)
        me = await client.get_me()
        chat = await event.get_chat()

        # Saved Messages = chat where peer is yourself
        if getattr(chat, "id", None) != me.id:
            return

        text = (event.raw_text or "").strip()
        if not text.startswith("/"):
            return

        log.info(f"Command received: {text}")

        context = {
            "force_order_callback": force_order_callback,
            "last_order_date": get_last_order_date() if get_last_order_date else "—",
        }

        await _handle_command(event, client, **context)

    log.info("Command handler registered (listening in Saved Messages)")
