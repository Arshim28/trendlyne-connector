#!/usr/bin/env python3
"""
Trendlyne Integration for Indian Stocks Database
Start with smallest sector (Aviation - 8 companies) for testing
"""

import requests
import sqlite3
import json
import time
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')
from token_extractor import TrendlyneTokenExtractor

class TrendlyneIntegrator:
    def __init__(self, db_path="indian_stocks.db"):
        self.db_path = db_path
        self.extractor = TrendlyneTokenExtractor()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...',
            'Accept': '*/*',
            'X-Requested-With': 'XMLHttpRequest'
        })

    def get_sector_companies(self, sector_name, limit=None):
        """Get companies from a specific sector"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = '''
            SELECT id, company_name, exchange, symbol, zerodha_url
            FROM companies
            WHERE sector_name = ? AND token_status = 'pending'
            ORDER BY company_name
        '''

        if limit:
            query += f' LIMIT {limit}'

        cursor.execute(query, (sector_name,))
        companies = cursor.fetchall()
        conn.close()

        return [{'id': row[0], 'name': row[1], 'exchange': row[2],
                'symbol': row[3], 'zerodha_url': row[4]} for row in companies]

    def search_trendlyne_for_company(self, company):
        """Search Trendlyne for a specific company"""
        search_url = "https://trendlyne.com/member/api/ac_snames/all/"

        # Try different search terms
        search_terms = [
            company['symbol'],  # Exchange symbol
            company['name'],    # Company name
            company['name'].split()[0]  # First word of company name
        ]

        for term in search_terms:
            try:
                params = {'term': term, 'all-results': 'true'}
                response = self.session.get(search_url, params=params)

                if response.status_code == 200:
                    results = response.json()

                    # Look for exact or close matches
                    for result in results:
                        if (result.get('category') == 'Equity' and
                            result.get('country') == 'IND' and
                            'urls' in result and result['urls']):

                            # Check if this matches our company
                            trendlyne_symbol = result.get('value', '')

                            # Exact symbol match is best
                            if trendlyne_symbol == company['symbol']:
                                return result

                            # Partial match in company name
                            if (term.lower() in result.get('label', '').lower() or
                                company['name'].lower() in result.get('label', '').lower()):
                                return result

                time.sleep(0.3)  # Rate limiting between search terms

            except Exception as e:
                print(f"    Search error for '{term}': {e}")

        return None

    def extract_token_from_equity_url(self, equity_url):
        """Extract auth token from Trendlyne equity URL"""
        try:
            result = self.extractor.extract_from_equity_page(equity_url)

            if result.get('extracted_auth_token') and result.get('stock_id'):
                return {
                    'stock_id': result['stock_id'],
                    'auth_token': result['extracted_auth_token'],
                    'equity_url': equity_url
                }
        except Exception as e:
            print(f"    Token extraction error: {e}")

        return None

    def test_token(self, stock_id, auth_token, equity_url):
        """Test if a Trendlyne token works"""
        test_url = f"https://trendlyne.com/mapp/v1/stock/web/ohlc/{stock_id}/{auth_token}/"

        try:
            response = self.session.get(test_url, headers={
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': equity_url
            })
            return response.status_code == 200
        except:
            return False

    def update_company_trendlyne_data(self, company_id, trendlyne_data, status):
        """Update company with Trendlyne data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if trendlyne_data:
            cursor.execute('''
                UPDATE companies SET
                    trendlyne_stock_id = ?,
                    trendlyne_auth_token = ?,
                    trendlyne_equity_url = ?,
                    token_status = ?,
                    token_discovered_date = ?,
                    last_updated = ?
                WHERE id = ?
            ''', (
                trendlyne_data.get('stock_id'),
                trendlyne_data.get('auth_token'),
                trendlyne_data.get('equity_url'),
                status,
                datetime.now(),
                datetime.now(),
                company_id
            ))
        else:
            cursor.execute('''
                UPDATE companies SET
                    token_status = ?,
                    last_updated = ?
                WHERE id = ?
            ''', (status, datetime.now(), company_id))

        conn.commit()
        conn.close()

    def integrate_sector(self, sector_name):
        """Integrate Trendlyne data for entire sector"""
        print(f"=== TRENDLYNE INTEGRATION: {sector_name.upper()} ===")

        companies = self.get_sector_companies(sector_name)
        print(f"Found {len(companies)} companies to process")

        success_count = 0
        not_found_count = 0
        error_count = 0

        for i, company in enumerate(companies):
            print(f"\n[{i+1}/{len(companies)}] Processing: {company['name']} ({company['symbol']})")

            try:
                # Step 1: Search Trendlyne
                print(f"  🔍 Searching Trendlyne...")
                search_result = self.search_trendlyne_for_company(company)

                if not search_result:
                    print(f"  ❌ Not found on Trendlyne")
                    self.update_company_trendlyne_data(company['id'], None, 'not_found')
                    not_found_count += 1
                    continue

                # Step 2: Extract token from equity URL
                equity_url = search_result['urls'][0][1]  # First URL is Overview
                print(f"  🎯 Found: {equity_url}")

                token_data = self.extract_token_from_equity_url(equity_url)

                if not token_data:
                    print(f"  ❌ Failed to extract token")
                    self.update_company_trendlyne_data(company['id'], None, 'failed')
                    error_count += 1
                    continue

                # Step 3: Test token
                print(f"  🧪 Testing token...")
                if self.test_token(token_data['stock_id'], token_data['auth_token'], equity_url):
                    print(f"  ✅ SUCCESS! Token works")
                    self.update_company_trendlyne_data(company['id'], token_data, 'working')
                    success_count += 1
                else:
                    print(f"  ❌ Token test failed")
                    self.update_company_trendlyne_data(company['id'], token_data, 'failed')
                    error_count += 1

                time.sleep(1.5)  # Rate limiting

            except Exception as e:
                print(f"  💥 Error: {e}")
                self.update_company_trendlyne_data(company['id'], None, 'error')
                error_count += 1

        print(f"\n=== {sector_name.upper()} INTEGRATION COMPLETE ===")
        print(f"✅ Success: {success_count}")
        print(f"❌ Not found: {not_found_count}")
        print(f"💥 Errors: {error_count}")
        print(f"📊 Success rate: {success_count/len(companies)*100:.1f}%")

        return success_count, not_found_count, error_count

    def show_sector_results(self, sector_name):
        """Show results for a sector"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT company_name, exchange, symbol, trendlyne_stock_id,
                   trendlyne_auth_token, token_status
            FROM companies
            WHERE sector_name = ?
            ORDER BY token_status, company_name
        ''', (sector_name,))

        results = cursor.fetchall()
        conn.close()

        print(f"\n=== {sector_name.upper()} RESULTS ===")

        working = [r for r in results if r[5] == 'working']
        not_found = [r for r in results if r[5] == 'not_found']
        failed = [r for r in results if r[5] == 'failed']

        print(f"\n✅ WORKING ({len(working)}):")
        for result in working:
            print(f"  {result[0]} ({result[2]}) - ID: {result[3]}")

        print(f"\n❌ NOT FOUND ({len(not_found)}):")
        for result in not_found:
            print(f"  {result[0]} ({result[2]})")

        print(f"\n💥 FAILED ({len(failed)}):")
        for result in failed:
            print(f"  {result[0]} ({result[2]})")

def main():
    integrator = TrendlyneIntegrator()

    # Start with Aviation sector (8 companies)
    sector_name = "Aviation"

    # Run integration
    success, not_found, errors = integrator.integrate_sector(sector_name)

    # Show detailed results
    integrator.show_sector_results(sector_name)

    print(f"\n🎯 Ready to scale to larger sectors!")

if __name__ == "__main__":
    main()