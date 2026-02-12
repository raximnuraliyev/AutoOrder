"""
Core state machine for AutoOrder.

States:
  IDLE  →  TRIGGER  →  SELECTING_MEALS  →  CONFIRMED  |  FAILED

Key safety principle:
  NEVER click a meal button that is already selected (☑️ in message text).
  The buttons are toggles — clicking an already-selected meal DESELECTS it.

Each bot message is a state snapshot (text + buttons).
The script's policy: read state → click only what's missing.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum, auto

from telethon import TelegramClient
from telethon.tl.custom import Message

import config
from logger import log


# ─── State definitions ──────────────────────────────────────────
class State(Enum):
    IDLE = auto()
    TRIGGER = auto()
    SELECTING_MEALS = auto()
    CONFIRMED = auto()
    FAILED = auto()


# ─── Helpers ────────────────────────────────────────────────────
def _button_matches(button_text: str, target: str) -> bool:
    """Case-insensitive, emoji-stripped match."""
    clean = button_text.strip()
    for ch in "✅☑️📋◀️❌⬜🔲":
        clean = clean.replace(ch, "")
    clean = clean.strip()
    return clean.lower() == target.lower()


def _find_button(message: Message, target: str):
    """Return first button whose text fuzzy-matches target, or None."""
    if not message.buttons:
        return None
    for row in message.buttons:
        for btn in row:
            if _button_matches(btn.text, target):
                return btn
    return None


def _list_buttons(message: Message) -> list[str]:
    """Flat list of button texts for logging."""
    if not message.buttons:
        return []
    return [btn.text for row in message.buttons for btn in row]


def _has_meal_buttons(message: Message) -> bool:
    """Check if any button matches a configured meal name."""
    if not message.buttons:
        return False
    for row in message.buttons:
        for btn in row:
            for meal in config.MEAL_BUTTONS:
                if _button_matches(btn.text, meal):
                    return True
    return False


def _get_already_ordered_meals(text: str) -> set[str]:
    """
    Parse the bot's message TEXT to find which meals are already selected.
    The bot marks ordered meals with ☑️ or ✅ in the message body.
    This is the GROUND TRUTH — buttons are just toggle actions.
    """
    if not text:
        return set()
    ordered = set()
    for meal in config.MEAL_BUTTONS:
        if f"☑️ {meal}" in text or f"✅ {meal}" in text:
            ordered.add(meal)
    return ordered


# ─── Polling (replaces date-based waiting) ──────────────────────
async def _poll_for_buttons(
    client: TelegramClient,
    bot_entity,
    timeout: float | None = None,
) -> Message | None:
    """Get the latest message from bot that has inline buttons."""
    if timeout is None:
        timeout = config.POLL_TIMEOUT
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        messages = await client.get_messages(bot_entity, limit=5)
        for msg in messages:
            if msg.buttons:
                return msg
        await asyncio.sleep(config.POLL_INTERVAL)
    return None


async def _poll_for_meal_buttons(
    client: TelegramClient,
    bot_entity,
    timeout: float | None = None,
) -> Message | None:
    """Wait specifically for a message containing meal-related buttons."""
    if timeout is None:
        timeout = config.POLL_TIMEOUT
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        messages = await client.get_messages(bot_entity, limit=5)
        for msg in messages:
            if _has_meal_buttons(msg):
                return msg
        await asyncio.sleep(config.POLL_INTERVAL)
    return None


# ─── Core ordering routine ──────────────────────────────────────
async def execute_order(client: TelegramClient) -> bool:
    """
    Run the full ordering state machine.
    Checks what is already ordered and only selects MISSING meals.
    Returns True on success, False on failure.
    """
    bot = await client.get_entity(f"@{config.BOT_USERNAME}")
    log.info(f"Bot resolved: {bot.first_name} (@{config.BOT_USERNAME})")

    # ── Time-window guard (Tashkent time) ────────────────────────
    now = datetime.now(tz=config.TIMEZONE)
    if not (config.WINDOW_START_HOUR <= now.hour < config.WINDOW_END_HOUR):
        log.warning(
            f"Outside ordering window ({config.WINDOW_START_HOUR}:00–"
            f"{config.WINDOW_END_HOUR}:00 Tashkent). "
            f"Current: {now.strftime('%H:%M')}. Skipping."
        )
        return False

    # ── STEP 1: Send /start ──────────────────────────────────────
    log.info("Sending /start to bot…")
    await client.send_message(bot, "/start")
    await asyncio.sleep(config.DELAY_AFTER_START)

    # ── STEP 2: Get bot response ─────────────────────────────────
    log.info("Waiting for bot response…")
    msg = await _poll_for_buttons(client, bot)
    if msg is None:
        log.error("Bot did not respond with any buttons. Aborting.")
        return False

    buttons = _list_buttons(msg)
    log.info(f"Current buttons: {buttons}")

    # ── STEP 3: Navigate to order form ───────────────────────────
    if _has_meal_buttons(msg):
        log.info("Bot already showing meal selection. Skipping trigger.")
    else:
        trigger = _find_button(msg, config.ORDER_BUTTON_TEXT)
        if trigger is None:
            log.error(
                f'"{config.ORDER_BUTTON_TEXT}" not found. '
                f"Available: {buttons}"
            )
            return False

        log.info(f'Clicking "{trigger.text}"…')
        await trigger.click()
        await asyncio.sleep(config.DELAY_BETWEEN_CLICKS)

        msg = await _poll_for_meal_buttons(client, bot)
        if msg is None:
            log.error("Meal selection form did not appear. Aborting.")
            return False

        buttons = _list_buttons(msg)
        log.info(f"Order form buttons: {buttons}")

    # ── STEP 4: Check what's already ordered (CRITICAL SAFETY) ──
    already_ordered = _get_already_ordered_meals(msg.text or "")

    if already_ordered:
        log.info(f"Already ordered: {already_ordered}")

    meals_needed = [m for m in config.MEAL_BUTTONS if m not in already_ordered]

    if not meals_needed:
        log.info("✅ All meals already ordered! Nothing to click.")
        return True

    log.info(f"Meals still needed: {meals_needed}")

    # ── STEP 5: Click ONLY unordered meal buttons ────────────────
    for meal in meals_needed:
        btn = _find_button(msg, meal)
        if btn is None:
            log.warning(
                f'Button "{meal}" not found. '
                f"Available: {_list_buttons(msg)}. Skipping."
            )
            continue

        log.info(f'Clicking "{btn.text}"…')
        await btn.click()
        await asyncio.sleep(config.DELAY_BETWEEN_CLICKS)

        # Re-fetch current state after click
        updated = await _poll_for_meal_buttons(client, bot, timeout=10)
        if updated is not None:
            msg = updated
            log.info(f"Updated buttons: {_list_buttons(msg)}")

    # ── STEP 6: Verify final state ───────────────────────────────
    await asyncio.sleep(config.DELAY_AFTER_ORDER)

    final_messages = await client.get_messages(bot, limit=3)
    for fmsg in final_messages:
        text = fmsg.text or ""
        final_ordered = _get_already_ordered_meals(text)
        if len(final_ordered) == len(config.MEAL_BUTTONS):
            log.info("✅ Order confirmed! All meals selected.")
            log.info(f"Confirmation:\n{text}")
            return True

    log.info("✅ All needed meal buttons clicked. Order likely placed.")
    return True


# ─── Top-level runner with retries ──────────────────────────────
async def run_order(client: TelegramClient) -> bool:
    """Attempt ordering with retry logic."""
    for attempt in range(1, config.MAX_RETRIES + 1):
        log.info(f"═══ Order attempt {attempt}/{config.MAX_RETRIES} ═══")
        try:
            success = await execute_order(client)
            if success:
                return True
            log.warning(f"Attempt {attempt} did not succeed.")
        except Exception as exc:
            log.exception(f"Attempt {attempt} crashed: {exc}")

        if attempt < config.MAX_RETRIES:
            log.info(f"Waiting {config.RETRY_DELAY}s before retry…")
            await asyncio.sleep(config.RETRY_DELAY)

    log.error("❌ All attempts exhausted. Order was NOT placed.")
    return False
