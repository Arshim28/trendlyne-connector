#!/usr/bin/env python3
"""
Analyze Zerodha sectors page to understand the structure
"""

import requests
from bs4 import BeautifulSoup
import json

def analyze_zerodha_sectors():
    """Fetch and analyze Zerodha sectors page"""

    url = "https://zerodha.com/markets/sector/"

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
        'DNT': '1',
        'Upgrade-Insecure-Requests': '1'
    }

    print("=== ZERODHA SECTORS ANALYSIS ===")
    print(f"Fetching: {url}")

    try:
        response = requests.get(url, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        print(f"Content-Length: {len(response.text)}")

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')

            print("\n=== PAGE STRUCTURE ANALYSIS ===")

            # Look for sector links
            sector_links = []

            # Common patterns for sector links
            patterns = [
                'a[href*="/sector/"]',
                'a[href*="/markets/sector/"]',
                '.sector-link',
                '.sector-item',
                '[data-sector]'
            ]

            for pattern in patterns:
                elements = soup.select(pattern)
                if elements:
                    print(f"Found {len(elements)} elements matching '{pattern}'")
                    for elem in elements[:3]:  # Show first 3
                        print(f"  - {elem.get_text(strip=True)} -> {elem.get('href', 'No href')}")

            # Look for any sector-related content
            print(f"\n=== TEXT CONTENT ANALYSIS ===")
            text = response.text.lower()

            sector_keywords = ['banking', 'pharma', 'it', 'auto', 'metal', 'oil', 'fmcg', 'telecom']
            for keyword in sector_keywords:
                count = text.count(keyword)
                if count > 0:
                    print(f"'{keyword}': {count} occurrences")

            # Look for any data in script tags
            scripts = soup.find_all('script')
            print(f"\nFound {len(scripts)} script tags")

            for i, script in enumerate(scripts):
                if script.string and ('sector' in script.string.lower() or 'market' in script.string.lower()):
                    print(f"  Script {i+1} contains relevant data (length: {len(script.string)})")
                    if len(script.string) < 500:
                        print(f"    Content preview: {script.string[:200]}...")

            # Save the HTML for manual inspection
            with open('zerodha_sectors.html', 'w') as f:
                f.write(response.text)
            print(f"\n💾 Saved HTML to zerodha_sectors.html for manual inspection")

        else:
            print(f"Failed to fetch: {response.status_code}")
            print(f"Response: {response.text[:200]}...")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_zerodha_sectors()