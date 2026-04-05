"""
steam/inventory.py
Fetches Rust inventory, parses skin data, and retrieves market prices.
"""

import os
import time
import logging
import requests
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

RUST_APP_ID = 252490
RUST_CONTEXT_ID = 2
STEAM_MARKET_PRICE_URL = "https://steamcommunity.com/market/priceoverview/"
PRICEMPIRE_URL = "https://api.pricempire.com/v3/items/prices"


@dataclass
class RustSkin:
    asset_id: str
    class_id: str
    name: str
    market_hash_name: str
    icon_url: str
    tradable: bool
    marketable: bool
    price_usd: float = 0.0
    price_source: str = "unknown"

    @property
    def icon_full_url(self) -> str:
        return f"https://community.cloudflare.steamstatic.com/economy/image/{self.icon_url}"


class InventoryReader:
    def __init__(self, steam_session):
        self.session = steam_session
        self.steam_id = os.getenv("STEAM_ID_64")
        self.pricempire_key = os.getenv("PRICEMPIRE_API_KEY")
        self._price_cache: dict[str, float] = {}
        self._cache_timestamp: float = 0
        self.CACHE_TTL = 300  # 5 minutes

    def fetch_inventory(self) -> list[RustSkin]:
        """Fetch all Rust skins from Steam inventory."""
        self.session.ensure_logged_in()

        try:
            logger.info("Fetching Rust inventory from Steam...")
            raw = self.session.client.get_my_inventory(
                game=_rust_game_options(),
                merge=True
            )

            skins = []
            for asset_id, item in raw.items():
                skin = RustSkin(
                    asset_id=asset_id,
                    class_id=item.get("classid", ""),
                    name=item.get("name", "Unknown"),
                    market_hash_name=item.get("market_hash_name", ""),
                    icon_url=item.get("icon_url", ""),
                    tradable=bool(item.get("tradable", 0)),
                    marketable=bool(item.get("marketable", 0)),
                )
                skins.append(skin)

            logger.info(f"Found {len(skins)} items in Rust inventory.")
            return skins

        except Exception as e:
            logger.error(f"Failed to fetch inventory: {e}")
            return []

    def fetch_inventory_with_prices(self) -> list[RustSkin]:
        """Fetch inventory and attach market prices to each skin."""
        skins = self.fetch_inventory()
        if not skins:
            return []

        # Prefer Pricempire bulk API if key available, else Steam market
        if self.pricempire_key:
            self._attach_prices_pricempire(skins)
        else:
            self._attach_prices_steam_market(skins)

        return skins

    def get_total_value(self, skins: Optional[list[RustSkin]] = None) -> float:
        """Return total USD value of all priced skins."""
        if skins is None:
            skins = self.fetch_inventory_with_prices()
        return round(sum(s.price_usd for s in skins), 2)

    def get_tradable_skins(self, skins: Optional[list[RustSkin]] = None) -> list[RustSkin]:
        """Return only tradable skins."""
        if skins is None:
            skins = self.fetch_inventory()
        return [s for s in skins if s.tradable]

    def format_inventory_summary(self, skins: Optional[list[RustSkin]] = None) -> str:
        """Format a readable inventory summary for Telegram."""
        if skins is None:
            skins = self.fetch_inventory_with_prices()

        if not skins:
            return "❌ Inventory is empty or could not be loaded."

        tradable = [s for s in skins if s.tradable]
        total_value = self.get_total_value(skins)
        priced = [s for s in skins if s.price_usd > 0]

        # Top 5 most valuable
        top_skins = sorted(priced, key=lambda s: s.price_usd, reverse=True)[:5]

        lines = [
            f"🎒 *Rust Inventory*",
            f"Total items: `{len(skins)}`",
            f"Tradable: `{len(tradable)}`",
            f"Total value: `${total_value:.2f} USD`",
            "",
            "💎 *Top 5 by value:*",
        ]

        for i, skin in enumerate(top_skins, 1):
            tradable_tag = "✅" if skin.tradable else "🔒"
            lines.append(f"{i}. {tradable_tag} `{skin.name}` — *${skin.price_usd:.2f}*")

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    #  Price fetching helpers                                              #
    # ------------------------------------------------------------------ #

    def _attach_prices_pricempire(self, skins: list[RustSkin]):
        """Bulk price fetch via Pricempire API (fast, one request)."""
        try:
            names = list({s.market_hash_name for s in skins if s.market_hash_name})
            params = {
                "api_key": self.pricempire_key,
                "source": "buff163",  # or "steam", "csfloat", etc.
                "appId": RUST_APP_ID,
            }
            # Pricempire accepts names as repeated query params
            resp = requests.get(
                PRICEMPIRE_URL,
                params=params,
                timeout=10
            )
            resp.raise_for_status()
            price_map: dict = resp.json()  # { market_hash_name: { price: ... } }

            for skin in skins:
                entry = price_map.get(skin.market_hash_name)
                if entry and entry.get("price"):
                    skin.price_usd = round(entry["price"] / 100, 2)  # pricempire returns cents
                    skin.price_source = "pricempire"

            logger.info(f"Pricempire: priced {sum(1 for s in skins if s.price_usd > 0)}/{len(skins)} items.")

        except Exception as e:
            logger.warning(f"Pricempire price fetch failed, falling back to Steam Market: {e}")
            self._attach_prices_steam_market(skins)

    def _attach_prices_steam_market(self, skins: list[RustSkin]):
        """
        Fetch prices from Steam Community Market (slow — rate-limited to ~1 req/s).
        Only fetches marketable items to avoid wasted calls.
        """
        marketable = [s for s in skins if s.marketable and s.market_hash_name]
        logger.info(f"Fetching Steam Market prices for {len(marketable)} marketable items (slow)...")

        for skin in marketable:
            # Check local cache first
            cached = self._price_cache.get(skin.market_hash_name)
            if cached and (time.time() - self._cache_timestamp) < self.CACHE_TTL:
                skin.price_usd = cached
                skin.price_source = "steam_market_cached"
                continue

            try:
                resp = requests.get(
                    STEAM_MARKET_PRICE_URL,
                    params={
                        "appid": RUST_APP_ID,
                        "currency": 1,  # USD
                        "market_hash_name": skin.market_hash_name,
                    },
                    timeout=8,
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("success") and data.get("lowest_price"):
                    price_str = data["lowest_price"].replace("$", "").replace(",", "")
                    price = float(price_str)
                    skin.price_usd = price
                    skin.price_source = "steam_market"
                    self._price_cache[skin.market_hash_name] = price
                    self._cache_timestamp = time.time()

            except Exception as e:
                logger.debug(f"Price fetch failed for {skin.name}: {e}")

            time.sleep(1.2)  # Steam Market rate limit: ~1 req/sec


def _rust_game_options():
    """Return steampy GameOptions for Rust."""
    from steampy.models import GameOptions
    return GameOptions.custom(str(RUST_APP_ID), str(RUST_CONTEXT_ID))
