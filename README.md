# 🤖 RustBot — Steam Skin Automation Bot

A Python Telegram bot for automating Steam inventory management, trade offers, and trade history syncing for Rust skins.

## ✨ Features

- 📦 **Inventory Reader** — fetch your full Rust inventory with live market prices
- 🔄 **Trade Automation** — send, accept, cancel trade offers via Telegram
- ✅ **Auto-Accept** — accept all incoming trade offers in one tap
- 📊 **Google Sheets Sync** — push your full Steam trade history to a spreadsheet with `/sync`
- 💬 **Telegram Control Panel** — control everything from your phone

## 🗂️ Project Structure

```
rustbot/
├── bot.py                        # Main entry point
├── requirements.txt
├── .env.example                  # Credentials template
├── test_steam.py                 # Test Steam connection
├── steam/
│   ├── client.py                 # Steam login + session management
│   ├── inventory.py              # Inventory fetcher + price tracker
│   └── trades.py                 # Trade offer logic
├── telegram/
│   ├── trade_commands.py         # /trades /acceptall /sendtrade etc.
│   └── sync_commands.py          # /sync → Google Sheets
└── utils/
    └── sheets_sync.py            # Steam trade history → Google Sheets
```

## ⚙️ Setup

### 1. Clone the repo
```bash
git clone https://github.com/aymanaghi/rustbot.git
cd rustbot
```

### 2. Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure credentials
```bash
cp .env.example .env
nano .env
```

Fill in your values:

| Variable | Where to get it |
|---|---|
| `STEAM_USERNAME` | Your Steam login |
| `STEAM_PASSWORD` | Your Steam password |
| `STEAM_API_KEY` | https://steamcommunity.com/dev/apikey |
| `STEAM_ID_64` | https://steamid.io |
| `STEAM_SHARED_SECRET` | From your `.maFile` (Steam Authenticator) |
| `STEAM_IDENTITY_SECRET` | From your `.maFile` |
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | From [@userinfobot](https://t.me/userinfobot) |
| `GOOGLE_CREDENTIALS_JSON` | Path to your service account JSON |
| `GOOGLE_SHEET_NAME` | Name for your Google Sheet |

### 5. Google Sheets setup (for /sync)
- Go to https://console.cloud.google.com
- Enable **Google Sheets API** + **Google Drive API**
- Create a **Service Account** and download the JSON key
- Save it as `credentials.json` in the project root
- Share your Google Sheet with the service account email

### 6. Test Steam connection
```bash
python test_steam.py
```

### 7. Run the bot
```bash
python bot.py
```

## 📱 Telegram Commands

| Command | Description |
|---|---|
| `/start` | Show all available commands |
| `/inventory` | Show Rust inventory with prices |
| `/trades` | List pending trade offers |
| `/accepttrade <id>` | Accept a specific trade offer |
| `/acceptall` | Accept all incoming offers |
| `/canceltrade <id>` | Cancel an outgoing offer |
| `/sendtrade` | Guided flow to send a trade offer |
| `/sync` | Sync full trade history to Google Sheets |

## 🔒 Security Notes

- Never commit your `.env` or `credentials.json` — both are in `.gitignore`
- Keep the repo **private** if it contains any account-specific config
- The bot only responds to your `TELEGRAM_CHAT_ID` — all other users are ignored

## 🛠️ Built With

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [steampy](https://github.com/bukson/steampy)
- [gspread](https://github.com/burnash/gspread)
- [APScheduler](https://github.com/agronholm/apscheduler)

## 📋 Roadmap

- [ ] Price alert system (`/watchprice`)
- [ ] Daily portfolio value report
- [ ] Inventory export to Google Sheets
- [ ] Trade offer value checker (auto-decline below threshold)
- [ ] Profit/loss calculator

## 📄 License

MIT
