#!/usr/bin/env python3
"""
Token Updater Script - Refresh all Trendlyne tokens in the database
Updates expired tokens with fresh ones extracted from equity pages
"""

import sqlite3
import requests
import re
import time
import json
import logging
from datetime import datetime
from urllib.parse import quote
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('token_update.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TokenUpdater:
    def __init__(self, db_path='indian_stocks_db/indian_stocks.db'):
        self.db_path = db_path
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

        # Statistics
        self.stats = {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': datetime.now()
        }

    def get_companies_to_update(self, limit=None, status_filter=None):
        """Get companies that need token updates"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Base query
        query = '''
            SELECT id, symbol, company_name, trendlyne_stock_id, trendlyne_equity_url,
                   token_status, trendlyne_auth_token
            FROM companies
            WHERE trendlyne_stock_id IS NOT NULL
        '''
        params = []

        # Add status filter if specified
        if status_filter:
            query += ' AND token_status = ?'
            params.append(status_filter)

        # Add ordering and limit
        query += ' ORDER BY id'
        if limit:
            query += ' LIMIT ?'
            params.append(limit)

        cursor.execute(query, params)
        companies = cursor.fetchall()
        conn.close()

        return companies

    def extract_token_from_equity_page(self, equity_url, stock_id):
        """Extract fresh token from equity page"""
        try:
            logger.debug(f"Fetching equity page: {equity_url}")
            response = self.session.get(equity_url, timeout=15)

            if response.status_code != 200:
                logger.warning(f"HTTP {response.status_code} for {equity_url}")
                return None

            html = response.text

            # Method 1: Look for OHLC API calls in JavaScript
            ohlc_pattern = r'/mapp/v1/stock/web/ohlc/(\d+)/([A-Z0-9+=]+)/'
            ohlc_matches = re.findall(ohlc_pattern, html)

            if ohlc_matches:
                for match_stock_id, token in ohlc_matches:
                    if match_stock_id == str(stock_id):
                        logger.debug(f"Found token via OHLC pattern: {token[:20]}...")
                        return token

            # Method 2: Look for any token patterns in the page
            token_pattern = r'([A-Z0-9]{20,32}={0,6})'
            token_candidates = re.findall(token_pattern, html)

            # Filter for likely auth tokens (proper length and format)
            for candidate in token_candidates:
                if len(candidate) >= 30 and candidate.endswith('='):
                    # Verify it's not a CSRF token or other random string
                    if candidate not in html[:1000]:  # Not in header
                        logger.debug(f"Found candidate token: {candidate[:20]}...")
                        return candidate

            logger.warning(f"No token found in equity page: {equity_url}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {equity_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error extracting token: {e}")
            return None

    def test_token(self, stock_id, token, symbol):
        """Test if a token works for both OHLC and fundamentals"""
        base_url = "https://trendlyne.com"
        referer = f"https://trendlyne.com/equity/{stock_id}/{symbol}/test/"

        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': referer,
            'DNT': '1',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }

        results = {'ohlc': False, 'fundamentals': False}

        # Test OHLC
        try:
            ohlc_url = f"{base_url}/mapp/v1/stock/web/ohlc/{stock_id}/{token}/"
            response = requests.get(ohlc_url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results['ohlc'] = bool(data.get('body', {}).get('liveData'))
        except Exception as e:
            logger.debug(f"OHLC test error: {e}")

        # Test Fundamentals
        try:
            fund_url = f"{base_url}/fundamentals/get-fundamental_results-v2/{stock_id}/{token}/"
            response = requests.get(fund_url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                results['fundamentals'] = bool(data.get('body'))
        except Exception as e:
            logger.debug(f"Fundamentals test error: {e}")

        return results

    def update_company_token(self, company_id, stock_id, symbol, equity_url, old_token):
        """Update token for a single company"""

        # Build equity URL if missing
        if not equity_url or not equity_url.startswith('http'):
            # Try to construct from available data
            company_slug = symbol.lower().replace(' ', '-')
            equity_url = f"https://trendlyne.com/equity/{stock_id}/{symbol}/{company_slug}/"

        # Extract fresh token
        new_token = self.extract_token_from_equity_page(equity_url, stock_id)

        if not new_token:
            return {'success': False, 'reason': 'token_extraction_failed'}

        # Skip if token hasn't changed
        if new_token == old_token:
            logger.debug(f"Token unchanged for {symbol}")
            return {'success': True, 'reason': 'token_unchanged', 'token': new_token}

        # Test the new token
        test_results = self.test_token(stock_id, new_token, symbol)

        token_works = test_results['ohlc'] or test_results['fundamentals']
        status = 'working' if token_works else 'failed'

        # Update database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE companies
            SET trendlyne_auth_token = ?,
                token_status = ?,
                token_discovered_date = ?,
                token_last_tested = ?,
                last_updated = ?,
                trendlyne_equity_url = ?
            WHERE id = ?
        ''', (new_token, status, datetime.now(), datetime.now(), datetime.now(), equity_url, company_id))

        conn.commit()
        conn.close()

        return {
            'success': True,
            'reason': 'updated',
            'token': new_token,
            'status': status,
            'test_results': test_results
        }

    def update_all_tokens(self, limit=None, status_filter='working', delay=2.0):
        """Update tokens for all companies"""

        logger.info(f"Starting token update process...")
        logger.info(f"Limit: {limit}, Status filter: {status_filter}, Delay: {delay}s")

        companies = self.get_companies_to_update(limit=limit, status_filter=status_filter)
        total = len(companies)

        logger.info(f"Found {total} companies to process")

        for i, (company_id, symbol, company_name, stock_id, equity_url, old_status, old_token) in enumerate(companies):

            self.stats['processed'] += 1

            logger.info(f"[{i+1}/{total}] Processing {symbol} - {company_name[:40]}")
            logger.info(f"  Stock ID: {stock_id}, Old Status: {old_status}")

            try:
                result = self.update_company_token(
                    company_id, stock_id, symbol, equity_url, old_token
                )

                if result['success']:
                    if result['reason'] == 'updated':
                        self.stats['success'] += 1
                        test_info = result['test_results']
                        logger.info(f"  ✅ Updated - Status: {result['status']}, OHLC: {test_info['ohlc']}, Fund: {test_info['fundamentals']}")
                    else:
                        self.stats['skipped'] += 1
                        logger.info(f"  ⏭️  {result['reason']}")
                else:
                    self.stats['failed'] += 1
                    logger.warning(f"  ❌ Failed - {result['reason']}")

            except Exception as e:
                self.stats['failed'] += 1
                logger.error(f"  💥 Exception: {e}")

            # Progress update
            if (i + 1) % 10 == 0:
                self.log_progress()

            # Rate limiting
            if i < total - 1:  # Don't delay on last item
                time.sleep(delay)

        self.log_final_stats()

    def log_progress(self):
        """Log current progress statistics"""
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
        rate = self.stats['processed'] / elapsed if elapsed > 0 else 0

        logger.info(f"Progress - Processed: {self.stats['processed']}, "
                   f"Success: {self.stats['success']}, "
                   f"Failed: {self.stats['failed']}, "
                   f"Rate: {rate:.1f}/min")

    def log_final_stats(self):
        """Log final statistics"""
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()

        logger.info("=== TOKEN UPDATE COMPLETE ===")
        logger.info(f"Total Processed: {self.stats['processed']}")
        logger.info(f"Successful Updates: {self.stats['success']}")
        logger.info(f"Failed Updates: {self.stats['failed']}")
        logger.info(f"Skipped: {self.stats['skipped']}")
        logger.info(f"Total Time: {elapsed/60:.1f} minutes")
        logger.info(f"Average Rate: {self.stats['processed']/(elapsed/60):.1f} companies/minute")

        success_rate = (self.stats['success'] / self.stats['processed'] * 100) if self.stats['processed'] > 0 else 0
        logger.info(f"Success Rate: {success_rate:.1f}%")

def main():
    updater = TokenUpdater()

    # Start with a small test batch
    print("Token Updater - Trendlyne Database Refresh")
    print("==========================================")

    mode = input("Choose mode:\n1. Test (5 companies)\n2. Small batch (50 companies)\n3. All companies\nEnter choice (1-3): ").strip()

    if mode == "1":
        limit = 5
        delay = 1.0
    elif mode == "2":
        limit = 50
        delay = 2.0
    else:
        limit = None
        delay = 3.0
        confirm = input("This will update ALL companies. Are you sure? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("Operation cancelled.")
            return

    # Update tokens
    updater.update_all_tokens(limit=limit, delay=delay)

    print("\nToken update complete! Check token_update.log for details.")

if __name__ == "__main__":
    main()