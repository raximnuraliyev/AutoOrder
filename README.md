# AutoOrder 🍽️

Autonomous Telegram food-ordering bot for **@pdpgrantbot**.  
Logs in as your user account, navigates the bot's inline menus, and selects all three meals (Nonushta, Tushlik, Kechki ovqat) for tomorrow — every day.

## Architecture

```
You (real human)  →  Python script  →  Telethon (user session)  →  Telegram  →  @pdpgrantbot
```

This is **user-session automation**, not a bot-token flow.

## Project structure

```
AutoOrder/
├── .env                 # secrets (API_ID, API_HASH, PHONE_NUMBER)
├── .gitignore
├── config.py            # all tunables in one place
├── logger.py            # structured logging (console + daily file)
├── order_logic.py       # core state machine
├── main.py              # CLI entry point
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

### 4. Test a manual run

```bash
python main.py
```

Watch the console — it will:
1. Send `/start` to the bot
2. Click **📋 Ertangi buyurtma**
3. Click **Nonushta**, **Tushlik**, **Kechki ovqat** one by one
4. Log confirmation

### 5. Schedule with Windows Task Scheduler

1. Open **Task Scheduler** → Create Basic Task
2. **Trigger**: Daily at `08:00`
3. **Action**: Start a program
   - Program: `python` (or full path to `python.exe`)
   - Arguments: `main.py`
   - Start in: `D:\AutoOrder`
4. Optional: add a second trigger at `08:30` as backup

Or via PowerShell:

```powershell
$action = New-ScheduledTaskAction -Execute "python" -Argument "main.py" -WorkingDirectory "D:\AutoOrder"
$trigger = New-ScheduledTaskTrigger -Daily -At 8:00AM
Register-ScheduledTask -TaskName "AutoOrder" -Action $action -Trigger $trigger -Description "Daily food order"
```

## Usage modes

| Command | Description |
|---|---|
| `python main.py --login` | Interactive first-time login |
| `python main.py` | Single-shot order (for Task Scheduler) |
| `python main.py --daemon` | Long-running, fires at scheduled hours |

## State machine

```
IDLE  →  TRIGGER  →  SELECTING_MEALS  →  CONFIRMED
                                      →  FAILED (retry)
```

Each bot message = state snapshot (text + buttons).  
Policy = click buttons matching the configured meal list.

## Logs

Daily logs are saved to `logs/order_YYYY-MM-DD.log`.

## Safety

- 2-second delays between actions
- Ordering window enforced (06:00–19:00)
- Max 3 retry attempts
- Session file never committed (`.gitignore`)
- Secrets loaded from environment only
#
