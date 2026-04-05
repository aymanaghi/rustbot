"""
telegram/trade_commands.py
Telegram bot handlers for all Steam trade offer actions.
Commands:
  /trades           - list pending incoming + outgoing offers
  /accepttrade <id> - accept a specific trade offer
  /acceptall        - auto-accept all incoming offers
  /canceltrade <id> - cancel an outgoing offer
  /sendtrade        - guided flow to send a trade offer
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from steam import SteamSession, InventoryReader, TradeManager

logger = logging.getLogger(__name__)

# Conversation states for /sendtrade flow
ASK_TRADE_URL, ASK_ASSET_IDS, CONFIRM_TRADE = range(3)


class TradeCommandHandler:
    def __init__(self, steam_session: SteamSession, allowed_chat_id: int):
        self.session = steam_session
        self.inventory = InventoryReader(steam_session)
        self.trades = TradeManager(steam_session)
        self.allowed_chat_id = allowed_chat_id

    def _is_authorized(self, update: Update) -> bool:
        return update.effective_chat.id == self.allowed_chat_id

    # ------------------------------------------------------------------ #
    #  /trades — list pending offers                                       #
    # ------------------------------------------------------------------ #

    async def cmd_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        await update.message.reply_text("🔍 Fetching trade offers...")
        summary = self.trades.get_pending_offers_summary()

        keyboard = [
            [InlineKeyboardButton("✅ Accept All Incoming", callback_data="acceptall")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_trades")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(summary, parse_mode="Markdown", reply_markup=reply_markup)

    # ------------------------------------------------------------------ #
    #  /accepttrade <offer_id>                                             #
    # ------------------------------------------------------------------ #

    async def cmd_accept_trade(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        if not context.args:
            await update.message.reply_text("Usage: `/accepttrade <offer_id>`", parse_mode="Markdown")
            return

        offer_id = context.args[0].strip()
        await update.message.reply_text(f"⏳ Accepting trade `{offer_id}`...", parse_mode="Markdown")

        success = self.trades.accept_trade_offer(offer_id)
        if success:
            await update.message.reply_text(f"✅ Trade `{offer_id}` accepted!", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Failed to accept trade `{offer_id}`. Check logs.", parse_mode="Markdown")

    # ------------------------------------------------------------------ #
    #  /acceptall — accept every pending incoming offer                   #
    # ------------------------------------------------------------------ #

    async def cmd_accept_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        await update.message.reply_text("⏳ Accepting all incoming trade offers...")
        result = self.trades.auto_accept_all_offers()

        msg = (
            f"✅ *Auto-Accept Complete*\n\n"
            f"Accepted: `{result['accepted']}`\n"
            f"Failed:   `{result['failed']}`\n"
            f"Total:    `{result['total']}`"
        )
        if result.get("error"):
            msg += f"\n\n⚠️ Error: `{result['error']}`"

        await update.message.reply_text(msg, parse_mode="Markdown")

    # ------------------------------------------------------------------ #
    #  /canceltrade <offer_id>                                             #
    # ------------------------------------------------------------------ #

    async def cmd_cancel_trade(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        if not context.args:
            await update.message.reply_text("Usage: `/canceltrade <offer_id>`", parse_mode="Markdown")
            return

        offer_id = context.args[0].strip()
        await update.message.reply_text(f"⏳ Cancelling trade `{offer_id}`...", parse_mode="Markdown")

        success = self.trades.cancel_trade_offer(offer_id)
        if success:
            await update.message.reply_text(f"✅ Trade `{offer_id}` cancelled.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Failed to cancel trade `{offer_id}`.", parse_mode="Markdown")

    # ------------------------------------------------------------------ #
    #  /sendtrade — multi-step conversation flow                           #
    # ------------------------------------------------------------------ #

    async def cmd_sendtrade_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Step 1: Ask for partner's trade URL."""
        if not self._is_authorized(update):
            return ConversationHandler.END

        await update.message.reply_text(
            "📤 *Send Trade Offer*\n\n"
            "Step 1/3: Paste the recipient's Steam *trade URL*:\n"
            "`https://steamcommunity.com/tradeoffer/new/?partner=...&token=...`\n\n"
            "Send /cancel to abort.",
            parse_mode="Markdown"
        )
        return ASK_TRADE_URL

    async def cmd_sendtrade_get_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Step 2: Got trade URL, show inventory and ask for asset IDs."""
        trade_url = update.message.text.strip()

        if not trade_url.startswith("https://steamcommunity.com/tradeoffer"):
            await update.message.reply_text("❌ That doesn't look like a valid trade URL. Try again or /cancel.")
            return ASK_TRADE_URL

        context.user_data["trade_url"] = trade_url
        await update.message.reply_text("⏳ Loading your tradable inventory...")

        skins = self.inventory.fetch_inventory_with_prices()
        tradable = self.inventory.get_tradable_skins(skins)

        if not tradable:
            await update.message.reply_text("❌ No tradable skins in your inventory.")
            return ConversationHandler.END

        # Show tradable skins with asset IDs
        lines = ["📦 *Tradable Skins* — copy the Asset IDs you want to send:\n"]
        for skin in tradable[:20]:  # cap at 20 for readability
            price_str = f"${skin.price_usd:.2f}" if skin.price_usd else "n/a"
            lines.append(f"• `{skin.asset_id}` — {skin.name} ({price_str})")

        if len(tradable) > 20:
            lines.append(f"\n_...and {len(tradable) - 20} more. Use /inventory for full list._")

        lines.append("\nStep 2/3: Send the *Asset IDs* to include, separated by commas.\nExample: `12345678,87654321`")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return ASK_ASSET_IDS

    async def cmd_sendtrade_get_assets(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Step 3: Got asset IDs, ask for confirmation."""
        raw = update.message.text.strip()
        asset_ids = [a.strip() for a in raw.split(",") if a.strip().isdigit()]

        if not asset_ids:
            await update.message.reply_text("❌ No valid asset IDs found. Send comma-separated numbers or /cancel.")
            return ASK_ASSET_IDS

        context.user_data["asset_ids"] = asset_ids

        # Lookup names for confirmation
        skins = self.inventory.fetch_inventory()
        skin_map = {s.asset_id: s.name for s in skins}

        lines = [f"📋 *Confirm Trade Offer*\n"]
        lines.append(f"To: `{context.user_data['trade_url'][:60]}...`\n")
        lines.append("Items to send:")
        for aid in asset_ids:
            name = skin_map.get(aid, "Unknown item")
            lines.append(f"  • `{aid}` — {name}")

        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm & Send", callback_data="confirm_send_trade"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_send_trade"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=reply_markup)
        return CONFIRM_TRADE

    async def cmd_sendtrade_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Final step: send the actual trade offer."""
        query = update.callback_query
        await query.answer()

        if query.data == "cancel_send_trade":
            await query.edit_message_text("❌ Trade offer cancelled.")
            return ConversationHandler.END

        asset_ids = context.user_data.get("asset_ids", [])
        trade_url = context.user_data.get("trade_url", "")

        await query.edit_message_text("⏳ Sending trade offer to Steam...")

        offer_id = self.trades.send_trade_offer(
            partner_steam_id="",  # steampy extracts this from the trade URL
            their_trade_url=trade_url,
            asset_ids_to_send=asset_ids,
            message="Sent via RustBot 🤖",
        )

        if offer_id:
            await query.edit_message_text(
                f"✅ *Trade offer sent!*\nOffer ID: `{offer_id}`\n\nUse `/canceltrade {offer_id}` to cancel.",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("❌ Trade offer failed. Check logs for details.")

        return ConversationHandler.END

    async def cmd_cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("❌ Trade flow cancelled.")
        return ConversationHandler.END

    # ------------------------------------------------------------------ #
    #  Inline button callbacks                                             #
    # ------------------------------------------------------------------ #

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == "acceptall":
            await query.edit_message_text("⏳ Accepting all incoming offers...")
            result = self.trades.auto_accept_all_offers()
            await query.edit_message_text(
                f"✅ Done! Accepted `{result['accepted']}` / `{result['total']}` offers.",
                parse_mode="Markdown"
            )

        elif query.data == "refresh_trades":
            summary = self.trades.get_pending_offers_summary()
            keyboard = [
                [InlineKeyboardButton("✅ Accept All Incoming", callback_data="acceptall")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_trades")],
            ]
            await query.edit_message_text(
                summary,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    # ------------------------------------------------------------------ #
    #  Register all handlers onto the Application                         #
    # ------------------------------------------------------------------ #

    def register(self, app):
        """Register all trade command handlers with a python-telegram-bot Application."""

        # Send trade conversation
        send_trade_conv = ConversationHandler(
            entry_points=[CommandHandler("sendtrade", self.cmd_sendtrade_start)],
            states={
                ASK_TRADE_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.cmd_sendtrade_get_url)],
                ASK_ASSET_IDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.cmd_sendtrade_get_assets)],
                CONFIRM_TRADE:  [CallbackQueryHandler(self.cmd_sendtrade_confirm, pattern="^(confirm|cancel)_send_trade$")],
            },
            fallbacks=[CommandHandler("cancel", self.cmd_cancel_conversation)],
        )

        app.add_handler(CommandHandler("trades", self.cmd_trades))
        app.add_handler(CommandHandler("accepttrade", self.cmd_accept_trade))
        app.add_handler(CommandHandler("acceptall", self.cmd_accept_all))
        app.add_handler(CommandHandler("canceltrade", self.cmd_cancel_trade))
        app.add_handler(send_trade_conv)
        app.add_handler(CallbackQueryHandler(self.handle_callback, pattern="^(acceptall|refresh_trades)$"))

        logger.info("Trade command handlers registered.")
