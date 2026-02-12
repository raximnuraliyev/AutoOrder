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
import sys
from datetime import datetime

from telethon import TelegramClient

import config
from logger import log
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


# ─── Daemon mode (24/7 for Wispbyte / server) ──────────────────
async def daemon():
    """
    Long-running process. Stays alive permanently.
    Fires the order once per day at the configured hour (Tashkent time).
    """
    client = _build_client()

    async with client:
        if not await client.is_user_authorized():
            log.error(
                "No active session. Run `python main.py --login` first."
            )
            sys.exit(1)

        me = await client.get_me()
        log.info(f"Session active: {me.first_name} (id={me.id})")
        log.info(
            f"Daemon running 24/7. Scheduled hours (Tashkent): "
            f"{config.SCHEDULE_HOURS}"
        )

        last_order_date: str | None = None
        last_heartbeat_hour: int = -1

        while True:
            now = datetime.now(tz=config.TIMEZONE)
            today = now.strftime("%Y-%m-%d")

            # ── Heartbeat (once per hour) ────────────────────────
            if now.hour != last_heartbeat_hour:
                log.info(
                    f"♥ Daemon alive — {now.strftime('%Y-%m-%d %H:%M')} Tashkent"
                )
                last_heartbeat_hour = now.hour

            # ── Fire order at scheduled hour ─────────────────────
            if now.hour in config.SCHEDULE_HOURS and last_order_date != today:
                log.info(
                    f"⏰ Schedule triggered: "
                    f"{now.strftime('%H:%M')} Tashkent time"
                )
                try:
                    success = await run_order(client)
                    if success:
                        last_order_date = today
                        log.info(
                            f"Order complete for {today}. "
                            f"Next check tomorrow."
                        )
                    else:
                        log.warning(
                            "Order run returned failure. "
                            "Will NOT retry today (meals may be partially set)."
                        )
                        # Mark as done to avoid infinite retry loops
                        last_order_date = today
                except Exception as exc:
                    log.exception(f"Daemon order run crashed: {exc}")
                    # Still mark to prevent spam-retrying
                    last_order_date = today

            # ── Sleep between checks ─────────────────────────────
            await asyncio.sleep(30)


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
