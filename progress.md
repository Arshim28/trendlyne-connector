# Trendlyne API Analysis Progress

## Overview
This document tracks our findings for reverse engineering Trendlyne's API calls and data structure to enable programmatic integration for AI-based analysis pipelines.

## Successful Findings

### API Endpoints Discovered

#### ✅ OHLC Data Endpoint (VERIFIED WORKING)
- **URL Pattern**: `https://trendlyne.com/mapp/v1/stock/web/ohlc/{stock_id}/{auth_token}/`
- **Method**: GET
- **Example**: `https://trendlyne.com/mapp/v1/stock/web/ohlc/1577/RKDTEX74CDGD62YUGULP4UKK5Q======/`
- **Purpose**: Fetches real-time and historical price/volume data
- **Status**: ✅ **TESTED SUCCESSFULLY** - Returns 200 OK with JSON data

#### ✅ Fundamentals Data Endpoint (VERIFIED WORKING)
- **URL Pattern**: `https://trendlyne.com/fundamentals/get-fundamental_results-v2/{stock_id}/{auth_token}/`
- **Method**: GET
- **Example**: `https://trendlyne.com/fundamentals/get-fundamental_results-v2/1577/RKDTEX74CDGD62YUGULP4UKK5Q======/`
- **Purpose**: Fetches comprehensive financial statement data
- **Status**: ✅ **TESTED SUCCESSFULLY** - Returns 98KB+ financial data
- **Data**: Quarterly/Annual, P&L/BS/CF, 600+ financial parameters

#### ✅ Search/Discovery API (VERIFIED WORKING)
- **URL Pattern**: `https://trendlyne.com/member/api/ac_snames/all/?term={search_term}&all-results=true`
- **Method**: GET
- **Purpose**: Discovers stocks and their equity URLs for token extraction
- **Status**: ✅ **TESTED SUCCESSFULLY** - Found 28 working stocks
- **Success Rate**: 100% token extraction success

### Request/Response Structures

#### Required Headers (VERIFIED)
```
User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...
Accept: */*
Content-Type: application/json
X-Requested-With: XMLHttpRequest
Referer: https://trendlyne.com/equity/{stock_id}/{symbol}/{company-slug}/
```

#### Response Structure (VERIFIED)
```json
{
  "head": {
    "status": "0",
    "statusDescription": "Success",
    "responseCode": null
  },
  "body": {
    "liveHeaders": [...],     // Field definitions
    "liveData": [...],        // Real-time price/volume data (437+ entries)
    "eodHeaders": [...],      // End-of-day field definitions
    "eodData": [...],         // Historical daily data
    "eodDataLastWeek": [...], // Last week's data
    "stockHeaders": [...],    // Stock info fields
    "stockData": [...],       // Stock details
    "exchange": "NSE",        // Exchange name
    "suggestions": [...]      // Related suggestions
  }
}
```

#### Live Data Format (VERIFIED)
- **Fields**: [timestamp, last_price, volume]
- **Example**: ["2025-09-17T07:54:54+00:00", 831.7, 175.0]
- **Data Points**: 437+ real-time entries
- **Update Frequency**: ~5 minute intervals

### Authentication Methods
- **Token-based**: Auth token embedded in URL path ✅ WORKING
- **Example Token**: `RKDTEX74CDGD62YUGULP4UKK5Q======`
- **CSRF Protection**: csrftoken cookie (optional for this endpoint)

### Data Models

#### Stock Identification (VERIFIED)
- **Stock ID**: 1577 (Mold-Tek Packaging Ltd)
- **Symbol**: MOLDTKPAC
- **Company Slug**: mold-tek-packaging-ltd
- **Exchange**: NSE

#### URL Patterns (VERIFIED)
- **Equity Page**: `/equity/1577/MOLDTKPAC/mold-tek-packaging-ltd/`
- **API Base**: `/mapp/v1/stock/web/`
- **OHLC Endpoint**: `/mapp/v1/stock/web/ohlc/1577/RKDTEX74CDGD62YUGULP4UKK5Q======/`

## Notes
- Repository initialized for Trendlyne API analysis
- Focus on identifying successful API patterns only

---
*Last updated: 2025-09-17*