#!/usr/bin/env python3
"""
Trendlyne Stock Discovery System
Discovers stock listings and builds a database of stock_id/auth_token pairs
"""

import requests
import sqlite3
import json
import time
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from token_extractor import TrendlyneTokenExtractor

class StockDatabase:
    def __init__(self, db_path="trendlyne_stocks.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Stocks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id TEXT UNIQUE NOT NULL,
                symbol TEXT,
                company_name TEXT,
                company_slug TEXT,
                exchange TEXT,
                equity_url TEXT,
                auth_token TEXT,
                token_discovered_at TIMESTAMP,
                token_last_tested TIMESTAMP,
                token_status TEXT DEFAULT 'unknown',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Discovery log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS discovery_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT,
                target_url TEXT,
                result TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def add_stock(self, stock_data):
        """Add or update stock information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO stocks
            (stock_id, symbol, company_name, company_slug, exchange, equity_url,
             auth_token, token_discovered_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            stock_data.get('stock_id'),
            stock_data.get('symbol'),
            stock_data.get('company_name'),
            stock_data.get('company_slug'),
            stock_data.get('exchange'),
            stock_data.get('equity_url'),
            stock_data.get('auth_token'),
            datetime.now() if stock_data.get('auth_token') else None,
            datetime.now()
        ))

        conn.commit()
        conn.close()

    def update_token_status(self, stock_id, status):
        """Update token testing status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE stocks
            SET token_status = ?, token_last_tested = ?
            WHERE stock_id = ?
        ''', (status, datetime.now(), stock_id))

        conn.commit()
        conn.close()

    def get_all_stocks(self):
        """Get all stocks from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM stocks ORDER BY created_at DESC')
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()

        conn.close()
        return [dict(zip(columns, row)) for row in rows]

    def log_discovery(self, action, target_url, result):
        """Log discovery action"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO discovery_log (action, target_url, result)
            VALUES (?, ?, ?)
        ''', (action, target_url, result))

        conn.commit()
        conn.close()

class StockDiscovery:
    def __init__(self):
        self.extractor = TrendlyneTokenExtractor()
        self.db = StockDatabase()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36'
        })

    def parse_equity_url(self, equity_url):
        """Parse equity URL to extract stock information"""
        # Pattern: /equity/{stock_id}/{symbol}/{company_slug}/
        pattern = r'/equity/(\d+)/([A-Z0-9]+)/([^/]+)/?'
        match = re.search(pattern, equity_url)

        if match:
            return {
                'stock_id': match.group(1),
                'symbol': match.group(2),
                'company_slug': match.group(3),
                'company_name': match.group(3).replace('-', ' ').title(),
                'equity_url': equity_url
            }
        return None

    def discover_from_search(self, query="", limit=50):
        """Discover stocks from Trendlyne search"""
        search_url = "https://trendlyne.com/search/"

        try:
            response = self.session.get(search_url, params={'q': query})
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            equity_links = []

            # Find all equity links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/equity/' in href and re.search(r'/equity/\d+/', href):
                    full_url = urljoin("https://trendlyne.com", href)
                    equity_links.append(full_url)

            return list(set(equity_links))[:limit]

        except Exception as e:
            self.db.log_discovery("search_discovery", search_url, f"Error: {e}")
            return []

    def discover_from_listings(self, limit=100):
        """Discover stocks from various listing pages"""
        listing_urls = [
            "https://trendlyne.com/markets/india/equity-stocks/",
            "https://trendlyne.com/markets/nse/",
            "https://trendlyne.com/markets/bse/",
            "https://trendlyne.com/watchlist/stocks/"
        ]

        all_equity_urls = []

        for listing_url in listing_urls:
            try:
                print(f"Discovering from: {listing_url}")
                response = self.session.get(listing_url)

                if response.status_code == 200:
                    # Find equity URLs in the page
                    equity_pattern = r'href=["\']([^"\']*?/equity/\d+/[^"\']*?)["\']'
                    matches = re.findall(equity_pattern, response.text)

                    for match in matches:
                        full_url = urljoin("https://trendlyne.com", match)
                        all_equity_urls.append(full_url)

                    self.db.log_discovery("listing_discovery", listing_url, f"Found {len(matches)} equity URLs")

                else:
                    self.db.log_discovery("listing_discovery", listing_url, f"HTTP {response.status_code}")

                time.sleep(1)  # Be respectful

            except Exception as e:
                self.db.log_discovery("listing_discovery", listing_url, f"Error: {e}")

        return list(set(all_equity_urls))[:limit]

    def extract_and_store_stock(self, equity_url):
        """Extract stock info and token, then store in database"""
        try:
            # Parse basic info from URL
            stock_info = self.parse_equity_url(equity_url)
            if not stock_info:
                return False

            print(f"Processing: {stock_info['symbol']} ({stock_info['stock_id']})")

            # Extract auth token
            extraction_result = self.extractor.extract_from_equity_page(equity_url)

            if extraction_result.get('extracted_auth_token'):
                stock_info['auth_token'] = extraction_result['extracted_auth_token']
                stock_info['exchange'] = 'NSE'  # Default assumption

            # Store in database
            self.db.add_stock(stock_info)
            self.db.log_discovery("token_extraction", equity_url,
                                f"Stock ID: {stock_info['stock_id']}, Token: {'Found' if stock_info.get('auth_token') else 'Not found'}")

            return True

        except Exception as e:
            self.db.log_discovery("token_extraction", equity_url, f"Error: {e}")
            return False

    def test_all_tokens(self):
        """Test all stored auth tokens"""
        stocks = self.db.get_all_stocks()

        for stock in stocks:
            if stock['auth_token']:
                try:
                    test_url = f"https://trendlyne.com/mapp/v1/stock/web/ohlc/{stock['stock_id']}/{stock['auth_token']}/"

                    response = self.session.get(test_url, headers={
                        'X-Requested-With': 'XMLHttpRequest',
                        'Referer': stock['equity_url']
                    })

                    status = "working" if response.status_code == 200 else f"failed_{response.status_code}"
                    self.db.update_token_status(stock['stock_id'], status)

                    print(f"Token test {stock['symbol']}: {status}")
                    time.sleep(0.5)  # Rate limiting

                except Exception as e:
                    self.db.update_token_status(stock['stock_id'], f"error_{e}")

def run_discovery():
    """Run stock discovery process"""
    discovery = StockDiscovery()

    print("=== TRENDLYNE STOCK DISCOVERY ===")

    # Step 1: Discover equity URLs
    print("\n1. Discovering stock listings...")
    equity_urls = discovery.discover_from_listings(limit=20)  # Start small
    print(f"Found {len(equity_urls)} equity URLs")

    # Step 2: Extract tokens for each stock
    print("\n2. Extracting tokens...")
    success_count = 0
    for url in equity_urls[:10]:  # Process first 10
        if discovery.extract_and_store_stock(url):
            success_count += 1
        time.sleep(1)  # Be respectful

    print(f"Successfully processed {success_count}/{len(equity_urls[:10])} stocks")

    # Step 3: Test all tokens
    print("\n3. Testing tokens...")
    discovery.test_all_tokens()

    # Step 4: Show results
    print("\n4. Results:")
    stocks = discovery.db.get_all_stocks()
    working_tokens = [s for s in stocks if s['token_status'] == 'working']

    print(f"Total stocks: {len(stocks)}")
    print(f"Working tokens: {len(working_tokens)}")

    print("\nWorking stocks:")
    for stock in working_tokens:
        print(f"  {stock['symbol']} (ID: {stock['stock_id']}) - {stock['company_name']}")

if __name__ == "__main__":
    run_discovery()