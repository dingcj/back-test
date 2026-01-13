# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Fund Historical Net Asset Value (NAV) Data Downloader** - a Python CLI tool that downloads historical fund performance data from East Money/Tiantian Fund (Chinese financial data source). The tool extracts fund metrics including net value, cumulative value, daily growth rate, and subscription/redemption status, then saves them as CSV/Excel files.

## Quick Start Commands

**Run the downloader:**
```bash
# Download all historical data for a fund
python fund_data_downloader.py -c 210014

# Specify custom output directory
python fund_data_downloader.py -c 210014 -o ./my_data
```

**Install dependencies:**
```bash
pip install requests pandas beautifulsoup4 openpyxl
```

## Architecture

The codebase is organized around a single main class:

**`FundDataDownloader` class** (`fund_data_downloader.py`):
- **API Integration** (`_make_request`): Handles HTTP requests to East Money API with proper headers and user-agent simulation. Supports both JSON and JavaScript variable response formats.
- **Data Parsing** (`_parse_data`): Extracts fund metrics from HTML tables using BeautifulSoup with regex fallback. Handles complex HTML entities and encodings.
- **Pagination** (`download`): Automatically iterates through all pages of historical data, tracking progress and total record counts.
- **File Output** (`_save_to_file`): Generates files with naming convention `fund_{code}_netvalue_{end_date}_to_{start_date}.csv` (e.g., `fund_210014_netvalue_20130130_to_20260112.csv`)

## Key Implementation Details

**API Response Handling:**
- Primary format: JSON with HTML content in the `content` field
- Fallback format: JavaScript variable assignment (`var apidata={...}`)
- HTML entities are unescaped using `html.unescape()`
- Both BeautifulSoup and regex parsers supported for maximum compatibility

**Data Processing:**
- Data sorted by date descending (newest first)
- Date column converted to pandas datetime
- Growth rates cleaned of % symbols and converted to numeric
- Empty values handled gracefully with `errors="coerce"`

**File Naming Convention:**
- Uses data date range, not creation date
- Format: `{start_date}_to_{end_date}` where dates are in `YYYYMMDD` format
- Dates extracted from actual data min/max values

**Error Handling:**
- Network timeouts: 30 seconds per request
- Maximum page limit: 500 pages (prevents infinite loops)
- Multiple parsing strategies with graceful fallbacks
- Comprehensive try/except blocks for all external calls

## Development Notes

**Data Directory:**
- The `data/` directory is gitignored and contains downloaded CSV files
- Files use UTF-8-sig encoding (BOM) for Excel compatibility
- Optional Excel export requires `openpyxl` package

**Chinese Language:**
- All output messages and data fields are in Chinese
- Fund codes are 6-digit Chinese fund identifiers
- Data columns: 净值日期, 单位净值, 累计净值, 日增长率(%), 申购状态, 赎回状态

**Testing:**
- Use real fund codes like `210014` for testing
- Expected output: 3,000+ records for funds with ~13 years of history
- Verify file naming matches actual data date ranges
