#!/usr/bin/env python3
"""
Trendlyne API Analysis Tool
Analyzes and interacts with Trendlyne's API endpoints based on reverse engineering.
"""

import requests
import json
from urllib.parse import urlparse, parse_qs
import re

class TrendlyneAPI:
    """Class to interact with Trendlyne API endpoints"""

    def __init__(self):
        self.base_url = "https://trendlyne.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'DNT': '1',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'X-Requested-With': 'XMLHttpRequest'
        })

    def analyze_ohlc_endpoint(self, stock_id, token):
        """
        Analyze OHLC (Open, High, Low, Close) data endpoint

        Args:
            stock_id: Stock ID (e.g., 1577)
            token: Authentication token (e.g., RKDTEX74CDGD62YUGULP4UKK5Q======)
        """
        endpoint = f"/mapp/v1/stock/web/ohlc/{stock_id}/{token}/"
        url = self.base_url + endpoint

        try:
            response = self.session.get(url)
            return {
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'data': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            }
        except Exception as e:
            return {'error': str(e)}

    def extract_stock_info_from_url(self, equity_url):
        """
        Extract stock information from equity URL
        Pattern: /equity/{stock_id}/{symbol}/{company_name}/

        Args:
            equity_url: Full equity URL or path
        """
        # Extract pattern: /equity/1577/MOLDTKPAC/mold-tek-packaging-ltd/
        pattern = r'/equity/(\d+)/([A-Z]+)/([^/]+)/?'
        match = re.search(pattern, equity_url)

        if match:
            return {
                'stock_id': match.group(1),
                'symbol': match.group(2),
                'company_slug': match.group(3)
            }
        return None

def analyze_api_structure():
    """Analyze the API structure from the provided example"""

    example_data = {
        'request': {
            'url': 'https://trendlyne.com/mapp/v1/stock/web/ohlc/1577/RKDTEX74CDGD62YUGULP4UKK5Q======/',
            'method': 'GET',
            'headers': {
                'authority': 'trendlyne.com',
                'method': 'GET',
                'path': '/mapp/v1/stock/web/ohlc/1577/RKDTEX74CDGD62YUGULP4UKK5Q======/',
                'scheme': 'https',
                'accept': '*/*',
                'content-type': 'application/json',
                'x-requested-with': 'XMLHttpRequest',
                'referer': 'https://trendlyne.com/equity/1577/MOLDTKPAC/mold-tek-packaging-ltd/'
            }
        },
        'response': {
            'status': 200,
            'headers': {
                'content-type': 'application/json',
                'content-encoding': 'gzip',
                'server': 'CloudFront',
                'x-cache': 'Miss from cloudfront'
            }
        }
    }

    print("=== Trendlyne API Analysis ===")
    print(f"Base URL: {urlparse(example_data['request']['url']).netloc}")
    print(f"API Version: v1")
    print(f"Endpoint Pattern: /mapp/v1/stock/web/ohlc/{'{stock_id}'}/{'{token}'}/")
    print(f"Method: {example_data['request']['method']}")
    print(f"Content-Type: {example_data['response']['headers']['content-type']}")
    print(f"Authentication: Token-based (in URL path)")

    # Extract components
    url_path = example_data['request']['path']
    path_parts = url_path.strip('/').split('/')

    print(f"\nURL Structure:")
    print(f"  - API Base: /mapp/v1/stock/web/")
    print(f"  - Data Type: {path_parts[4]} (ohlc)")
    print(f"  - Stock ID: {path_parts[5]} (1577)")
    print(f"  - Auth Token: {path_parts[6]} (RKDTEX74CDGD62YUGULP4UKK5Q======)")

    print(f"\nReferer Pattern:")
    referer = example_data['request']['headers']['referer']
    print(f"  - {referer}")
    print(f"  - Pattern: /equity/{'{stock_id}'}/{'{symbol}'}/{'{company-slug}'}/")

if __name__ == "__main__":
    analyze_api_structure()

    # Example usage
    api = TrendlyneAPI()

    # Extract stock info from equity URL
    equity_url = "https://trendlyne.com/equity/1577/MOLDTKPAC/mold-tek-packaging-ltd/"
    stock_info = api.extract_stock_info_from_url(equity_url)

    if stock_info:
        print(f"\nExtracted Stock Info:")
        print(f"  Stock ID: {stock_info['stock_id']}")
        print(f"  Symbol: {stock_info['symbol']}")
        print(f"  Company: {stock_info['company_slug']}")