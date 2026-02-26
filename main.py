"""
AutoOrder — entry point.

Usage:
  python main.py              # daemon mode (24/7, for Wispbyte / server)
  python main.py --once       # single-shot run (for testing / Task Scheduler)
  python main.py --login      # first-time login only (interactive)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import AuthKeyDuplicatedError

import config
import settings
from commands import register_commands
from logger import log
from notifier import notify_error, notify_info
from order_logic import run_order


def _build_client() -> TelegramClient:
    """Construct a Telethon client from config."""
    if not config.API_ID or not config.API_HASH:
        log.error("API_ID / API_HASH not set. Check your .env file.")
        sys.exit(1)

    return TelegramClient(
        config.SESSION_PATH,
        config.API_ID,
        config.API_HASH,
    )


# ─── Login flow (first time) ───────────────────────────────────
async def interactive_login():
    """Start client, prompt for phone + OTP, save session, exit."""
    client = _build_client()
    log.info("Starting interactive login…")
    await client.start(phone=config.PHONE_NUMBER or None)
    me = await client.get_me()
    log.info(f"Logged in as: {me.first_name} (id={me.id})")
    log.info(f"Session saved to: {config.SESSION_PATH}.session")
    await client.disconnect()


# ─── Single-shot run (for testing / Task Scheduler) ────────────
async def run_once():
    """Connect using saved session, execute order, disconnect."""
    client = _build_client()

    try:
        async with client:
            if not await client.is_user_authorized():
                log.error(
                    "No active session. Run `python main.py --login` first."
                )
                sys.exit(1)

            me = await client.get_me()
            log.info(f"Session active: {me.first_name} (id={me.id})")

            success = await run_order(client)
            status = "SUCCESS" if success else "FAILED"
            log.info(f"══════════ Run finished: {status} ══════════")
            return success
    except AuthKeyDuplicatedError:
        _handle_auth_key_error()
        return False


def _handle_auth_key_error():
    """Handle AuthKeyDuplicatedError by deleting the corrupt session."""
    session_file = Path(config.SESSION_PATH + ".session")
    journal_file = Path(config.SESSION_PATH + ".session-journal")
    log.error(
        "\n"
        "═══════════════════════════════════════════════════════════\n"
        "  SESSION INVALIDATED (AuthKeyDuplicatedError)\n"
        "\n"
        "  The session was used from two different IPs at once.\n"
        "  Telegram revoked it permanently.\n"
        "\n"
        "  FIX: Run `python main.py --login` to create a new session.\n"
        "═══════════════════════════════════════════════════════════"
    )
    # Delete the corrupt session files
    for f in (session_file, journal_file):
        try:
            if f.exists():
                f.unlink()
                log.info(f"Deleted corrupt session file: {f}")
        except OSError as exc:
            log.warning(f"Could not delete {f}: {exc}")


# ─── Daemon mode (24/7 for Wispbyte / server) ──────────────────
async def daemon():
    """
    Long-running process. Stays alive permanently.

    - Checks at EACH configured hour whether food is ordered.
      (e.g., schedule = [8, 14, 17] → checks at 8 AM, 2 PM, 5 PM)
    - Per-hour tracking: each hour fires independently, so the bot
      can retry at 14:00 even if 8:00 failed.
    - Listens for Telegram commands in Saved Messages.
    - Sends notifications to the user on errors / success.
    """
    client = _build_client()

    try:
        async with client:
            if not await client.is_user_authorized():
                log.error(
                    "No active session. Run `python main.py --login` first."
                )
                sys.exit(1)

            me = await client.get_me()
            log.info(f"Session active: {me.first_name} (id={me.id})")

            # ── Shared state ─────────────────────────────────────────
            # Track which (date, hour) combos have already been handled
            completed_runs: set[str] = set()   # "2025-06-15@8", "2025-06-15@14"
            last_heartbeat_hour: int = -1
            last_order_date: str | None = None

            def _get_last_order_date() -> str | None:
                return last_order_date

            # ── Register command handler ─────────────────────────────
            register_commands(
                client,
                force_order_callback=run_order,
                get_last_order_date=_get_last_order_date,
            )

            schedule_hours = settings.get_schedule_hours()
            selected_meals = settings.get_selected_meals()
            hours_str = ", ".join(f"{h}:00" for h in schedule_hours)
            meals_str = ", ".join(selected_meals)
            log.info(
                f"Daemon running 24/7.\n"
                f"  Schedule (Tashkent): {hours_str}\n"
                f"  Meals: {meals_str}\n"
                f"  Enabled: {settings.is_enabled()}"
            )

            await notify_info(
                client,
                f"AutoOrder daemon started.\n"
                f"Schedule: {hours_str}\n"
                f"Meals: {meals_str}\n"
                f"Send /help in Saved Messages for commands.",
            )

            while True:
                now = datetime.now(tz=config.TIMEZONE)
                today = now.strftime("%Y-%m-%d")
                run_key = f"{today}@{now.hour}"

                # ── Heartbeat (once per hour) ────────────────────────
                if now.hour != last_heartbeat_hour:
                    log.info(
                        f"♥ Daemon alive — {now.strftime('%Y-%m-%d %H:%M')} Tashkent"
                    )
                    last_heartbeat_hour = now.hour

                # ── Re-read settings each cycle (user may have changed) ──
                schedule_hours = settings.get_schedule_hours()
                enabled = settings.is_enabled()

                # ── Fire order at each scheduled hour ────────────────
                if (
                    enabled
                    and now.hour in schedule_hours
                    and run_key not in completed_runs
                ):
                    log.info(
                        f"⏰ Schedule triggered: "
                        f"{now.strftime('%H:%M')} Tashkent time"
                    )
                    try:
                        success = await run_order(client)
                        if success:
                            last_order_date = today
                            log.info(
                                f"Order complete for {today} at {now.hour}:00. "
                            )
                        else:
                            log.warning(
                                f"Order run returned failure at {now.hour}:00. "
                                "Marking this hour as done."
                            )
                    except Exception as exc:
                        log.exception(f"Daemon order run crashed: {exc}")
                        await notify_error(
                            client,
                            f"Daemon crash at {now.hour}:00:\n{exc}",
                            kind="crash",
                        )

                    # Mark this (date, hour) as done regardless of outcome
                    completed_runs.add(run_key)

                    # Clean up old entries (keep only today's)
                    old_keys = [k for k in completed_runs if not k.startswith(today)]
                    for k in old_keys:
                        completed_runs.discard(k)

                # ── Sleep between checks ─────────────────────────────
                await asyncio.sleep(30)
    except AuthKeyDuplicatedError:
        _handle_auth_key_error()
        sys.exit(1)


# ─── CLI ────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="AutoOrder — Telegram food bot automation"
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Interactive first-time login (phone + OTP).",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Single-shot order run (for testing / Task Scheduler).",
    )
    args = parser.parse_args()

    now = datetime.now(tz=config.TIMEZONE)
    log.info(
        f"AutoOrder starting at {now.strftime('%Y-%m-%d %H:%M:%S')} Tashkent"
    )

    if args.login:
        asyncio.run(interactive_login())
    elif args.once:
        success = asyncio.run(run_once())
        sys.exit(0 if success else 1)
    else:
        # Default: daemon mode — stays alive 24/7 (for Wispbyte)
        asyncio.run(daemon())


if __name__ == "__main__":
    main()
