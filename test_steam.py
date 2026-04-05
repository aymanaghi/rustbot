"""
test_steam.py
Run this to verify your Steam credentials and inventory fetching work.
Usage: python test_steam.py
"""

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

from steam import SteamSession, InventoryReader, TradeManager


def main():
    print("=" * 50)
    print("  RustBot - Steam Module Test")
    print("=" * 50)

    # 1. Login
    print("\n[1] Testing Steam login...")
    session = SteamSession()
    if not session.login():
        print("❌ Login failed. Check your .env credentials.")
        return
    print("✅ Login successful!")

    # 2. Inventory fetch
    print("\n[2] Fetching Rust inventory (no prices)...")
    inv = InventoryReader(session)
    skins = inv.fetch_inventory()
    print(f"✅ Found {len(skins)} items.")
    if skins:
        print(f"   Example: {skins[0].name} | Tradable: {skins[0].tradable}")

    # 3. Inventory + prices (Steam Market, slow)
    print("\n[3] Fetching prices (this may take a while on Steam Market)...")
    skins_with_prices = inv.fetch_inventory_with_prices()
    total = inv.get_total_value(skins_with_prices)
    print(f"✅ Total inventory value: ${total:.2f} USD")

    # 4. Summary output (Telegram format)
    print("\n[4] Telegram summary preview:")
    print("-" * 40)
    print(inv.format_inventory_summary(skins_with_prices))
    print("-" * 40)

    # 5. Pending trades
    print("\n[5] Checking pending trade offers...")
    trades = TradeManager(session)
    print(trades.get_pending_offers_summary())

    print("\n✅ All tests passed. Steam module is ready!")


if __name__ == "__main__":
    main()
