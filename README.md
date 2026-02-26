# AutoOrder 🍽️

Autonomous Telegram food-ordering bot for **@pdpgrantbot**.  
Logs in as your user account, navigates the bot's inline menus, and selects your chosen meals for tomorrow — every day, at the times you pick.

## Features

- **Multi-schedule**: order at multiple times per day (e.g., 8 AM, 2 PM, 5 PM)
- **Meal selection**: choose any combination of Breakfast / Lunch / Dinner
- **Telegram commands**: control everything from Saved Messages — no code edits needed
- **Error notifications**: get alerted in Telegram if something goes wrong
- **Retry logic**: automatic retries with configurable attempts

## Architecture

```
You (real human)  →  Python script  →  Telethon (user session)  →  Telegram  →  @pdpgrantbot
                  ↕
          Saved Messages (commands & notifications)
```

This is **user-session automation**, not a bot-token flow.

## Project structure

```
AutoOrder/
├── .env                 # secrets (API_ID, API_HASH, PHONE_NUMBER)
├── .gitignore
├── config.py            # static defaults & tunables
├── settings.py          # persistent user preferences (JSON)
├── commands.py          # Telegram command handler (Saved Messages)
├── notifier.py          # send notifications to user via Telegram
├── logger.py            # structured logging (console + daily file)
├── order_logic.py       # core state machine
├── main.py              # CLI entry point
├── user_settings.json   # auto-generated user preferences
├── requirements.txt
└── README.md
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure `.env`

```env
API_ID=#####
API_HASH=#####
PHONE_NUMBER=+######
BOT_USERNAME=pdpgrantbot
```

Put your real phone number (with country code) for the first login.

### 3. First-time login

```bash
python main.py --login
```

This will:
- Prompt for your phone number (if not in `.env`)
- Send you a Telegram OTP code
- Save the session to `auto_order_session.session`

**You only do this once.** After that, the session file handles auth automatically.

### 4. Start the daemon

```bash
python main.py
```

The daemon will:
1. Start listening for your commands in **Saved Messages**
2. Check at each scheduled hour and order if needed
3. Send you notifications on success or failure

## Telegram Commands

Open **Saved Messages** in Telegram (the chat with yourself) and send:

| Command | Description |
|---|---|
| `/help` | Show all available commands |
| `/status` | View current schedule, meals, and state |
| `/schedule 8 14 17` | Set check hours (Tashkent time) |
| `/meals` | View current meal selection |
| `/meals breakfast lunch` | Set which meals to order |
| `/meals dinner` | Order only dinner |
| `/meals breakfast lunch dinner` | Order all three meals |
| `/order` | Force an order right now |
| `/on` | Enable auto-ordering |
| `/off` | Disable auto-ordering |

**Meal aliases:** `breakfast` = Nonushta, `lunch` = Tushlik, `dinner` = Kechki ovqat

### Examples

```
/schedule 8 14 17        → check at 8 AM, 2 PM, and 5 PM
/meals lunch dinner      → only order lunch and dinner
/meals breakfast         → only order breakfast
/off                     → pause auto-ordering
/on                      → resume auto-ordering
/order                   → order right now (manual trigger)
```

## Notifications

AutoOrder sends messages to your **Saved Messages** when:
- ✅ An order is placed successfully
- ⚠️ An order fails (with error details)
- ℹ️ The daemon starts up
- ❌ All retry attempts are exhausted

## Usage modes

| Command | Description |
|---|---|
| `python main.py --login` | Interactive first-time login |
| `python main.py --once` | Single-shot order (for Task Scheduler) |
| `python main.py` | Daemon mode — stays alive 24/7 |

## State machine

```
IDLE  →  TRIGGER  →  SELECTING_MEALS  →  CONFIRMED
                                      →  FAILED (retry)
```

Each bot message = state snapshot (text + buttons).  
Policy = click buttons matching the user's selected meals.

## Logs

Daily logs are saved to `logs/order_YYYY-MM-DD.log`.

## Safety

- 2-second delays between actions
- Ordering window enforced (06:00–19:00)
- Max 3 retry attempts
- Per-hour tracking (each scheduled hour fires independently)
- Session file never committed (`.gitignore`)
- Secrets loaded from environment only
