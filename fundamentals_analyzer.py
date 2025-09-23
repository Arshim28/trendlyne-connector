#!/usr/bin/env python3
"""
Interactive Fundamentals Analyzer for Indian Stocks
Allows user to select tickers and analyze fundamental data trends and peer comparisons
"""

import sqlite3
import requests
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import os
import sys

class FundamentalsAnalyzer:
    def __init__(self, db_path="indian_stocks_db/indian_stocks.db"):
        self.db_path = db_path
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        })

        # Create output directory for reports
        os.makedirs('fundamentals_reports', exist_ok=True)

    def search_tickers(self, search_term=""):
        """Search for tickers in the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if search_term:
            cursor.execute('''
                SELECT symbol, company_name, sector_name, exchange, trendlyne_stock_id, trendlyne_auth_token
                FROM companies
                WHERE (symbol LIKE ? OR company_name LIKE ?)
                AND token_status = 'working'
                AND trendlyne_auth_token IS NOT NULL
                ORDER BY symbol
            ''', (f'%{search_term.upper()}%', f'%{search_term.title()}%'))
        else:
            cursor.execute('''
                SELECT symbol, company_name, sector_name, exchange, trendlyne_stock_id, trendlyne_auth_token
                FROM companies
                WHERE token_status = 'working'
                AND trendlyne_auth_token IS NOT NULL
                ORDER BY symbol
                LIMIT 50
            ''')

        results = cursor.fetchall()
        conn.close()

        return [{'symbol': row[0], 'name': row[1], 'sector': row[2],
                'exchange': row[3], 'stock_id': row[4], 'auth_token': row[5]}
                for row in results]

    def get_sector_peers(self, sector_name, limit=10):
        """Get peer companies from the same sector"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT symbol, company_name, trendlyne_stock_id, trendlyne_auth_token
            FROM companies
            WHERE sector_name = ?
            AND token_status = 'working'
            AND trendlyne_auth_token IS NOT NULL
            ORDER BY symbol
            LIMIT ?
        ''', (sector_name, limit))

        results = cursor.fetchall()
        conn.close()

        return [{'symbol': row[0], 'name': row[1], 'stock_id': row[2], 'auth_token': row[3]}
                for row in results]

    def fetch_fundamentals(self, stock_id, auth_token, company_name=""):
        """Fetch fundamentals data for a company"""
        url = f"https://trendlyne.com/fundamentals/get-fundamental_results-v2/{stock_id}/{auth_token}/"
        equity_url = f"https://trendlyne.com/equity/{stock_id}/"

        try:
            response = self.session.get(url, headers={'Referer': equity_url}, timeout=30)

            if response.status_code == 200:
                data = response.json()
                if data.get('head', {}).get('status') == '0':
                    return data
                else:
                    print(f"❌ API Error for {company_name}: {data.get('head', {}).get('statusDescription', 'Unknown error')}")
            else:
                print(f"❌ HTTP {response.status_code} for {company_name}")

        except Exception as e:
            print(f"❌ Request failed for {company_name}: {e}")

        return None

    def extract_key_metrics(self, fundamentals_data):
        """Extract key financial metrics from fundamentals data"""
        body = fundamentals_data.get('body', {})

        # Get quarterly and annual data
        quarterly_order = body.get('quarterlyOrder', [])
        annual_order = body.get('annualOrder', [])
        quarterly_data = body.get('quarterlyDataDump', {}).get('consolidated', {})
        annual_data = body.get('annualDataDump', {}).get('consolidated', {})

        metrics = {
            'quarterly': {},
            'annual': {},
            'company_info': body.get('stockData', {}),
            'latest_quarter': quarterly_order[0] if quarterly_order else None,
            'latest_year': annual_order[0] if annual_order else None
        }

        # Key metrics to extract
        key_metrics = {
            'Revenue': ['SR_Q', 'TOTAL_SR_Q', 'OperatingIncome_Q'],  # Revenue metrics
            'NetProfit': ['NP_Q'],  # Net Profit
            'EBITDA': ['EBIDT_Q'],  # EBITDA
            'EPS': ['EPS_Q'],  # Earnings Per Share
            'OperatingProfit': ['OP_Q'],  # Operating Profit
            'TotalRevenue': ['TOTAL_SR_Q'],  # Total Revenue
            'EmployeeExpenses': ['EmployeeExpenses_Q'],  # Employee costs
            'Interest': ['INT_Q'],  # Interest expenses
            'Tax': ['TAX_Q'],  # Tax
            'EquityCapital': ['EQCAP_Q'],  # Equity Capital
            'BookValue': ['BVSH_Q'],  # Book Value per Share
            'NetProfitMargin': ['NETPCT_Q']  # Net Profit Margin
        }

        # Extract quarterly trends
        for period in quarterly_order:
            if period in quarterly_data:
                period_data = quarterly_data[period]
                metrics['quarterly'][period] = {}

                for metric_name, possible_keys in key_metrics.items():
                    for key in possible_keys:
                        if key in period_data and period_data[key] is not None:
                            metrics['quarterly'][period][metric_name] = period_data[key]
                            break

        # Extract annual trends (similar logic)
        annual_metrics = {
            'Revenue': ['SR_A', 'TOTAL_SR_A', 'OperatingIncome_A'],
            'NetProfit': ['NP_A'],
            'EBITDA': ['EBIDT_A'],
            'EPS': ['EPS_A'],
            'OperatingProfit': ['OP_A'],
            'TotalRevenue': ['TOTAL_SR_A'],
            'ROE': ['ROE_A'],
            'ROA': ['ROA_A'],
            'DebtToEquity': ['DE_A']
        }

        for period in annual_order:
            if period in annual_data:
                period_data = annual_data[period]
                metrics['annual'][period] = {}

                for metric_name, possible_keys in annual_metrics.items():
                    for key in possible_keys:
                        if key in period_data and period_data[key] is not None:
                            metrics['annual'][period][metric_name] = period_data[key]
                            break

        return metrics

    def create_trend_analysis(self, company_data, save_charts=True):
        """Create trend analysis charts and summary"""
        symbol = company_data['symbol']
        name = company_data['name']
        metrics = company_data['metrics']

        print(f"\n📈 TREND ANALYSIS: {symbol} - {name}")
        print("="*80)

        # Quarterly trends
        if metrics['quarterly']:
            print("\n📊 QUARTERLY TRENDS:")
            quarterly_df = pd.DataFrame(metrics['quarterly']).T
            quarterly_df.index = pd.to_datetime(quarterly_df.index, format='%b %Y')
            quarterly_df = quarterly_df.sort_index()

            # Display latest metrics
            latest_q = metrics['latest_quarter']
            if latest_q in metrics['quarterly']:
                print(f"\nLatest Quarter ({latest_q}):")
                for metric, value in metrics['quarterly'][latest_q].items():
                    if value is not None:
                        unit = "₹ Cr" if metric in ['Revenue', 'NetProfit', 'EBITDA', 'OperatingProfit', 'TotalRevenue'] else ""
                        unit = "₹" if metric in ['EPS', 'BookValue'] else unit
                        unit = "%" if metric in ['NetProfitMargin', 'ROE', 'ROA'] else unit
                        print(f"  {metric}: {value} {unit}")

            # Calculate growth rates
            if len(quarterly_df) > 1:
                print(f"\nQuarterly Growth (Latest vs Previous):")
                for col in ['Revenue', 'NetProfit', 'EBITDA']:
                    if col in quarterly_df.columns:
                        latest_val = quarterly_df[col].dropna().iloc[-1] if not quarterly_df[col].dropna().empty else None
                        prev_val = quarterly_df[col].dropna().iloc[-2] if len(quarterly_df[col].dropna()) > 1 else None

                        if latest_val and prev_val and prev_val != 0:
                            growth = ((latest_val - prev_val) / prev_val) * 100
                            print(f"  {col}: {growth:.1f}%")

            # Create quarterly charts
            if save_charts and not quarterly_df.empty:
                self.create_charts(quarterly_df, symbol, 'Quarterly', name)

        # Annual trends
        if metrics['annual']:
            print(f"\n📊 ANNUAL TRENDS:")
            annual_df = pd.DataFrame(metrics['annual']).T
            annual_df.index = pd.to_datetime(annual_df.index, format='%b %Y')
            annual_df = annual_df.sort_index()

            # Display latest metrics
            latest_y = metrics['latest_year']
            if latest_y in metrics['annual']:
                print(f"\nLatest Year ({latest_y}):")
                for metric, value in metrics['annual'][latest_y].items():
                    if value is not None:
                        unit = "₹ Cr" if metric in ['Revenue', 'NetProfit', 'EBITDA'] else ""
                        unit = "%" if metric in ['ROE', 'ROA'] else unit
                        print(f"  {metric}: {value} {unit}")

            # Calculate annual growth
            if len(annual_df) > 1:
                print(f"\nAnnual Growth (Latest vs Previous):")
                for col in ['Revenue', 'NetProfit', 'EBITDA']:
                    if col in annual_df.columns:
                        latest_val = annual_df[col].dropna().iloc[-1] if not annual_df[col].dropna().empty else None
                        prev_val = annual_df[col].dropna().iloc[-2] if len(annual_df[col].dropna()) > 1 else None

                        if latest_val and prev_val and prev_val != 0:
                            growth = ((latest_val - prev_val) / prev_val) * 100
                            print(f"  {col}: {growth:.1f}%")

            # Create annual charts
            if save_charts and not annual_df.empty:
                self.create_charts(annual_df, symbol, 'Annual', name)

        return {
            'quarterly_df': quarterly_df if 'quarterly_df' in locals() else pd.DataFrame(),
            'annual_df': annual_df if 'annual_df' in locals() else pd.DataFrame()
        }

    def create_charts(self, df, symbol, period_type, company_name):
        """Create trend charts"""
        if df.empty:
            return

        # Set up the plotting style
        plt.style.use('default')
        sns.set_palette("husl")

        # Create subplots
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'{symbol} - {company_name}\n{period_type} Financial Trends', fontsize=16, fontweight='bold')

        # Revenue trend
        if 'Revenue' in df.columns or 'TotalRevenue' in df.columns:
            revenue_col = 'Revenue' if 'Revenue' in df.columns else 'TotalRevenue'
            axes[0,0].plot(df.index, df[revenue_col], marker='o', linewidth=2, markersize=6)
            axes[0,0].set_title('Revenue Trend', fontweight='bold')
            axes[0,0].set_ylabel('₹ Crores')
            axes[0,0].grid(True, alpha=0.3)
            axes[0,0].tick_params(axis='x', rotation=45)

        # Profit trend
        if 'NetProfit' in df.columns:
            axes[0,1].plot(df.index, df['NetProfit'], marker='s', color='green', linewidth=2, markersize=6)
            axes[0,1].set_title('Net Profit Trend', fontweight='bold')
            axes[0,1].set_ylabel('₹ Crores')
            axes[0,1].grid(True, alpha=0.3)
            axes[0,1].tick_params(axis='x', rotation=45)

        # EBITDA trend
        if 'EBITDA' in df.columns:
            axes[1,0].plot(df.index, df['EBITDA'], marker='^', color='orange', linewidth=2, markersize=6)
            axes[1,0].set_title('EBITDA Trend', fontweight='bold')
            axes[1,0].set_ylabel('₹ Crores')
            axes[1,0].grid(True, alpha=0.3)
            axes[1,0].tick_params(axis='x', rotation=45)

        # EPS trend
        if 'EPS' in df.columns:
            axes[1,1].plot(df.index, df['EPS'], marker='d', color='red', linewidth=2, markersize=6)
            axes[1,1].set_title('Earnings Per Share Trend', fontweight='bold')
            axes[1,1].set_ylabel('₹')
            axes[1,1].grid(True, alpha=0.3)
            axes[1,1].tick_params(axis='x', rotation=45)

        plt.tight_layout()

        # Save chart
        filename = f'fundamentals_reports/{symbol}_{period_type.lower()}_trends.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.show()
        print(f"📊 Chart saved: {filename}")

    def compare_peers(self, companies_data):
        """Compare selected companies"""
        if len(companies_data) < 2:
            print("❌ Need at least 2 companies for peer comparison")
            return

        print(f"\n🔍 PEER COMPARISON: {len(companies_data)} Companies")
        print("="*80)

        # Create comparison dataframes
        latest_metrics = {}

        for company in companies_data:
            symbol = company['symbol']
            metrics = company['metrics']

            # Get latest quarterly metrics
            latest_q = metrics['latest_quarter']
            if latest_q and latest_q in metrics['quarterly']:
                latest_metrics[symbol] = metrics['quarterly'][latest_q].copy()
                latest_metrics[symbol]['Company'] = company['name']
                latest_metrics[symbol]['Sector'] = company.get('sector', 'N/A')

        if not latest_metrics:
            print("❌ No comparable data found")
            return

        # Create comparison DataFrame
        comparison_df = pd.DataFrame(latest_metrics).T

        # Display comparison table
        comparison_cols = ['Revenue', 'NetProfit', 'EBITDA', 'EPS', 'NetProfitMargin']
        available_cols = [col for col in comparison_cols if col in comparison_df.columns]

        if available_cols:
            print("\nLatest Quarter Comparison:")
            print(comparison_df[['Company'] + available_cols].to_string())

            # Create comparison chart
            self.create_peer_comparison_chart(comparison_df, available_cols)

        return comparison_df

    def create_peer_comparison_chart(self, df, metrics):
        """Create peer comparison charts"""
        if df.empty or not metrics:
            return

        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Peer Comparison - Latest Quarter', fontsize=16, fontweight='bold')

        companies = df.index.tolist()

        # Revenue comparison
        if 'Revenue' in metrics:
            axes[0,0].bar(companies, df['Revenue'], color='skyblue', alpha=0.7)
            axes[0,0].set_title('Revenue Comparison', fontweight='bold')
            axes[0,0].set_ylabel('₹ Crores')
            axes[0,0].tick_params(axis='x', rotation=45)

        # Net Profit comparison
        if 'NetProfit' in metrics:
            colors = ['green' if x >= 0 else 'red' for x in df['NetProfit']]
            axes[0,1].bar(companies, df['NetProfit'], color=colors, alpha=0.7)
            axes[0,1].set_title('Net Profit Comparison', fontweight='bold')
            axes[0,1].set_ylabel('₹ Crores')
            axes[0,1].tick_params(axis='x', rotation=45)
            axes[0,1].axhline(y=0, color='black', linestyle='-', alpha=0.3)

        # EBITDA comparison
        if 'EBITDA' in metrics:
            axes[1,0].bar(companies, df['EBITDA'], color='orange', alpha=0.7)
            axes[1,0].set_title('EBITDA Comparison', fontweight='bold')
            axes[1,0].set_ylabel('₹ Crores')
            axes[1,0].tick_params(axis='x', rotation=45)

        # EPS comparison
        if 'EPS' in metrics:
            axes[1,1].bar(companies, df['EPS'], color='purple', alpha=0.7)
            axes[1,1].set_title('EPS Comparison', fontweight='bold')
            axes[1,1].set_ylabel('₹')
            axes[1,1].tick_params(axis='x', rotation=45)

        plt.tight_layout()

        # Save chart
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'fundamentals_reports/peer_comparison_{timestamp}.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.show()
        print(f"📊 Peer comparison chart saved: {filename}")

    def save_report(self, companies_data):
        """Save detailed analysis report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'fundamentals_reports/analysis_report_{timestamp}.json'

        # Prepare report data
        report = {
            'timestamp': timestamp,
            'analysis_date': datetime.now().isoformat(),
            'companies': []
        }

        for company in companies_data:
            company_report = {
                'symbol': company['symbol'],
                'name': company['name'],
                'sector': company.get('sector', 'N/A'),
                'metrics': company['metrics'],
                'summary': {
                    'latest_quarter': company['metrics'].get('latest_quarter'),
                    'latest_year': company['metrics'].get('latest_year'),
                    'quarters_available': len(company['metrics'].get('quarterly', {})),
                    'years_available': len(company['metrics'].get('annual', {}))
                }
            }
            report['companies'].append(company_report)

        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        print(f"📄 Detailed report saved: {filename}")
        return filename

    def interactive_menu(self):
        """Main interactive menu"""
        selected_companies = []

        while True:
            print("\n" + "="*80)
            print("📊 FUNDAMENTALS ANALYZER - INDIAN STOCKS")
            print("="*80)
            print(f"Selected companies: {len(selected_companies)}")
            if selected_companies:
                for i, comp in enumerate(selected_companies, 1):
                    print(f"  {i}. {comp['symbol']} - {comp['name']} ({comp['sector']})")

            print("\nOptions:")
            print("1. Search and add ticker")
            print("2. View selected companies' trends")
            print("3. Peer comparison (requires 2+ companies)")
            print("4. Auto-add sector peers")
            print("5. Remove company")
            print("6. Save analysis report")
            print("7. Clear all selections")
            print("0. Exit")

            choice = input("\nEnter your choice (0-7): ").strip()

            if choice == '0':
                print("👋 Goodbye!")
                break

            elif choice == '1':
                self.search_and_add_ticker(selected_companies)

            elif choice == '2':
                if not selected_companies:
                    print("❌ No companies selected. Add some tickers first.")
                else:
                    self.analyze_selected_companies(selected_companies)

            elif choice == '3':
                if len(selected_companies) < 2:
                    print("❌ Need at least 2 companies for comparison.")
                else:
                    self.compare_peers(selected_companies)

            elif choice == '4':
                self.auto_add_peers(selected_companies)

            elif choice == '5':
                self.remove_company(selected_companies)

            elif choice == '6':
                if selected_companies:
                    self.save_report(selected_companies)
                else:
                    print("❌ No companies to save report for.")

            elif choice == '7':
                selected_companies.clear()
                print("✅ All selections cleared.")

            else:
                print("❌ Invalid choice. Please try again.")

    def search_and_add_ticker(self, selected_companies):
        """Search and add ticker to selection"""
        search_term = input("Enter ticker symbol or company name (or press Enter for top 20): ").strip()

        print("🔍 Searching...")
        results = self.search_tickers(search_term)

        if not results:
            print("❌ No companies found.")
            return

        print(f"\n📋 Found {len(results)} companies:")
        for i, company in enumerate(results[:20], 1):  # Show max 20
            print(f"{i:2d}. {company['symbol']:<10} - {company['name'][:40]:<40} ({company['sector']})")

        try:
            choice = int(input(f"\nSelect company (1-{min(len(results), 20)}) or 0 to cancel: "))
            if 1 <= choice <= min(len(results), 20):
                selected_company = results[choice-1]

                # Check if already selected
                if any(comp['symbol'] == selected_company['symbol'] for comp in selected_companies):
                    print(f"❌ {selected_company['symbol']} already selected.")
                    return

                # Fetch fundamentals data
                print(f"📊 Fetching fundamentals for {selected_company['symbol']}...")
                fundamentals = self.fetch_fundamentals(
                    selected_company['stock_id'],
                    selected_company['auth_token'],
                    selected_company['name']
                )

                if fundamentals:
                    metrics = self.extract_key_metrics(fundamentals)
                    selected_company['metrics'] = metrics
                    selected_companies.append(selected_company)
                    print(f"✅ Added {selected_company['symbol']} - {selected_company['name']}")
                else:
                    print(f"❌ Failed to fetch data for {selected_company['symbol']}")
            elif choice != 0:
                print("❌ Invalid selection.")

        except ValueError:
            print("❌ Invalid input.")

    def analyze_selected_companies(self, selected_companies):
        """Analyze trends for all selected companies"""
        for company in selected_companies:
            trend_data = self.create_trend_analysis(company)
            company['trend_data'] = trend_data

        print(f"\n✅ Analysis complete for {len(selected_companies)} companies.")
        print("📊 Charts saved in 'fundamentals_reports/' directory.")

    def auto_add_peers(self, selected_companies):
        """Automatically add sector peers"""
        if not selected_companies:
            print("❌ Select at least one company first.")
            return

        # Use the sector of the first selected company
        reference_sector = selected_companies[0]['sector']

        print(f"🔍 Finding peers in '{reference_sector}' sector...")
        peers = self.get_sector_peers(reference_sector, limit=10)

        # Filter out already selected companies
        new_peers = [peer for peer in peers
                    if not any(comp['symbol'] == peer['symbol'] for comp in selected_companies)]

        if not new_peers:
            print("❌ No new peers found in the sector.")
            return

        print(f"\n📋 Found {len(new_peers)} peer companies:")
        for i, peer in enumerate(new_peers[:5], 1):  # Show max 5
            print(f"{i}. {peer['symbol']} - {peer['name']}")

        count = min(3, len(new_peers))  # Add max 3 peers
        confirm = input(f"\nAdd top {count} peers? (y/N): ").strip().lower()

        if confirm == 'y':
            for peer in new_peers[:count]:
                print(f"📊 Fetching data for {peer['symbol']}...")
                fundamentals = self.fetch_fundamentals(peer['stock_id'], peer['auth_token'], peer['name'])

                if fundamentals:
                    metrics = self.extract_key_metrics(fundamentals)
                    peer_company = {
                        'symbol': peer['symbol'],
                        'name': peer['name'],
                        'sector': reference_sector,
                        'stock_id': peer['stock_id'],
                        'auth_token': peer['auth_token'],
                        'metrics': metrics
                    }
                    selected_companies.append(peer_company)
                    print(f"✅ Added {peer['symbol']}")
                else:
                    print(f"❌ Failed to fetch data for {peer['symbol']}")

    def remove_company(self, selected_companies):
        """Remove company from selection"""
        if not selected_companies:
            print("❌ No companies selected.")
            return

        print("\nSelected companies:")
        for i, comp in enumerate(selected_companies, 1):
            print(f"{i}. {comp['symbol']} - {comp['name']}")

        try:
            choice = int(input(f"Remove which company? (1-{len(selected_companies)}) or 0 to cancel: "))
            if 1 <= choice <= len(selected_companies):
                removed = selected_companies.pop(choice-1)
                print(f"✅ Removed {removed['symbol']}")
            elif choice != 0:
                print("❌ Invalid selection.")
        except ValueError:
            print("❌ Invalid input.")


def main():
    """Main function"""
    print("🚀 Starting Fundamentals Analyzer...")

    # Check if required packages are available
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        import pandas as pd
    except ImportError as e:
        print(f"❌ Required package missing: {e}")
        print("📦 Install required packages:")
        print("   pip install pandas matplotlib seaborn")
        return

    analyzer = FundamentalsAnalyzer()
    analyzer.interactive_menu()

if __name__ == "__main__":
    main()