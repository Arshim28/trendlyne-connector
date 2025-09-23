#!/usr/bin/env python3
"""
Interactive Sector Scraper for Indian Stocks Database
Allows user to choose which sector to integrate with Trendlyne
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

class InteractiveSectorScraper:
    def __init__(self, db_path="indian_stocks.db"):
        self.db_path = db_path
        self.extractor = TrendlyneTokenExtractor()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...',
            'Accept': '*/*',
            'X-Requested-With': 'XMLHttpRequest'
        })

    def get_all_sectors(self):
        """Get all sectors from database with their stats"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                s.sector_name,
                s.company_count,
                COUNT(CASE WHEN c.token_status = 'working' THEN 1 END) as working_count,
                COUNT(CASE WHEN c.token_status = 'pending' THEN 1 END) as pending_count,
                COUNT(CASE WHEN c.token_status = 'failed' THEN 1 END) as failed_count,
                COUNT(CASE WHEN c.token_status = 'not_found' THEN 1 END) as not_found_count
            FROM sectors s
            LEFT JOIN companies c ON s.sector_name = c.sector_name
            GROUP BY s.sector_name, s.company_count
            ORDER BY s.company_count ASC
        ''')

        sectors = cursor.fetchall()
        conn.close()

        return [{
            'name': row[0],
            'total_companies': row[1],
            'working': row[2],
            'pending': row[3],
            'failed': row[4],
            'not_found': row[5]
        } for row in sectors]

    def display_sector_menu(self, sectors):
        """Display interactive sector selection menu"""
        print("\n" + "="*80)
        print("🏭 INDIAN STOCKS DATABASE - SECTOR SCRAPER")
        print("="*80)
        print(f"{'No.':<4} {'Sector Name':<30} {'Total':<7} {'✅Work':<7} {'⏳Pend':<7} {'❌Fail':<7} {'❓NotF':<7} {'%Done':<7}")
        print("-"*80)

        for i, sector in enumerate(sectors, 1):
            total = sector['total_companies']
            working = sector['working']
            pending = sector['pending']
            failed = sector['failed']
            not_found = sector['not_found']

            if total > 0:
                done_pct = (working / total) * 100
            else:
                done_pct = 0

            # Color coding based on completion
            if done_pct == 100:
                status = "🟢"
            elif done_pct > 0:
                status = "🟡"
            else:
                status = "🔴"

            print(f"{i:<4} {sector['name']:<30} {total:<7} {working:<7} {pending:<7} {failed:<7} {not_found:<7} {done_pct:<6.1f}% {status}")

        print("-"*80)
        print("Legend: ✅=Working tokens, ⏳=Pending, ❌=Failed, ❓=Not found on Trendlyne")
        print("Status: 🟢=Complete, 🟡=In progress, 🔴=Not started")

    def get_user_choice(self, sectors):
        """Get user's sector choice"""
        while True:
            try:
                print(f"\nChoose a sector to scrape (1-{len(sectors)}) or 'q' to quit:")
                choice = input("Enter your choice: ").strip().lower()

                if choice == 'q':
                    return None

                choice_num = int(choice)
                if 1 <= choice_num <= len(sectors):
                    return sectors[choice_num - 1]
                else:
                    print(f"❌ Please enter a number between 1 and {len(sectors)}")

            except ValueError:
                print("❌ Please enter a valid number or 'q' to quit")

    def get_sector_companies(self, sector_name, status_filter='pending'):
        """Get companies from a specific sector with given status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, company_name, exchange, symbol, zerodha_url
            FROM companies
            WHERE sector_name = ? AND token_status = ?
            ORDER BY company_name
        ''', (sector_name, status_filter))

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

    def scrape_sector(self, sector_name):
        """Scrape Trendlyne data for entire sector"""
        print(f"\n🔄 STARTING SCRAPE: {sector_name.upper()}")
        print("="*60)

        companies = self.get_sector_companies(sector_name)
        if not companies:
            print(f"✅ No pending companies found in {sector_name} sector")
            return 0, 0, 0

        print(f"📊 Found {len(companies)} pending companies to process")

        success_count = 0
        not_found_count = 0
        error_count = 0

        start_time = time.time()

        for i, company in enumerate(companies):
            elapsed = time.time() - start_time
            if i > 0:
                avg_time = elapsed / i
                remaining = (len(companies) - i) * avg_time
                eta_mins = remaining / 60
                print(f"\n⏱️  Progress: {i}/{len(companies)} | ETA: {eta_mins:.1f} mins")

            print(f"\n[{i+1}/{len(companies)}] {company['name']} ({company['symbol']})")

            try:
                # Step 1: Search Trendlyne
                print(f"  🔍 Searching...")
                search_result = self.search_trendlyne_for_company(company)

                if not search_result:
                    print(f"  ❌ Not found")
                    self.update_company_trendlyne_data(company['id'], None, 'not_found')
                    not_found_count += 1
                    continue

                # Step 2: Extract token
                equity_url = search_result['urls'][0][1]
                print(f"  🎯 Found: {search_result.get('value', '')}")

                token_data = self.extract_token_from_equity_url(equity_url)

                if not token_data:
                    print(f"  ❌ Token extraction failed")
                    self.update_company_trendlyne_data(company['id'], None, 'failed')
                    error_count += 1
                    continue

                # Step 3: Test token
                print(f"  🧪 Testing...")
                if self.test_token(token_data['stock_id'], token_data['auth_token'], equity_url):
                    print(f"  ✅ SUCCESS! (ID: {token_data['stock_id']})")
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

        total_time = time.time() - start_time
        print(f"\n⏱️  Total time: {total_time/60:.1f} minutes")
        print(f"\n🎯 {sector_name.upper()} SCRAPE COMPLETE")
        print(f"✅ Success: {success_count}")
        print(f"❌ Not found: {not_found_count}")
        print(f"💥 Errors: {error_count}")
        print(f"📊 Success rate: {success_count/len(companies)*100:.1f}%")

        return success_count, not_found_count, error_count

    def run_interactive_scraper(self):
        """Run the interactive sector scraper"""
        while True:
            # Get and display sectors
            sectors = self.get_all_sectors()
            self.display_sector_menu(sectors)

            # Get user choice
            chosen_sector = self.get_user_choice(sectors)

            if chosen_sector is None:
                print("\n👋 Goodbye!")
                break

            # Confirm choice
            print(f"\n🎯 Selected: {chosen_sector['name']}")
            print(f"📊 Companies: {chosen_sector['total_companies']}")
            print(f"⏳ Pending: {chosen_sector['pending']}")

            if chosen_sector['pending'] == 0:
                print("✅ No pending companies to process!")
                input("\nPress Enter to continue...")
                continue

            confirm = input(f"\nProceed with scraping {chosen_sector['name']}? (y/N): ").strip().lower()

            if confirm == 'y':
                # Run the scrape
                self.scrape_sector(chosen_sector['name'])
                input("\nPress Enter to continue...")
            else:
                print("❌ Cancelled")

def main():
    print("🚀 Indian Stocks Database - Trendlyne Integration")
    scraper = InteractiveSectorScraper()
    scraper.run_interactive_scraper()

if __name__ == "__main__":
    main()