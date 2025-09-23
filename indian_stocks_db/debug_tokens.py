#!/usr/bin/env python3
"""
Debug token extraction and testing
"""

import requests
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')
from token_extractor import TrendlyneTokenExtractor

def debug_token_extraction():
    """Debug token extraction for one Aviation company"""

    # Test with SpiceJet
    test_url = "https://trendlyne.com/equity/2064/SPICEJET/spicejet-ltd/"

    print("=== DEBUG TOKEN EXTRACTION ===")
    print(f"Testing URL: {test_url}")

    extractor = TrendlyneTokenExtractor()

    # Extract token
    result = extractor.extract_from_equity_page(test_url)

    print(f"\nExtraction result:")
    print(f"Stock ID: {result.get('stock_id')}")
    print(f"Auth Token: {result.get('extracted_auth_token')}")

    if result.get('extracted_auth_token'):
        stock_id = result['stock_id']
        auth_token = result['extracted_auth_token']

        # Test the token manually
        print(f"\n=== MANUAL TOKEN TEST ===")
        api_url = f"https://trendlyne.com/mapp/v1/stock/web/ohlc/{stock_id}/{auth_token}/"

        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...',
            'Accept': '*/*',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': test_url
        }

        print(f"API URL: {api_url}")

        response = requests.get(api_url, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")

        if response.status_code == 200:
            print("✅ Token works!")
            try:
                data = response.json()
                print(f"Response keys: {list(data.keys())}")
            except:
                print("Non-JSON response")
        else:
            print(f"❌ Token failed: {response.status_code}")
            print(f"Response: {response.text[:200]}")

    else:
        print("❌ No token extracted")

if __name__ == "__main__":
    debug_token_extraction()