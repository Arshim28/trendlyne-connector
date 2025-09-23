#!/usr/bin/env python3
"""
Seed-based discovery starting with known working examples
"""

import requests
import time
from stock_discovery import StockDiscovery

def seed_discovery():
    """Start with known working examples and expand"""
    discovery = StockDiscovery()

    # Known working examples to seed the database
    seed_stocks = [
        "https://trendlyne.com/equity/1577/MOLDTKPAC/mold-tek-packaging-ltd/",
        # We can add more manually discovered ones here
    ]

    print("=== SEED STOCK DISCOVERY ===")
    print(f"Starting with {len(seed_stocks)} seed stocks")

    success_count = 0
    for equity_url in seed_stocks:
        print(f"\nProcessing seed: {equity_url}")
        if discovery.extract_and_store_stock(equity_url):
            success_count += 1
        time.sleep(1)

    print(f"\nSeed processing complete: {success_count}/{len(seed_stocks)} successful")

    # Test the tokens
    print("\nTesting seed tokens...")
    discovery.test_all_tokens()

    # Show results
    stocks = discovery.db.get_all_stocks()
    print(f"\nDatabase now contains {len(stocks)} stocks")

    for stock in stocks:
        print(f"  {stock['symbol']} (ID: {stock['stock_id']}) - Token: {stock['auth_token'][:20]}... - Status: {stock['token_status']}")

def discover_by_stock_id_range():
    """Try to discover stocks by incrementing stock IDs around known working ones"""
    discovery = StockDiscovery()

    # Start around known working stock ID 1577
    base_id = 1577
    range_size = 10

    print(f"\n=== STOCK ID RANGE DISCOVERY ===")
    print(f"Testing stock IDs around {base_id} (±{range_size})")

    discovered = 0
    for stock_id in range(base_id - range_size, base_id + range_size + 1):
        # Try common URL pattern variations
        test_patterns = [
            f"https://trendlyne.com/equity/{stock_id}/",
            f"https://trendlyne.com/stocks/{stock_id}/",
        ]

        for pattern in test_patterns:
            try:
                print(f"Testing: {pattern}")
                response = discovery.session.get(pattern)

                if response.status_code == 200 and '/equity/' in response.url:
                    # Found a valid equity page, extract its data
                    actual_url = response.url
                    print(f"  ✅ Found: {actual_url}")

                    if discovery.extract_and_store_stock(actual_url):
                        discovered += 1

                    break  # Found valid URL for this stock_id

                time.sleep(0.5)

            except Exception as e:
                print(f"  ❌ Error: {e}")

    print(f"\nRange discovery complete: {discovered} new stocks found")

    # Test all tokens
    discovery.test_all_tokens()

    # Show final results
    stocks = discovery.db.get_all_stocks()
    working_stocks = [s for s in stocks if s['token_status'] == 'working']

    print(f"\nFinal Database Status:")
    print(f"Total stocks: {len(stocks)}")
    print(f"Working tokens: {len(working_stocks)}")

    print("\nAll stocks in database:")
    for stock in stocks:
        status_emoji = "✅" if stock['token_status'] == 'working' else "❓" if stock['token_status'] == 'unknown' else "❌"
        print(f"  {status_emoji} {stock['symbol']} (ID: {stock['stock_id']}) - {stock['company_name']}")

if __name__ == "__main__":
    # First, seed with known working examples
    seed_discovery()

    # Then try to discover more by stock ID range
    discover_by_stock_id_range()