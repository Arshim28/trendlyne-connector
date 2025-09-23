#!/usr/bin/env python3
"""
Mass Discovery Pipeline: Search API → Extract Tokens → Build Database
"""

import requests
import json
import time
from stock_discovery import StockDiscovery

def search_for_stocks(search_terms, limit_per_term=20):
    """Use search API to find stocks"""

    search_url = "https://trendlyne.com/member/api/ac_snames/all/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...',
        'Accept': '*/*',
        'X-Requested-With': 'XMLHttpRequest'
    }

    all_stocks = []

    for term in search_terms:
        try:
            params = {'term': term, 'all-results': 'true'}
            response = requests.get(search_url, headers=headers, params=params)

            if response.status_code == 200:
                stocks = response.json()
                print(f"Search '{term}': {len(stocks)} stocks found")

                # Filter for Indian equity stocks with valid URLs
                valid_stocks = []
                for stock in stocks[:limit_per_term]:
                    if (stock.get('category') == 'Equity' and
                        stock.get('country') == 'IND' and
                        'urls' in stock and stock['urls']):

                        # Extract equity URL
                        equity_url = stock['urls'][0][1]
                        if '/equity/' in equity_url and 'trendlyne.com/equity/' in equity_url:
                            stock['equity_url'] = equity_url
                            valid_stocks.append(stock)

                all_stocks.extend(valid_stocks)
                print(f"  → {len(valid_stocks)} valid equity stocks")

            time.sleep(0.5)  # Rate limiting

        except Exception as e:
            print(f"Error searching '{term}': {e}")

    return all_stocks

def run_mass_discovery():
    """Run comprehensive stock discovery pipeline"""

    print("=== MASS STOCK DISCOVERY PIPELINE ===")

    # Comprehensive search terms to cover major stocks
    search_terms = [
        "adani", "reliance", "tata", "infosys", "hdfc", "icici", "sbi", "wipro",
        "bharti", "itc", "asian", "bajaj", "mahindra", "maruti", "hero",
        "axis", "kotak", "sun", "dr", "ultra", "tech", "ltd", "bank",
        "power", "oil", "gas", "steel", "pharma", "auto", "cement"
    ]

    # Step 1: Search for stocks
    print(f"\n1. Searching for stocks using {len(search_terms)} terms...")
    found_stocks = search_for_stocks(search_terms, limit_per_term=10)

    # Remove duplicates by stock_id
    unique_stocks = {}
    for stock in found_stocks:
        stock_id = stock.get('k')
        if stock_id and stock_id not in unique_stocks:
            unique_stocks[stock_id] = stock

    print(f"Found {len(unique_stocks)} unique stocks")

    # Step 2: Extract tokens for each stock
    print(f"\n2. Extracting tokens from equity pages...")
    discovery = StockDiscovery()

    success_count = 0
    failed_count = 0

    for i, (stock_id, stock) in enumerate(unique_stocks.items()):
        try:
            equity_url = stock['equity_url']
            symbol = stock.get('value', 'UNKNOWN')

            print(f"[{i+1}/{len(unique_stocks)}] Processing {symbol} (ID: {stock_id})")

            if discovery.extract_and_store_stock(equity_url):
                success_count += 1
                print(f"  ✅ Success")
            else:
                failed_count += 1
                print(f"  ❌ Failed")

            time.sleep(1)  # Be respectful

        except Exception as e:
            print(f"  💥 Error: {e}")
            failed_count += 1

    print(f"\nExtraction complete:")
    print(f"  Success: {success_count}")
    print(f"  Failed: {failed_count}")

    # Step 3: Test all tokens
    print(f"\n3. Testing all discovered tokens...")
    discovery.test_all_tokens()

    # Step 4: Show final results
    stocks = discovery.db.get_all_stocks()
    working_stocks = [s for s in stocks if s['token_status'] == 'working']

    print(f"\n=== FINAL RESULTS ===")
    print(f"Total stocks in database: {len(stocks)}")
    print(f"Stocks with working tokens: {len(working_stocks)}")
    print(f"Success rate: {len(working_stocks)/len(stocks)*100:.1f}%")

    print(f"\n🎉 WORKING STOCKS:")
    for stock in working_stocks:
        print(f"  ✅ {stock['symbol']} (ID: {stock['stock_id']}) - {stock['company_name']}")

    return working_stocks

if __name__ == "__main__":
    working_stocks = run_mass_discovery()

    print(f"\n🚀 DISCOVERY COMPLETE!")
    print(f"Ready for AI analysis with {len(working_stocks)} stocks!")
    print("Each stock now has both OHLC and Fundamentals API access.")