#!/usr/bin/env python3
"""
Enhanced Fundamentals Analyzer for Indian Stocks
Leverages Trendlyne's built-in peer comparison data from the fundamentals API
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
import numpy as np

class EnhancedFundamentalsAnalyzer:
    def __init__(self, db_path="indian_stocks_db/indian_stocks.db"):
        self.db_path = db_path
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        })

        # Create enhanced output directory
        os.makedirs('enhanced_fundamentals_reports', exist_ok=True)

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

    def fetch_fundamentals_with_peers(self, stock_id, auth_token, company_name=""):
        """Fetch fundamentals data including built-in peer comparison data"""
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

    def extract_peer_comparison_data(self, fundamentals_data):
        """Extract peer comparison data from Trendlyne response"""
        body = fundamentals_data.get('body', {})
        pr_data = body.get('pr', {})

        if not pr_data:
            return None

        peer_data = {
            'headers': pr_data.get('table_headers', []),
            'companies': pr_data.get('table_data', []),
            'filters': pr_data.get('filter_dict', []),
            'target_company': None,
            'peers': [],
            'market_leaders': []
        }

        # Process company data
        for company in peer_data['companies']:
            company_info = {
                'name': self._extract_company_name(company.get('Stock', {})),
                'is_target': company.get('Stock', {}).get('highlight_class') == 'hlddd',
                'market_position': company.get('Stock', {}).get('leader_flag'),
                'trendlyne_id': company.get('Stock', {}).get('pk'),
                'fundamental_url': company.get('Stock', {}).get('fundamental_url'),
                'metrics': {}
            }

            # Extract all metrics
            for header in peer_data['headers']:
                metric_name = header.get('name', '')
                if metric_name in company:
                    company_info['metrics'][metric_name] = company[metric_name]

            # Categorize companies
            if company_info['is_target']:
                peer_data['target_company'] = company_info
            else:
                peer_data['peers'].append(company_info)
                if company_info['market_position'] in ['Market Leader', 'Market Runner Up']:
                    peer_data['market_leaders'].append(company_info)

        return peer_data

    def _extract_company_name(self, stock_data):
        """Extract clean company name from stock data"""
        if isinstance(stock_data, dict):
            return stock_data.get('value', stock_data.get('order_by', 'Unknown'))
        return str(stock_data)

    def _clean_numeric_value(self, value):
        """Clean and convert string values to numeric"""
        if value is None:
            return None

        # Convert to string first
        str_value = str(value).strip()

        # Handle empty or None values
        if not str_value or str_value.lower() in ['none', 'null', '']:
            return None

        # Remove percentage signs and commas
        cleaned = str_value.replace('%', '').replace(',', '').replace('₹', '').strip()

        try:
            # Try to convert to float
            return float(cleaned)
        except (ValueError, TypeError):
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
            'Revenue': ['SR_Q', 'TOTAL_SR_Q', 'OperatingIncome_Q'],
            'NetProfit': ['NP_Q'],
            'EBITDA': ['EBIDT_Q'],
            'EPS': ['EPS_Q'],
            'OperatingProfit': ['OP_Q'],
            'TotalRevenue': ['TOTAL_SR_Q'],
            'EmployeeExpenses': ['EmployeeExpenses_Q'],
            'Interest': ['INT_Q'],
            'Tax': ['TAX_Q'],
            'EquityCapital': ['EQCAP_Q'],
            'BookValue': ['BVSH_Q'],
            'NetProfitMargin': ['NETPCT_Q']
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

        # Extract annual trends
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

    def create_enhanced_peer_analysis(self, company_data, save_charts=True):
        """Create comprehensive peer analysis with Trendlyne's built-in peer data"""
        symbol = company_data['symbol']
        name = company_data['name']
        peer_data = company_data.get('peer_data')

        if not peer_data:
            print(f"❌ No peer data available for {symbol}")
            return None

        print(f"\n🏆 ENHANCED PEER ANALYSIS: {symbol} - {name}")
        print("="*80)

        target_company = peer_data.get('target_company')
        peers = peer_data.get('peers', [])
        market_leaders = peer_data.get('market_leaders', [])

        # If no target company found, try to find it or use the first company
        if not target_company:
            print("⚠️  Target company not identified in peer data. Using first available company.")
            if peer_data.get('companies'):
                # Use the first company as target and remove it from peers
                all_companies = peer_data['companies']
                target_company = {
                    'name': self._extract_company_name(all_companies[0].get('Stock', {})),
                    'is_target': True,
                    'market_position': all_companies[0].get('Stock', {}).get('leader_flag'),
                    'trendlyne_id': all_companies[0].get('Stock', {}).get('pk'),
                    'fundamental_url': all_companies[0].get('Stock', {}).get('fundamental_url'),
                    'metrics': all_companies[0]
                }
                # Rebuild peers list without the target
                peers = []
                for i, comp in enumerate(all_companies[1:], 1):
                    peer_info = {
                        'name': self._extract_company_name(comp.get('Stock', {})),
                        'is_target': False,
                        'market_position': comp.get('Stock', {}).get('leader_flag'),
                        'trendlyne_id': comp.get('Stock', {}).get('pk'),
                        'fundamental_url': comp.get('Stock', {}).get('fundamental_url'),
                        'metrics': comp
                    }
                    peers.append(peer_info)
                    if peer_info['market_position'] in ['Market Leader', 'Market Runner Up']:
                        market_leaders.append(peer_info)
            else:
                print(f"❌ No company data available for {symbol}")
                return None

        print(f"\n📊 TARGET COMPANY: {target_company['name']}")
        self._display_key_metrics(target_company['metrics'])

        print(f"\n🥇 MARKET LEADERS IN SECTOR:")
        for leader in market_leaders:
            print(f"   • {leader['name']} ({leader['market_position']})")

        print(f"\n👥 PEER COMPANIES: {len(peers)} companies")
        for i, peer in enumerate(peers[:5], 1):
            print(f"   {i}. {peer['name']}")

        # Create peer comparison analysis
        peer_analysis = self._analyze_peer_metrics(target_company, peers)

        if save_charts:
            self._create_enhanced_peer_charts(symbol, name, target_company, peers, market_leaders)
            self._create_peer_ranking_analysis(symbol, target_company, peers)

        return peer_analysis

    def _display_key_metrics(self, metrics):
        """Display key metrics in a formatted way"""
        key_display_metrics = [
            ('Current Price', '₹'),
            ('Market Capitalization', 'Cr'),
            ('PE TTM Price to Earnings', 'x'),
            ('ROE Annual %', '%'),
            ('Revenue Growth Qtr YoY %', '%'),
            ('Net Profit Qtr', 'Cr'),
            ('Trendlyne Durability Score', '/100'),
            ('Trendlyne Valuation Score', '/100')
        ]

        for metric_name, unit in key_display_metrics:
            if metric_name in metrics and metrics[metric_name] is not None:
                value = metrics[metric_name]
                print(f"   {metric_name}: {value} {unit}")

    def _analyze_peer_metrics(self, target_company, peers):
        """Analyze target company's position among peers"""
        analysis = {
            'rankings': {},
            'percentiles': {},
            'vs_leaders': {},
            'strengths': [],
            'weaknesses': []
        }

        # Key metrics for ranking analysis
        ranking_metrics = [
            'Current Price', 'Market Capitalization', 'PE TTM Price to Earnings',
            'ROE Annual %', 'Revenue Growth Qtr YoY %', 'Net Profit Qtr',
            'Trendlyne Durability Score', 'Trendlyne Valuation Score'
        ]

        for metric in ranking_metrics:
            if metric not in target_company['metrics']:
                continue

            raw_target_value = target_company['metrics'][metric]
            target_value = self._clean_numeric_value(raw_target_value)
            if target_value is None:
                continue

            # Get peer values
            peer_values = []
            for peer in peers:
                if metric in peer['metrics'] and peer['metrics'][metric] is not None:
                    cleaned_value = self._clean_numeric_value(peer['metrics'][metric])
                    if cleaned_value is not None:
                        peer_values.append(cleaned_value)

            if not peer_values:
                continue

            # Calculate ranking
            all_values = peer_values + [target_value]

            # For metrics where higher is better
            higher_is_better = metric in [
                'ROE Annual %', 'Revenue Growth Qtr YoY %', 'Net Profit Qtr',
                'Trendlyne Durability Score', 'Trendlyne Valuation Score'
            ]

            if higher_is_better:
                sorted_values = sorted(all_values, reverse=True)
                rank = sorted_values.index(target_value) + 1
                percentile = ((len(sorted_values) - rank) / (len(sorted_values) - 1)) * 100
            else:
                sorted_values = sorted(all_values)
                rank = sorted_values.index(target_value) + 1
                percentile = ((len(sorted_values) - rank) / (len(sorted_values) - 1)) * 100

            analysis['rankings'][metric] = {
                'rank': rank,
                'total_companies': len(all_values),
                'percentile': percentile,
                'target_value': target_value,
                'peer_median': np.median(peer_values),
                'peer_average': np.mean(peer_values)
            }

            # Identify strengths and weaknesses
            if percentile >= 75:
                analysis['strengths'].append(metric)
            elif percentile <= 25:
                analysis['weaknesses'].append(metric)

        return analysis

    def _create_enhanced_peer_charts(self, symbol, company_name, target_company, peers, market_leaders):
        """Create comprehensive peer comparison charts"""
        # Prepare data for visualization
        companies = [target_company] + peers
        company_names = [comp['name'][:20] + '...' if len(comp['name']) > 20
                        else comp['name'] for comp in companies]

        # Key metrics for visualization
        metrics_to_plot = [
            ('Market Capitalization', 'Market Cap (₹ Cr)'),
            ('ROE Annual %', 'ROE (%)'),
            ('Revenue Growth Qtr YoY %', 'Revenue Growth YoY (%)'),
            ('PE TTM Price to Earnings', 'P/E Ratio'),
            ('Trendlyne Durability Score', 'Durability Score'),
            ('Trendlyne Valuation Score', 'Valuation Score')
        ]

        fig, axes = plt.subplots(3, 2, figsize=(18, 15))
        fig.suptitle(f'{symbol} - Enhanced Peer Analysis\n{company_name}', fontsize=16, fontweight='bold')

        for idx, (metric_key, metric_label) in enumerate(metrics_to_plot):
            row, col = idx // 2, idx % 2
            ax = axes[row, col]

            # Extract values
            values = []
            colors = []
            labels = []

            for i, company in enumerate(companies):
                raw_value = company['metrics'].get(metric_key)
                cleaned_value = self._clean_numeric_value(raw_value)
                if cleaned_value is not None:
                    values.append(cleaned_value)
                    labels.append(company_names[i])

                    # Color coding
                    if company == target_company:
                        colors.append('#2E86AB')  # Blue for target
                    elif company in market_leaders:
                        colors.append('#A23B72')  # Purple for market leaders
                    else:
                        colors.append('#F18F01')  # Orange for peers

            if values:
                bars = ax.barh(labels, values, color=colors, alpha=0.8)
                ax.set_xlabel(metric_label)
                ax.set_title(f'{metric_label} Comparison', fontweight='bold')

                # Highlight target company
                target_idx = 0  # Target is first
                if target_idx < len(bars):
                    bars[target_idx].set_edgecolor('black')
                    bars[target_idx].set_linewidth(2)

                # Add value labels on bars
                for i, (bar, value) in enumerate(zip(bars, values)):
                    ax.text(bar.get_width() + max(values) * 0.01, bar.get_y() + bar.get_height()/2,
                           f'{value:.1f}', ha='left', va='center', fontweight='bold', fontsize=8)

            ax.grid(True, alpha=0.3, axis='x')

        # Add legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#2E86AB', label=f'{symbol} (Target)'),
            Patch(facecolor='#A23B72', label='Market Leaders'),
            Patch(facecolor='#F18F01', label='Sector Peers')
        ]
        fig.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(0.99, 0.99))

        plt.tight_layout()
        filename = f'enhanced_fundamentals_reports/{symbol}_enhanced_peer_analysis.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.show()
        print(f"📊 Enhanced peer analysis chart saved: {filename}")

    def _create_peer_ranking_analysis(self, symbol, target_company, peers):
        """Create peer ranking analysis chart"""
        # Ranking metrics
        ranking_metrics = [
            'Market Capitalization', 'ROE Annual %', 'Revenue Growth Qtr YoY %',
            'Trendlyne Durability Score', 'Trendlyne Valuation Score'
        ]

        rankings = []
        metric_names = []

        for metric in ranking_metrics:
            if metric not in target_company['metrics']:
                continue

            raw_target_value = target_company['metrics'][metric]
            target_value = self._clean_numeric_value(raw_target_value)
            if target_value is None:
                continue

            peer_values = []
            for peer in peers:
                raw_value = peer['metrics'].get(metric)
                cleaned_value = self._clean_numeric_value(raw_value)
                if cleaned_value is not None:
                    peer_values.append(cleaned_value)

            if not peer_values:
                continue

            all_values = peer_values + [target_value]

            # Calculate percentile ranking
            higher_is_better = metric in [
                'ROE Annual %', 'Revenue Growth Qtr YoY %',
                'Trendlyne Durability Score', 'Trendlyne Valuation Score'
            ]

            if higher_is_better:
                sorted_values = sorted(all_values, reverse=True)
                rank = sorted_values.index(target_value) + 1
                percentile = ((len(sorted_values) - rank) / (len(sorted_values) - 1)) * 100
            else:
                sorted_values = sorted(all_values)
                rank = sorted_values.index(target_value) + 1
                percentile = ((len(sorted_values) - rank) / (len(sorted_values) - 1)) * 100

            rankings.append(percentile)
            metric_names.append(metric.replace(' Annual %', '').replace(' Qtr YoY %', ''))

        if rankings:
            # Create radar chart
            fig, ax = plt.subplots(figsize=(10, 8), subplot_kw=dict(projection='polar'))

            # Number of variables
            N = len(metric_names)

            # Angles for each metric
            angles = [n / float(N) * 2 * np.pi for n in range(N)]
            angles += angles[:1]  # Complete the circle

            # Add rankings
            rankings += rankings[:1]  # Complete the circle

            # Plot
            ax.plot(angles, rankings, 'o-', linewidth=2, label=symbol, color='#2E86AB')
            ax.fill(angles, rankings, alpha=0.25, color='#2E86AB')

            # Add labels
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(metric_names, fontsize=10)
            ax.set_ylim(0, 100)
            ax.set_yticks([25, 50, 75, 100])
            ax.set_yticklabels(['25th', '50th', '75th', '100th'], fontsize=8)
            ax.grid(True)

            plt.title(f'{symbol} - Peer Ranking Analysis\n(Percentile Rankings)',
                     size=14, fontweight='bold', pad=20)

            # Add performance zones
            ax.axhline(y=75, color='green', alpha=0.3, linestyle='--', label='Top Quartile')
            ax.axhline(y=50, color='orange', alpha=0.3, linestyle='--', label='Median')
            ax.axhline(y=25, color='red', alpha=0.3, linestyle='--', label='Bottom Quartile')

            plt.legend(loc='upper right', bbox_to_anchor=(1.2, 1.0))

            filename = f'enhanced_fundamentals_reports/{symbol}_peer_rankings.png'
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            plt.show()
            print(f"📊 Peer ranking analysis saved: {filename}")

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

        # Annual trends (similar implementation)
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

        plt.style.use('default')
        sns.set_palette("husl")

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

        filename = f'enhanced_fundamentals_reports/{symbol}_{period_type.lower()}_trends.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.show()
        print(f"📊 Chart saved: {filename}")

    def save_enhanced_report(self, companies_data):
        """Save enhanced analysis report with peer data"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'enhanced_fundamentals_reports/enhanced_analysis_report_{timestamp}.json'

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
                'peer_data': company.get('peer_data', {}),
                'peer_analysis': company.get('peer_analysis', {}),
                'summary': {
                    'latest_quarter': company['metrics'].get('latest_quarter'),
                    'latest_year': company['metrics'].get('latest_year'),
                    'quarters_available': len(company['metrics'].get('quarterly', {})),
                    'years_available': len(company['metrics'].get('annual', {})),
                    'peers_count': len(company.get('peer_data', {}).get('peers', [])),
                    'market_leaders_count': len(company.get('peer_data', {}).get('market_leaders', []))
                }
            }
            report['companies'].append(company_report)

        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        print(f"📄 Enhanced report saved: {filename}")
        return filename

    def interactive_menu(self):
        """Main interactive menu"""
        selected_companies = []

        while True:
            print("\n" + "="*80)
            print("🚀 ENHANCED FUNDAMENTALS ANALYZER - WITH PEER DATA")
            print("="*80)
            print(f"Selected companies: {len(selected_companies)}")
            if selected_companies:
                for i, comp in enumerate(selected_companies, 1):
                    peer_count = len(comp.get('peer_data', {}).get('peers', []))
                    print(f"  {i}. {comp['symbol']} - {comp['name']} ({peer_count} peers)")

            print("\nOptions:")
            print("1. Search and add ticker (with peer analysis)")
            print("2. View company trends")
            print("3. Enhanced peer analysis")
            print("4. Compare multiple companies")
            print("5. Remove company")
            print("6. Save enhanced report")
            print("7. Clear all selections")
            print("0. Exit")

            choice = input("\nEnter your choice (0-7): ").strip()

            if choice == '0':
                print("👋 Goodbye!")
                break

            elif choice == '1':
                self.search_and_add_ticker_enhanced(selected_companies)

            elif choice == '2':
                if not selected_companies:
                    print("❌ No companies selected. Add some tickers first.")
                else:
                    self.analyze_selected_companies(selected_companies)

            elif choice == '3':
                if not selected_companies:
                    print("❌ No companies selected. Add some tickers first.")
                else:
                    self.run_enhanced_peer_analysis(selected_companies)

            elif choice == '4':
                if len(selected_companies) < 2:
                    print("❌ Need at least 2 companies for comparison.")
                else:
                    self.compare_multiple_companies(selected_companies)

            elif choice == '5':
                self.remove_company(selected_companies)

            elif choice == '6':
                if selected_companies:
                    self.save_enhanced_report(selected_companies)
                else:
                    print("❌ No companies to save report for.")

            elif choice == '7':
                selected_companies.clear()
                print("✅ All selections cleared.")

            else:
                print("❌ Invalid choice. Please try again.")

    def search_and_add_ticker_enhanced(self, selected_companies):
        """Search and add ticker with enhanced peer analysis"""
        search_term = input("Enter ticker symbol or company name (or press Enter for top 20): ").strip()

        print("🔍 Searching...")
        results = self.search_tickers(search_term)

        if not results:
            print("❌ No companies found.")
            return

        print(f"\n📋 Found {len(results)} companies:")
        for i, company in enumerate(results[:20], 1):
            print(f"{i:2d}. {company['symbol']:<10} - {company['name'][:40]:<40} ({company['sector']})")

        try:
            choice = int(input(f"\nSelect company (1-{min(len(results), 20)}) or 0 to cancel: "))
            if 1 <= choice <= min(len(results), 20):
                selected_company = results[choice-1]

                if any(comp['symbol'] == selected_company['symbol'] for comp in selected_companies):
                    print(f"❌ {selected_company['symbol']} already selected.")
                    return

                print(f"📊 Fetching enhanced data for {selected_company['symbol']}...")
                fundamentals = self.fetch_fundamentals_with_peers(
                    selected_company['stock_id'],
                    selected_company['auth_token'],
                    selected_company['name']
                )

                if fundamentals:
                    # Extract regular metrics
                    metrics = self.extract_key_metrics(fundamentals)
                    selected_company['metrics'] = metrics

                    # Extract peer comparison data
                    peer_data = self.extract_peer_comparison_data(fundamentals)
                    selected_company['peer_data'] = peer_data

                    selected_companies.append(selected_company)

                    peer_count = len(peer_data['peers']) if peer_data else 0
                    print(f"✅ Added {selected_company['symbol']} with {peer_count} peers")

                    if peer_data and peer_data['market_leaders']:
                        print(f"🏆 Market leaders identified: {len(peer_data['market_leaders'])}")

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

        print(f"\n✅ Trend analysis complete for {len(selected_companies)} companies.")

    def run_enhanced_peer_analysis(self, selected_companies):
        """Run enhanced peer analysis for selected companies"""
        for company in selected_companies:
            peer_analysis = self.create_enhanced_peer_analysis(company)
            company['peer_analysis'] = peer_analysis

        print(f"\n✅ Enhanced peer analysis complete for {len(selected_companies)} companies.")
        print("📊 Charts saved in 'enhanced_fundamentals_reports/' directory.")

    def compare_multiple_companies(self, selected_companies):
        """Compare multiple selected companies"""
        print(f"\n🔍 MULTI-COMPANY COMPARISON: {len(selected_companies)} Companies")
        print("="*80)

        comparison_data = []
        for company in selected_companies:
            if company.get('peer_data') and company['peer_data'].get('target_company'):
                target_metrics = company['peer_data']['target_company']['metrics']
                comparison_data.append({
                    'symbol': company['symbol'],
                    'name': company['name'],
                    'metrics': target_metrics
                })

        if len(comparison_data) < 2:
            print("❌ Need at least 2 companies with peer data for comparison.")
            return

        # Create multi-company comparison chart
        self._create_multi_company_comparison(comparison_data)

    def _create_multi_company_comparison(self, companies_data):
        """Create multi-company comparison chart"""
        symbols = [comp['symbol'] for comp in companies_data]

        metrics_to_compare = [
            ('Market Capitalization', 'Market Cap (₹ Cr)'),
            ('ROE Annual %', 'ROE (%)'),
            ('Revenue Growth Qtr YoY %', 'Revenue Growth (%)'),
            ('PE TTM Price to Earnings', 'P/E Ratio')
        ]

        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Multi-Company Comparison', fontsize=16, fontweight='bold')

        colors = plt.cm.Set3(np.linspace(0, 1, len(companies_data)))

        for idx, (metric_key, metric_label) in enumerate(metrics_to_compare):
            row, col = idx // 2, idx % 2
            ax = axes[row, col]

            values = []
            labels = []
            bar_colors = []

            for i, company in enumerate(companies_data):
                raw_value = company['metrics'].get(metric_key)
                cleaned_value = self._clean_numeric_value(raw_value)
                if cleaned_value is not None:
                    values.append(cleaned_value)
                    labels.append(company['symbol'])
                    bar_colors.append(colors[i])

            if values:
                bars = ax.bar(labels, values, color=bar_colors, alpha=0.8)
                ax.set_ylabel(metric_label)
                ax.set_title(f'{metric_label} Comparison', fontweight='bold')
                ax.grid(True, alpha=0.3, axis='y')

                # Add value labels on bars
                for bar, value in zip(bars, values):
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values) * 0.01,
                           f'{value:.1f}', ha='center', va='bottom', fontweight='bold')

        plt.tight_layout()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'enhanced_fundamentals_reports/multi_company_comparison_{timestamp}.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.show()
        print(f"📊 Multi-company comparison saved: {filename}")

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
    print("🚀 Starting Enhanced Fundamentals Analyzer with Peer Data...")

    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        import pandas as pd
        import numpy as np
    except ImportError as e:
        print(f"❌ Required package missing: {e}")
        print("📦 Install required packages:")
        print("   pip install pandas matplotlib seaborn numpy")
        return

    analyzer = EnhancedFundamentalsAnalyzer()
    analyzer.interactive_menu()

if __name__ == "__main__":
    main()