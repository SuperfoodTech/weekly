# Changelog

All notable changes to this project will be documented in this file.

## [1.0.1] - 2026-05-11

### Fixed
- ✅ **CSV Export Bug**: Diperbaiki masalah penimpaan file (overwrite) pada eksport CSV, sehingga data dari banyak cabang kini bisa ditambah (append) ke file yang sama.
- ✅ **Order Batal API 404 Error**: Ditambahkan header `x-dashboard-id: 83` yang hilang pada endpoint `proxy/46` untuk mengatasi error 404 Not Found saat menarik data pesanan batal.
- ✅ **Elasticsearch Query Error**: Diperbaiki format filter `merchant_id` yang menyebabkan `query_shard_exception` akibat format string yang tidak sesuai standar Elasticsearch.
- ✅ **Defensive Parsing**: Ditambahkan validasi dan ekstraksi data pembatalan yang lebih aman serta pelaporan error (logging) yang detail dari Elasticsearch.

## [1.0.0] - 2026-05-11


### Added

#### Core Features
- ✅ Multi-account session management with BEARER_TOKEN support
- ✅ Per-Store ID scraping for multi-outlet analytics
- ✅ Automatic Google Sheet mapping for outlet-to-Store ID matching
- ✅ Dual export format (Excel .xlsx and CSV .csv)
- ✅ Phone number normalization (support multiple formats)
- ✅ Outlet name normalization with whitespace handling
- ✅ Store ID deduplication (avoid duplicate rows)

#### API Integration
- ✅ Revenue data collection (gross omzet)
- ✅ Net revenue calculation (after deductions)
- ✅ Commission data tracking
- ✅ Orders & cancelled orders tracking
- ✅ Session validation via `/v1/users/me` endpoint
- ✅ Multi-panel Elasticsearch query support

#### Data Processing
- ✅ Date range support (default: 3 months back)
- ✅ Custom date range input with validation
- ✅ Daily and monthly aggregation modes
- ✅ Automatic totals and averages calculation
- ✅ Filtering by Aplikasi=GoFood and Status=Live
- ✅ Phone number normalization (62 → 85 variant handling)

#### File Handling
- ✅ Excel workbook creation with proper closure
- ✅ CSV export with UTF-8 BOM encoding (Google Sheets compatible)
- ✅ Automatic file corruption recovery
- ✅ Absolute path display for file locations
- ✅ Proper error handling for locked/corrupted files

#### User Interface
- ✅ Interactive outlet/Store ID selection
- ✅ Display of multi-Store ID outlets with count badges
- ✅ Per-Store ID processing with clear output
- ✅ Custom date range input validation
- ✅ Session status indicator (valid/expired)
- ✅ Batch outlet selection (comma-separated)

#### Documentation
- ✅ Comprehensive API documentation (API_DOCUMENTATION.md)
- ✅ Quick start guide (README.md)
- ✅ Google Sheet integration guide (GOOGLE_SHEET_GUIDE.md)
- ✅ Environment configuration template (.env.example)
- ✅ Dependencies specification (requirements.txt)

### Technical Details

#### Architecture
- Single Python file (`gofood.py`) with modular function design
- Session-based request handling with proper headers
- Environment variable configuration system
- Sheet mapping with dual key indexing (phone + name)

#### Data Accuracy
- Store ID deduplication at multiple levels
- Phone number variant normalization (62 vs 85)
- Name normalization (lowercase + whitespace trim)
- Outlet identification by name|phone combination (prevents same-name conflicts)

#### Error Handling
- Try-catch blocks for file operations
- Automatic recovery for corrupted Excel files
- Network error messaging
- Session validation before data collection
- Graceful degradation on API failures

### Fixed Issues

#### Session Management
- ✅ Proper Bearer token authentication
- ✅ Session validation before scraping
- ✅ Clear error messages for expired sessions

#### Phone Number Handling
- ✅ Support for both 62 and 85 prefixes
- ✅ Proper normalization across all operations
- ✅ Matching with multiple phone variants

#### File Management
- ✅ Proper workbook closure after save
- ✅ UTF-8 encoding with BOM for CSV
- ✅ Recovery from file corruption

#### Data Integrity
- ✅ Store ID deduplication
- ✅ Outlet name deduplication
- ✅ Proper aggregation for multiple Store IDs

### Known Limitations

- ⚠️ Requires valid GoFood merchant account tokens
- ⚠️ Google Sheet must be published publicly
- ⚠️ Phone numbers must be in Column AA
- ⚠️ API rate limiting not implemented (use responsibly)
- ⚠️ No real-time data (depends on GoFood portal data)

### Future Enhancements

- 🔄 API rate limiting
- 🔄 Database storage integration
- 🔄 Automated scheduling with APScheduler
- 🔄 Data visualization dashboards
- 🔄 Email notifications on completion
- 🔄 Webhook support for external integrations
- 🔄 Interactive web UI
- 🔄 Data backup & archival system

### Migration Guide

No migration needed for version 1.0.0 (initial release)

### Contributors

- Superfood Tech ID Development Team

### Special Notes

#### Testing Verified
- ✅ Multi-outlet scraping (11+ accounts tested)
- ✅ Store ID deduplication (4-10 Store IDs per outlet)
- ✅ Phone number normalization (62/85 variants)
- ✅ CSV export to Google Sheets
- ✅ Excel file integrity
- ✅ Session validation
- ✅ Custom date ranges
- ✅ Batch outlet selection

#### Dependencies
```
requests>=2.31.0
openpyxl>=3.10.0
python-dotenv>=1.0.0
```

#### Minimum Requirements
- Python 3.10+
- 50MB disk space
- Stable internet connection
- GoFood merchant account with published Store IDs

---

**Last Updated:** May 11, 2026  
**Status:** ✅ Production Ready  
**Version:** 1.0.1
