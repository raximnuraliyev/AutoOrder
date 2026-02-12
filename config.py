"""
Configuration layer for AutoOrder.
Loads secrets from environment / .env file.
All tunables live here — nothing is hardcoded elsewhere.
"""

import os
from datetime import timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env next to this file ──────────────────────────────────
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)

# ── Telegram credentials ────────────────────────────────────────
API_ID: int = int(os.getenv("API_ID", "0"))
API_HASH: str = os.getenv("API_HASH", "")
PHONE_NUMBER: str = os.getenv("PHONE_NUMBER", "")  # only needed on first login
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "pdpgrantbot")

# ── Session file ────────────────────────────────────────────────
SESSION_NAME: str = "auto_order_session"
SESSION_PATH: str = str(Path(__file__).resolve().parent / SESSION_NAME)

# ── Ordering policy ─────────────────────────────────────────────
# Button texts the script must click (order matters: click top→bottom)
ORDER_BUTTON_TEXT: str = "Ertangi buyurtma"  # the trigger button (📋 prefix in bot)
MEAL_BUTTONS: list[str] = [
    "Nonushta",      # Breakfast
    "Tushlik",       # Lunch
    "Kechki ovqat",  # Dinner
]

# ── Timezone ─────────────────────────────────────────────────────
# Tashkent = UTC+5.  All schedule logic uses this.
TIMEZONE = timezone(timedelta(hours=5))

# ── Timing ───────────────────────────────────────────────────────
# Ordering window enforced by the bot: 06:00 – 19:00 Tashkent
WINDOW_START_HOUR: int = 6
WINDOW_END_HOUR: int = 19

# Daemon fires at these hours (Tashkent time)
SCHEDULE_HOURS: list[int] = [8]

# ── Delays (seconds) — be polite to Telegram ────────────────────
DELAY_AFTER_START: float = 3.0      # after sending /start
DELAY_BETWEEN_CLICKS: float = 3.0   # between each button click
DELAY_AFTER_ORDER: float = 2.0      # after final click, before reading confirmation

# ── Polling ──────────────────────────────────────────────────────
POLL_TIMEOUT: float = 20.0          # max wait for bot reply
POLL_INTERVAL: float = 2.0          # seconds between polls

# ── Retry / safety ──────────────────────────────────────────────
MAX_RETRIES: int = 3
RETRY_DELAY: float = 5.0            # seconds between retries

# ── Logging ──────────────────────────────────────────────────────
LOG_DIR: str = str(Path(__file__).resolve().parent / "logs")
LOG_ENABLED: bool = True
