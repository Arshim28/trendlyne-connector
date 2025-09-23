#!/usr/bin/env python3
"""
Enhanced discovery that handles redirects and follows links to get full equity URLs
"""

import requests
import time
import re
from stock_discovery import StockDiscovery

def enhanced_stock_discovery():
    """Enhanced discovery that follows redirects to get complete equity URLs"""
    discovery = StockDiscovery()

    print("=== ENHANCED STOCK DISCOVERY ===")

    # Known working stock ID to start from
    base_id = 1577
    range_size = 20

    print(f"Systematically discovering stocks around ID {base_id} (±{range_size})")

    discovered = 0
    failed = 0

    for stock_id in range(base_id - range_size, base_id + range_size + 1):
        try:
            # Test basic equity URL pattern
            test_url = f"https://trendlyne.com/equity/{stock_id}/"
            print(f"Testing stock ID {stock_id}...")

            response = discovery.session.get(test_url, allow_redirects=True)

            if response.status_code == 200:
                final_url = response.url

                # Check if we got a proper equity page with full path
                equity_pattern = r'/equity/(\d+)/([A-Z0-9]+)/([^/]+)/?'
                if re.search(equity_pattern, final_url):
                    print(f"  ✅ Valid equity page: {final_url}")

                    # Extract stock data and token
                    if discovery.extract_and_store_stock(final_url):
                        discovered += 1
                        print(f"  💾 Stored stock data successfully")
                    else:
                        print(f"  ❌ Failed to extract data")
                        failed += 1

                else:
                    print(f"  ⚠️  Redirect but not full equity page: {final_url}")
                    failed += 1

            else:
                print(f"  ❌ HTTP {response.status_code}")
                failed += 1

            time.sleep(0.8)  # Rate limiting

        except Exception as e:
            print(f"  💥 Error: {e}")
            failed += 1

    print(f"\nDiscovery complete:")
    print(f"  Discovered: {discovered}")
    print(f"  Failed: {failed}")

    # Test all discovered tokens
    print(f"\nTesting all discovered tokens...")
    discovery.test_all_tokens()

    # Show final results
    stocks = discovery.db.get_all_stocks()
    working_stocks = [s for s in stocks if s['token_status'] == 'working']

    print(f"\n=== FINAL RESULTS ===")
    print(f"Total stocks in database: {len(stocks)}")
    print(f"Stocks with working tokens: {len(working_stocks)}")

    print(f"\nWorking stocks:")
    for stock in working_stocks:
        print(f"  ✅ {stock['symbol']} (ID: {stock['stock_id']}) - {stock['company_name']}")
        print(f"     Token: {stock['auth_token']}")
        print(f"     URL: {stock['equity_url']}")
        print()

    return working_stocks

def test_discovered_stocks(working_stocks):
    """Test API calls for all discovered working stocks"""
    print(f"\n=== TESTING API CALLS FOR {len(working_stocks)} STOCKS ===")

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...',
        'X-Requested-With': 'XMLHttpRequest'
    }

    successful_calls = 0

    for stock in working_stocks[:5]:  # Test first 5
        try:
            api_url = f"https://trendlyne.com/mapp/v1/stock/web/ohlc/{stock['stock_id']}/{stock['auth_token']}/"
            headers['Referer'] = stock['equity_url']

            print(f"Testing API for {stock['symbol']}...")
            response = requests.get(api_url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                live_data_count = len(data.get('body', {}).get('liveData', []))
                print(f"  ✅ Success! {live_data_count} live data points")
                successful_calls += 1

                # Save sample for this stock
                with open(f"sample_{stock['symbol']}_data.json", 'w') as f:
                    import json
                    json.dump(data, f, indent=2)
                print(f"  💾 Saved sample data to sample_{stock['symbol']}_data.json")

            else:
                print(f"  ❌ Failed: HTTP {response.status_code}")

            time.sleep(1)

        except Exception as e:
            print(f"  💥 Error: {e}")

    print(f"\nAPI Testing complete: {successful_calls}/{len(working_stocks[:5])} successful")

if __name__ == "__main__":
    # Run enhanced discovery
    working_stocks = enhanced_stock_discovery()

    # Test the discovered stocks
    if working_stocks:
        test_discovered_stocks(working_stocks)

        print(f"\n🎉 SUCCESS! Discovered {len(working_stocks)} working stock/token pairs")
        print("These can now be used for programmatic data collection!")
    else:
        print("\n❌ No working stocks discovered. Check the discovery logic.")