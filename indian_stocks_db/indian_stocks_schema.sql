-- Indian Stocks Database Schema
-- Sector-wise organization with Trendlyne integration

-- Main sectors table
CREATE TABLE IF NOT EXISTS sectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sector_name TEXT UNIQUE NOT NULL,
    sector_slug TEXT UNIQUE NOT NULL, -- URL-friendly name
    zerodha_url TEXT,
    company_count INTEGER DEFAULT 0,
    discovered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Companies table - all Indian listed companies
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Basic company info from Zerodha
    company_name TEXT NOT NULL,
    sector_id INTEGER REFERENCES sectors(id),
    sector_name TEXT, -- denormalized for easy queries

    -- Exchange info from Zerodha
    exchange TEXT, -- NSE or BSE
    symbol TEXT NOT NULL, -- Exchange symbol (TCS, INFY, etc.)
    zerodha_url TEXT, -- /markets/stocks/NSE/TCS/

    -- Trendlyne data (initially empty, to be populated)
    trendlyne_stock_id TEXT,
    trendlyne_symbol TEXT, -- might be different from exchange symbol
    trendlyne_auth_token TEXT,
    trendlyne_equity_url TEXT,
    trendlyne_company_slug TEXT,

    -- Token status tracking
    token_status TEXT DEFAULT 'pending', -- pending, working, failed, not_found
    token_discovered_date TIMESTAMP,
    token_last_tested TIMESTAMP,

    -- Discovery metadata
    discovery_source TEXT DEFAULT 'zerodha_sector',
    discovery_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint
    UNIQUE(exchange, symbol)
);

-- Sector-specific tables for detailed organization
-- This allows us to have sector-specific analysis

CREATE TABLE IF NOT EXISTS sector_software_services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER REFERENCES companies(id),
    company_name TEXT,
    exchange TEXT,
    symbol TEXT,
    trendlyne_stock_id TEXT,
    trendlyne_auth_token TEXT,
    token_status TEXT DEFAULT 'pending',
    UNIQUE(exchange, symbol)
);

CREATE TABLE IF NOT EXISTS sector_financial_services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER REFERENCES companies(id),
    company_name TEXT,
    exchange TEXT,
    symbol TEXT,
    trendlyne_stock_id TEXT,
    trendlyne_auth_token TEXT,
    token_status TEXT DEFAULT 'pending',
    UNIQUE(exchange, symbol)
);

CREATE TABLE IF NOT EXISTS sector_fmcg (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER REFERENCES companies(id),
    company_name TEXT,
    exchange TEXT,
    symbol TEXT,
    trendlyne_stock_id TEXT,
    trendlyne_auth_token TEXT,
    token_status TEXT DEFAULT 'pending',
    UNIQUE(exchange, symbol)
);

CREATE TABLE IF NOT EXISTS sector_healthcare (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER REFERENCES companies(id),
    company_name TEXT,
    exchange TEXT,
    symbol TEXT,
    trendlyne_stock_id TEXT,
    trendlyne_auth_token TEXT,
    token_status TEXT DEFAULT 'pending',
    UNIQUE(exchange, symbol)
);

CREATE TABLE IF NOT EXISTS sector_auto_ancillary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER REFERENCES companies(id),
    company_name TEXT,
    exchange TEXT,
    symbol TEXT,
    trendlyne_stock_id TEXT,
    trendlyne_auth_token TEXT,
    token_status TEXT DEFAULT 'pending',
    UNIQUE(exchange, symbol)
);

-- Generic sector table template (can be created dynamically)
-- We'll create one for each of the 27 sectors

-- Discovery and processing log
CREATE TABLE IF NOT EXISTS discovery_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL, -- sector_discovery, company_extraction, token_search, token_test
    sector_name TEXT,
    target TEXT, -- URL, company name, etc.
    result TEXT, -- success/failure details
    company_count INTEGER,
    success_count INTEGER,
    error_details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trendlyne search cache to avoid repeated searches
CREATE TABLE IF NOT EXISTS trendlyne_search_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_term TEXT UNIQUE NOT NULL,
    results_json TEXT, -- JSON of search results
    result_count INTEGER,
    search_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies(sector_name);
CREATE INDEX IF NOT EXISTS idx_companies_exchange_symbol ON companies(exchange, symbol);
CREATE INDEX IF NOT EXISTS idx_companies_trendlyne_id ON companies(trendlyne_stock_id);
CREATE INDEX IF NOT EXISTS idx_companies_token_status ON companies(token_status);
CREATE INDEX IF NOT EXISTS idx_discovery_log_action ON discovery_log(action);
CREATE INDEX IF NOT EXISTS idx_discovery_log_sector ON discovery_log(sector_name);