"""
bot.py
Main entry point. Starts the Telegram bot and registers all handlers.
Usage: python bot.py
"""

import os
import logging
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

from steam import SteamSession, InventoryReader
from telegram.trade_commands import TradeCommandHandler

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *RustBot Online*\n\n"
        "Available commands:\n"
        "`/inventory` — show your Rust inventory + values\n"
        "`/trades` — list pending trade offers\n"
        "`/accepttrade <id>` — accept a specific offer\n"
        "`/acceptall` — accept all incoming offers\n"
        "`/canceltrade <id>` — cancel an outgoing offer\n"
        "`/sendtrade` — send a new trade offer\n",
        parse_mode="Markdown"
    )


async def cmd_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    allowed = int(os.getenv("TELEGRAM_CHAT_ID", "0"))
    if update.effective_chat.id != allowed:
        return

    await update.message.reply_text("⏳ Loading inventory...")
    session: SteamSession = context.bot_data["steam_session"]
    inv = InventoryReader(session)
    skins = inv.fetch_inventory_with_prices()
    summary = inv.format_inventory_summary(skins)
    await update.message.reply_text(summary, parse_mode="Markdown")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = int(os.getenv("TELEGRAM_CHAT_ID", "0"))

    if not token:
        raise EnvironmentError("TELEGRAM_BOT_TOKEN not set in .env")

    # Steam login
    logger.info("Initialising Steam session...")
    steam = SteamSession()
    if not steam.login():
        raise ConnectionError("Steam login failed. Check credentials.")

    # Build Telegram app
    app = Application.builder().token(token).build()
    app.bot_data["steam_session"] = steam

    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("inventory", cmd_inventory))

    trade_handler = TradeCommandHandler(steam, allowed_chat_id=chat_id)
    trade_handler.register(app)

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
