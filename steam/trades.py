"""
steam/trades.py
Send, accept, decline, and monitor Steam trade offers for Rust skins.
"""

import logging
from typing import Optional
from steampy.models import TradeOfferState
from .inventory import RustSkin

logger = logging.getLogger(__name__)


class TradeManager:
    def __init__(self, steam_session):
        self.session = steam_session

    # ------------------------------------------------------------------ #
    #  Sending trade offers                                                #
    # ------------------------------------------------------------------ #

    def send_trade_offer(
        self,
        partner_steam_id: str,
        their_trade_url: str,
        asset_ids_to_send: list[str],
        message: str = "RustBot Trade",
    ) -> Optional[str]:
        """
        Send a trade offer to a partner.

        Args:
            partner_steam_id: 64-bit SteamID of the recipient.
            their_trade_url:   Full trade URL (includes token param).
            asset_ids_to_send: List of asset IDs from our inventory to send.
            message:           Optional message attached to the trade.

        Returns:
            Trade offer ID string if successful, None on failure.
        """
        self.session.ensure_logged_in()

        try:
            # Build the items_to_send list in steampy format
            my_items = [
                {"appid": "252490", "contextid": "2", "assetid": asset_id, "amount": "1"}
                for asset_id in asset_ids_to_send
            ]

            logger.info(f"Sending trade offer to {partner_steam_id} with {len(my_items)} items...")

            offer_id = self.session.client.make_offer_with_url(
                items_from_me=my_items,
                items_from_them=[],
                trade_offer_url=their_trade_url,
                message=message,
            )

            logger.info(f"Trade offer sent! Offer ID: {offer_id}")
            return offer_id

        except Exception as e:
            logger.error(f"Failed to send trade offer: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  Accepting trade offers                                              #
    # ------------------------------------------------------------------ #

    def accept_trade_offer(self, trade_offer_id: str) -> bool:
        """Accept an incoming trade offer by ID."""
        self.session.ensure_logged_in()

        try:
            logger.info(f"Accepting trade offer {trade_offer_id}...")
            self.session.client.accept_trade_offer(trade_offer_id)
            logger.info(f"Trade offer {trade_offer_id} accepted.")
            return True
        except Exception as e:
            logger.error(f"Failed to accept trade offer {trade_offer_id}: {e}")
            return False

    def auto_accept_all_offers(self) -> dict:
        """
        Auto-accept all pending incoming trade offers.
        Returns a summary dict with accepted/failed counts.
        """
        self.session.ensure_logged_in()

        try:
            offers_data = self.session.client.get_trade_offers(merge=True)
            incoming = offers_data.get("trade_offers_received", [])
            active = [
                o for o in incoming
                if o.get("trade_offer_state") == TradeOfferState.Active.value
            ]

            accepted = 0
            failed = 0

            for offer in active:
                offer_id = offer.get("tradeofferid")
                if self.accept_trade_offer(offer_id):
                    accepted += 1
                else:
                    failed += 1

            logger.info(f"Auto-accept complete: {accepted} accepted, {failed} failed.")
            return {"accepted": accepted, "failed": failed, "total": len(active)}

        except Exception as e:
            logger.error(f"Auto-accept failed: {e}")
            return {"accepted": 0, "failed": 0, "total": 0, "error": str(e)}

    # ------------------------------------------------------------------ #
    #  Cancelling / declining offers                                       #
    # ------------------------------------------------------------------ #

    def cancel_trade_offer(self, trade_offer_id: str) -> bool:
        """Cancel an outgoing trade offer."""
        self.session.ensure_logged_in()
        try:
            self.session.client.cancel_trade_offer(trade_offer_id)
            logger.info(f"Trade offer {trade_offer_id} cancelled.")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel offer {trade_offer_id}: {e}")
            return False

    def decline_trade_offer(self, trade_offer_id: str) -> bool:
        """Decline an incoming trade offer."""
        self.session.ensure_logged_in()
        try:
            self.session.client.decline_trade_offer(trade_offer_id)
            logger.info(f"Trade offer {trade_offer_id} declined.")
            return True
        except Exception as e:
            logger.error(f"Failed to decline offer {trade_offer_id}: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  Listing active offers                                               #
    # ------------------------------------------------------------------ #

    def get_pending_offers_summary(self) -> str:
        """Return a Telegram-formatted summary of pending trade offers."""
        self.session.ensure_logged_in()

        try:
            offers_data = self.session.client.get_trade_offers(merge=True)
            incoming = offers_data.get("trade_offers_received", [])
            outgoing = offers_data.get("trade_offers_sent", [])

            active_in = [
                o for o in incoming
                if o.get("trade_offer_state") == TradeOfferState.Active.value
            ]
            active_out = [
                o for o in outgoing
                if o.get("trade_offer_state") == TradeOfferState.Active.value
            ]

            lines = ["🔄 *Pending Trade Offers*", ""]

            if active_in:
                lines.append(f"📥 *Incoming ({len(active_in)}):*")
                for o in active_in[:5]:
                    oid = o.get("tradeofferid", "?")
                    partner = o.get("steamid_other", "?")
                    items_in = len(o.get("items_to_receive", []))
                    items_out = len(o.get("items_to_give", []))
                    lines.append(f"  • ID `{oid}` | Partner `{partner[-4:]}...` | ↓{items_in} ↑{items_out}")
            else:
                lines.append("📥 No incoming offers.")

            lines.append("")

            if active_out:
                lines.append(f"📤 *Outgoing ({len(active_out)}):*")
                for o in active_out[:5]:
                    oid = o.get("tradeofferid", "?")
                    partner = o.get("steamid_other", "?")
                    items_out = len(o.get("items_to_give", []))
                    lines.append(f"  • ID `{oid}` | Partner `{partner[-4:]}...` | ↑{items_out} items")
            else:
                lines.append("📤 No outgoing offers.")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to fetch trade offers: {e}")
            return f"❌ Could not load trade offers: {e}"
