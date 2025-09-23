# 📊 Fundamentals Analyzer - Usage Guide

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Analyzer
```bash
python3 fundamentals_analyzer.py
```

## 🎯 Features

### ✅ **Ticker Selection**
- **Search by Symbol**: Enter ticker like "HDFC", "RELIANCE"
- **Search by Name**: Enter company name like "Tata Motors"
- **Browse Top Companies**: Press Enter to see top 20 companies

### ✅ **Trend Analysis**
- **Quarterly Trends**: Up to 13 quarters of data
- **Annual Trends**: Up to 11 years of historical data
- **Key Metrics**:
  - Revenue, Net Profit, EBITDA
  - EPS, Operating Profit, Margins
  - Growth rates (QoQ, YoY)
- **Visual Charts**: Automatic trend chart generation

### ✅ **Peer Comparison**
- **Sector-based**: Compare companies in same sector
- **Multi-company**: Compare 2+ selected companies
- **Visual Comparison**: Side-by-side charts
- **Latest Quarter**: Head-to-head metrics comparison

### ✅ **Auto Peer Discovery**
- **Smart Suggestions**: Automatically find sector peers
- **Bulk Addition**: Add multiple peers at once
- **Filtered Results**: Only working Trendlyne integrations

## 📋 Interactive Menu Options

```
1. Search and add ticker        - Find and select companies
2. View selected trends         - Analyze financial trends
3. Peer comparison             - Compare 2+ companies
4. Auto-add sector peers       - Add peers automatically
5. Remove company              - Remove from selection
6. Save analysis report        - Export detailed JSON report
7. Clear all selections        - Start fresh
0. Exit                        - Quit application
```

## 📊 Available Metrics

### **Quarterly Data**
- Revenue & Total Revenue
- Net Profit & Operating Profit
- EBITDA & Net Profit Margin
- EPS & Book Value per Share
- Employee Expenses & Interest Costs
- Growth rates (QoQ)

### **Annual Data**
- All quarterly metrics (annual versions)
- ROE (Return on Equity)
- ROA (Return on Assets)
- Debt-to-Equity Ratio
- Long-term growth trends

## 📁 Output Files

### **Charts** (`fundamentals_reports/`)
- `{SYMBOL}_quarterly_trends.png` - Quarterly trend charts
- `{SYMBOL}_annual_trends.png` - Annual trend charts
- `peer_comparison_{timestamp}.png` - Peer comparison charts

### **Reports** (`fundamentals_reports/`)
- `analysis_report_{timestamp}.json` - Detailed analysis data
- Contains complete metrics, trends, and metadata

## 🔍 Example Workflow

### 1. **Single Company Analysis**
```
1. Search ticker: "RELIANCE"
2. Select Reliance Industries
3. View trends → Get 11 years of annual data
4. Charts saved automatically
```

### 2. **Peer Comparison**
```
1. Add "HDFC" → Select HDFC Bank
2. Auto-add peers → Gets ICICI, SBI, Axis Bank
3. Peer comparison → Side-by-side analysis
4. Save report → Export complete analysis
```

### 3. **Sector Analysis**
```
1. Search "software" → Browse IT companies
2. Add TCS, Infosys, Wipro
3. View trends → Individual company analysis
4. Compare peers → Sector-wide comparison
```

## 📈 Chart Types

### **Trend Charts** (2x2 Layout)
- **Revenue Trend**: Line chart with growth trajectory
- **Net Profit Trend**: Profitability over time
- **EBITDA Trend**: Operating performance
- **EPS Trend**: Per-share earnings

### **Peer Comparison** (2x2 Layout)
- **Revenue Comparison**: Bar chart comparison
- **Net Profit Comparison**: Color-coded bars (green/red)
- **EBITDA Comparison**: Operating efficiency
- **EPS Comparison**: Per-share performance

## ⚡ Tips & Best Practices

### **For Best Results:**
- Start with well-known large-cap stocks (HDFC, Reliance, TCS)
- Use peer comparison for same-sector companies
- Analyze both quarterly and annual trends
- Save reports before clearing selections

### **Troubleshooting:**
- If a company shows no data, try another from the same sector
- Charts require display capability (may not work in headless environments)
- Large datasets may take time to load

## 🎯 Use Cases

### **Investment Research**
- Fundamental analysis of potential investments
- Peer comparison within sectors
- Historical performance evaluation

### **Portfolio Analysis**
- Compare current holdings
- Sector allocation analysis
- Performance benchmarking

### **Academic Research**
- Financial trend studies
- Sector performance analysis
- Company case studies

## 📞 Data Source
- **Database**: 5,326+ Indian companies across 27 sectors
- **API**: Trendlyne fundamentals endpoints
- **Coverage**: NSE & BSE listed companies
- **Success Rate**: 87% working integrations