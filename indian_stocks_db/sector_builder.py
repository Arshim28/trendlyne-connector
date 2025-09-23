#!/usr/bin/env python3
"""
Indian Stocks Database Builder
Extracts all companies from Zerodha sectors and prepares for Trendlyne integration
"""

import requests
import sqlite3
import json
import time
from bs4 import BeautifulSoup
from datetime import datetime
import re

class IndianStocksDB:
    def __init__(self, db_path="indian_stocks.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize database with schema"""
        with open('indian_stocks_schema.sql', 'r') as f:
            schema = f.read()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.executescript(schema)
        conn.commit()
        conn.close()

    def log_action(self, action, sector_name=None, target=None, result=None,
                   company_count=0, success_count=0, error_details=None):
        """Log discovery actions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO discovery_log
            (action, sector_name, target, result, company_count, success_count, error_details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (action, sector_name, target, result, company_count, success_count, error_details))

        conn.commit()
        conn.close()

    def get_zerodha_sectors(self):
        """Get all sectors from Zerodha main page"""
        url = "https://zerodha.com/markets/sector/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...'
        }

        print("=== EXTRACTING ZERODHA SECTORS ===")

        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                self.log_action("sector_discovery", target=url, result=f"HTTP {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            sector_links = soup.select('a[href*="/markets/sector/"]')

            sectors = []
            for link in sector_links:
                sector_name = link.get_text(strip=True)
                sector_url = link.get('href')

                if sector_url.startswith('/'):
                    sector_url = f"https://zerodha.com{sector_url}"

                # Extract slug from URL
                sector_slug = sector_url.split('/')[-2] if sector_url.endswith('/') else sector_url.split('/')[-1]

                sectors.append({
                    'name': sector_name,
                    'slug': sector_slug,
                    'url': sector_url
                })

            print(f"Found {len(sectors)} sectors")
            self.log_action("sector_discovery", target=url, result="success", company_count=len(sectors))

            return sectors

        except Exception as e:
            print(f"Error: {e}")
            self.log_action("sector_discovery", target=url, result="error", error_details=str(e))
            return []

    def store_sectors(self, sectors):
        """Store sectors in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for sector in sectors:
            cursor.execute('''
                INSERT OR REPLACE INTO sectors (sector_name, sector_slug, zerodha_url)
                VALUES (?, ?, ?)
            ''', (sector['name'], sector['slug'], sector['url']))

        conn.commit()
        conn.close()

        print(f"Stored {len(sectors)} sectors in database")

    def extract_companies_from_sector(self, sector):
        """Extract all companies from a specific sector page"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...'
        }

        print(f"Extracting companies from: {sector['name']}")

        try:
            response = requests.get(sector['url'], headers=headers)
            if response.status_code != 200:
                self.log_action("company_extraction", sector['name'], sector['url'],
                              f"HTTP {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all company links
            company_links = soup.select('a[href*="/markets/stocks/"]')

            companies = []
            for link in company_links:
                company_name = link.get_text(strip=True)
                company_url = link.get('href')

                # Extract exchange and symbol from URL
                # Pattern: /markets/stocks/{EXCHANGE}/{SYMBOL}/
                url_match = re.search(r'/markets/stocks/([^/]+)/([^/]+)/?', company_url)
                if url_match:
                    exchange = url_match.group(1)
                    symbol = url_match.group(2)

                    companies.append({
                        'name': company_name,
                        'exchange': exchange,
                        'symbol': symbol,
                        'zerodha_url': f"https://zerodha.com{company_url}" if company_url.startswith('/') else company_url,
                        'sector_name': sector['name']
                    })

            print(f"  Found {len(companies)} companies")
            self.log_action("company_extraction", sector['name'], sector['url'],
                          "success", company_count=len(companies))

            return companies

        except Exception as e:
            print(f"  Error: {e}")
            self.log_action("company_extraction", sector['name'], sector['url'],
                          "error", error_details=str(e))
            return []

    def store_companies(self, companies, sector_id):
        """Store companies in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stored_count = 0
        for company in companies:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO companies
                    (company_name, sector_id, sector_name, exchange, symbol, zerodha_url,
                     discovery_source, discovery_date, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    company['name'],
                    sector_id,
                    company['sector_name'],
                    company['exchange'],
                    company['symbol'],
                    company['zerodha_url'],
                    'zerodha_sector',
                    datetime.now(),
                    datetime.now()
                ))
                stored_count += 1

            except Exception as e:
                print(f"    Error storing {company['name']}: {e}")

        conn.commit()
        conn.close()

        return stored_count

    def create_sector_table(self, sector_slug):
        """Create sector-specific table"""
        table_name = f"sector_{sector_slug.replace('-', '_')}"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER REFERENCES companies(id),
                company_name TEXT,
                exchange TEXT,
                symbol TEXT,
                trendlyne_stock_id TEXT,
                trendlyne_auth_token TEXT,
                token_status TEXT DEFAULT 'pending',
                UNIQUE(exchange, symbol)
            )
        ''')

        conn.commit()
        conn.close()

        return table_name

    def populate_sector_table(self, sector_name, table_name):
        """Populate sector-specific table with companies"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get companies for this sector
        cursor.execute('''
            SELECT id, company_name, exchange, symbol
            FROM companies
            WHERE sector_name = ?
        ''', (sector_name,))

        companies = cursor.fetchall()

        # Insert into sector table
        for company in companies:
            cursor.execute(f'''
                INSERT OR REPLACE INTO {table_name}
                (company_id, company_name, exchange, symbol)
                VALUES (?, ?, ?, ?)
            ''', company)

        conn.commit()
        conn.close()

        return len(companies)

    def build_complete_database(self):
        """Build the complete Indian stocks database"""
        print("=== BUILDING COMPLETE INDIAN STOCKS DATABASE ===")

        # Step 1: Get all sectors
        sectors = self.get_zerodha_sectors()
        if not sectors:
            print("Failed to get sectors")
            return

        # Step 2: Store sectors
        self.store_sectors(sectors)

        # Step 3: Process each sector
        total_companies = 0
        for i, sector in enumerate(sectors):
            print(f"\n[{i+1}/{len(sectors)}] Processing: {sector['name']}")

            # Extract companies
            companies = self.extract_companies_from_sector(sector)
            if not companies:
                continue

            # Get sector ID
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM sectors WHERE sector_slug = ?', (sector['slug'],))
            sector_id = cursor.fetchone()[0]
            conn.close()

            # Store companies
            stored_count = self.store_companies(companies, sector_id)
            total_companies += stored_count

            # Create and populate sector-specific table
            table_name = self.create_sector_table(sector['slug'])
            sector_companies = self.populate_sector_table(sector['name'], table_name)

            print(f"  Stored {stored_count} companies in main table")
            print(f"  Populated {sector_companies} companies in {table_name}")

            # Update sector company count
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE sectors SET company_count = ?, last_updated = ?
                WHERE id = ?
            ''', (len(companies), datetime.now(), sector_id))
            conn.commit()
            conn.close()

            time.sleep(1)  # Be respectful to Zerodha

        print(f"\n=== DATABASE BUILD COMPLETE ===")
        print(f"Total companies: {total_companies}")
        print(f"Total sectors: {len(sectors)}")

    def show_database_summary(self):
        """Show summary of built database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Sectors summary
        cursor.execute('SELECT COUNT(*) FROM sectors')
        sector_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM companies')
        company_count = cursor.fetchone()[0]

        cursor.execute('SELECT exchange, COUNT(*) FROM companies GROUP BY exchange')
        exchange_counts = cursor.fetchall()

        cursor.execute('''
            SELECT sector_name, COUNT(*) as count
            FROM companies
            GROUP BY sector_name
            ORDER BY count DESC
            LIMIT 10
        ''')
        top_sectors = cursor.fetchall()

        conn.close()

        print(f"\n=== DATABASE SUMMARY ===")
        print(f"Total sectors: {sector_count}")
        print(f"Total companies: {company_count}")
        print(f"\nExchange breakdown:")
        for exchange, count in exchange_counts:
            print(f"  {exchange}: {count} companies")

        print(f"\nTop 10 sectors by company count:")
        for sector, count in top_sectors:
            print(f"  {sector}: {count} companies")

if __name__ == "__main__":
    db = IndianStocksDB()

    # Build the complete database
    db.build_complete_database()

    # Show summary
    db.show_database_summary()