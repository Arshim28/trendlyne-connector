#!/usr/bin/env python3
"""
Trendlyne Token Extractor
Extracts stock_id and auth_token pairs from equity pages
"""

import requests
import re
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

class TrendlyneTokenExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

    def extract_from_equity_page(self, equity_url):
        """
        Extract stock_id and auth_token from an equity page

        Args:
            equity_url: URL like https://trendlyne.com/equity/1577/MOLDTKPAC/mold-tek-packaging-ltd/
        """
        try:
            print(f"Fetching: {equity_url}")
            response = self.session.get(equity_url)

            if response.status_code != 200:
                return {"error": f"HTTP {response.status_code}"}

            html = response.text

            # Extract stock_id from URL
            stock_id_match = re.search(r'/equity/(\d+)/', equity_url)
            stock_id = stock_id_match.group(1) if stock_id_match else None

            # Method 1: Look for OHLC API calls in JavaScript
            ohlc_pattern = r'/mapp/v1/stock/web/ohlc/(\d+)/([A-Z0-9+=]+)/'
            ohlc_matches = re.findall(ohlc_pattern, html)

            # Method 2: Look for embedded data or config
            config_patterns = [
                r'stockId["\']?\s*[:=]\s*["\']?(\d+)',
                r'stock_id["\']?\s*[:=]\s*["\']?(\d+)',
                r'authToken["\']?\s*[:=]\s*["\']?([A-Z0-9+=]+)',
                r'auth_token["\']?\s*[:=]\s*["\']?([A-Z0-9+=]+)',
                r'token["\']?\s*[:=]\s*["\']?([A-Z0-9+=]+)'
            ]

            found_tokens = []
            found_stock_ids = []

            for pattern in config_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if 'token' in pattern.lower():
                    found_tokens.extend(matches)
                else:
                    found_stock_ids.extend(matches)

            # Method 3: Look for data attributes
            soup = BeautifulSoup(html, 'html.parser')
            data_elements = soup.find_all(attrs={"data-stock-id": True})
            data_tokens = soup.find_all(attrs={"data-token": True})

            result = {
                "equity_url": equity_url,
                "stock_id": stock_id,
                "extraction_methods": {
                    "ohlc_api_calls": ohlc_matches,
                    "js_config_stock_ids": list(set(found_stock_ids)),
                    "js_config_tokens": list(set(found_tokens)),
                    "data_attributes": {
                        "stock_ids": [elem.get('data-stock-id') for elem in data_elements],
                        "tokens": [elem.get('data-token') for elem in data_tokens]
                    }
                }
            }

            # Try to find the most likely auth_token
            auth_token = None
            if ohlc_matches:
                auth_token = ohlc_matches[0][1]  # First OHLC match
            elif found_tokens:
                # Filter tokens that look like auth tokens (longer, with padding)
                auth_candidates = [t for t in found_tokens if len(t) > 20 and '=' in t]
                auth_token = auth_candidates[0] if auth_candidates else found_tokens[0]

            result["extracted_auth_token"] = auth_token

            return result

        except Exception as e:
            return {"error": str(e)}

    def find_stock_listings(self, base_url="https://trendlyne.com"):
        """
        Find stock listing pages to discover more equity URLs
        """
        try:
            # Common listing pages
            listing_paths = [
                "/stocks/",
                "/equity/",
                "/nse/",
                "/bse/",
                "/browse/",
                "/screener/"
            ]

            found_equity_urls = []

            for path in listing_paths:
                try:
                    url = urljoin(base_url, path)
                    print(f"Checking: {url}")

                    response = self.session.get(url)
                    if response.status_code == 200:
                        # Find equity URLs in the page
                        equity_pattern = r'href=["\']([^"\']*?/equity/\d+/[^"\']*?)["\']'
                        matches = re.findall(equity_pattern, response.text)

                        for match in matches:
                            full_url = urljoin(base_url, match)
                            found_equity_urls.append(full_url)

                except Exception as e:
                    print(f"Error checking {path}: {e}")

            return list(set(found_equity_urls))  # Remove duplicates

        except Exception as e:
            return {"error": str(e)}

def test_token_extraction():
    """Test the token extraction with known working example"""
    extractor = TrendlyneTokenExtractor()

    test_url = "https://trendlyne.com/equity/1577/MOLDTKPAC/mold-tek-packaging-ltd/"
    result = extractor.extract_from_equity_page(test_url)

    print("=== TOKEN EXTRACTION TEST ===")
    print(json.dumps(result, indent=2))

    # Verify if extracted token works
    if result.get("extracted_auth_token") and result.get("stock_id"):
        print("\n=== TESTING EXTRACTED TOKEN ===")
        test_url = f"https://trendlyne.com/mapp/v1/stock/web/ohlc/{result['stock_id']}/{result['extracted_auth_token']}/"

        response = requests.get(test_url, headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...',
            'X-Requested-With': 'XMLHttpRequest'
        })

        print(f"API Test Result: {response.status_code}")
        if response.status_code == 200:
            print("✅ Extracted token WORKS!")
        else:
            print("❌ Extracted token failed")

if __name__ == "__main__":
    test_token_extraction()