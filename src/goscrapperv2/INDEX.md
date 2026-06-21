# 📚 GoScrapper Documentation Index

Complete documentation and guides for GoScrapper GoFood Analytics scraper.

## 🚀 Getting Started

**New to GoScrapper?** Start here:

1. **[README.md](README.md)** - Overview, quick start, and common usage
   - Features overview
   - Installation steps
   - Basic configuration
   - Troubleshooting tips

2. **[GOOGLE_SHEET_GUIDE.md](GOOGLE_SHEET_GUIDE.md)** - Google Sheet setup and formatting
   - Sheet structure requirements
   - Column mapping guide
   - Phone number formatting
   - Multi-Store ID handling
   - Filtering rules
   - Step-by-step setup

3. **[.env.example](.env.example)** - Configuration template
   - Bearer token setup
   - Outlet information
   - Example .env structure

---

## 📖 Detailed Documentation

### API Reference
**[API_DOCUMENTATION.md](API_DOCUMENTATION.md)** - Complete technical reference

Sections:
- [Overview](#overview) - Project description and features
- [Installation & Setup](#installation--setup) - Requirements and installation
- [Configuration](#configuration) - Environment variables setup
- [Core Functions](#core-functions) - Function reference and usage
- [Output Format](#output-format) - Data structure and fields
- [API Endpoints Used](#api-endpoints-used) - GoFood Portal endpoints
- [Usage Examples](#usage-examples) - Real-world examples
- [Data Processing Flow](#data-processing-flow) - System architecture
- [Error Handling](#error-handling) - Common issues and solutions
- [Advanced Configuration](#advanced-configuration) - Custom setup

### Project Information
**[CHANGELOG.md](CHANGELOG.md)** - Release history and version notes

Sections:
- [v1.0.0](#100---2026-05-11) - Initial release features
- [Known Limitations](#known-limitations) - Current constraints
- [Future Enhancements](#future-enhancements) - Planned features
- [Testing Verified](#testing-verified) - Quality assurance summary

---

## 📁 Project Structure

```
goscrapper/
├── gofood.py                    # Main application
├── requirements.txt             # Python dependencies
├── .env.example                 # Configuration template
│
├── README.md                    # Quick start guide
├── API_DOCUMENTATION.md         # Full API reference
├── GOOGLE_SHEET_GUIDE.md        # Sheet integration guide
├── CHANGELOG.md                 # Release history
├── INDEX.md                     # This file
│
├── revenue_3_bulan.xlsx         # Sample output (Excel)
├── revenue_3_bulan.csv          # Sample output (CSV)
└── .env                         # Configuration (git-ignored)
```

---

## 🎯 Quick Navigation by Use Case

### I want to...

#### 🔧 Install and set up GoScrapper
→ See [README.md - Installation](README.md#-quick-start)

#### ⚙️ Configure environment variables
→ See [.env.example](.env.example) and [API_DOCUMENTATION.md - Configuration](API_DOCUMENTATION.md#configuration)

#### 📊 Set up Google Sheet mapping
→ See [GOOGLE_SHEET_GUIDE.md](GOOGLE_SHEET_GUIDE.md)

#### ▶️ Run the scraper
→ See [README.md - Usage Examples](README.md#-usage-examples)

#### 📈 Understand output format
→ See [API_DOCUMENTATION.md - Output Format](API_DOCUMENTATION.md#output-format)

#### 🐛 Fix an error
→ See [README.md - Troubleshooting](README.md#-troubleshooting) or [API_DOCUMENTATION.md - Error Handling](API_DOCUMENTATION.md#error-handling)

#### 💻 Understand the code
→ See [API_DOCUMENTATION.md - Core Functions](API_DOCUMENTATION.md#core-functions)

#### 🔌 Use the API functions programmatically
→ See [API_DOCUMENTATION.md - API Endpoints](API_DOCUMENTATION.md#api-endpoints-used)

#### 📋 Check what was changed in this version
→ See [CHANGELOG.md](CHANGELOG.md)

---

## 📊 Data Flow Diagram

```
┌─────────────────────────────────────┐
│  Configure .env with tokens         │  See: .env.example
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│  Set up Google Sheet with outlet    │  See: GOOGLE_SHEET_GUIDE.md
│  data (names, Store IDs, cabang)    │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│  Run: python3 gofood.py             │  See: README.md
│  Select outlets and date range      │
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│  Fetch analytics data from          │  See: API_DOCUMENTATION.md
│  GoFood Portal (5 data types)       │  - API Endpoints Used
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│  Process & aggregate per Store ID   │  See: API_DOCUMENTATION.md
│  Calculate totals & averages        │  - Data Processing Flow
└────────────┬────────────────────────┘
             │
┌────────────▼────────────────────────┐
│  Save Excel + CSV files             │  See: API_DOCUMENTATION.md
│  Ready to import to Google Sheets    │  - Output Format
└─────────────────────────────────────┘
```

---

## 🔑 Key Concepts

### Multi-Account Support
- Multiple GoFood merchant accounts managed in single .env file
- Each account needs unique BEARER_TOKEN_{phone}_{id}
- Separate outlet info (name, branch) per account
- See: [API_DOCUMENTATION.md - Configuration](API_DOCUMENTATION.md#environment-variables-env-file)

### Store ID Mapping
- Phone numbers from .env matched to Store IDs from Google Sheet
- One outlet can have multiple Store IDs (branches/locations)
- Automatic deduplication and normalization
- See: [GOOGLE_SHEET_GUIDE.md - Multi-Store ID Handling](GOOGLE_SHEET_GUIDE.md#multi-store-id-handling)

### Phone Number Normalization
- Supports multiple formats: 62xxxxx, 85xxxxx, +62xxxxx, etc.
- Automatically normalized to 85xxxxx format
- Prevents matching errors across different formats
- See: [API_DOCUMENTATION.md - normalize_phone()](API_DOCUMENTATION.md#normalize_phones)

### Per-Store ID Scraping
- Each Store ID scraped separately
- Separate data rows for each Store ID in output
- Enables tracking by branch/location
- See: [API_DOCUMENTATION.md - Core Functions](API_DOCUMENTATION.md#core-functions)

### Dual Export Format
- Excel (.xlsx): Full formatting, compatible with Excel/Sheets
- CSV (.csv): Universal format, direct import to Google Sheets
- Identical data, different formats
- See: [API_DOCUMENTATION.md - Output Format](API_DOCUMENTATION.md#output-format)

---

## 📞 Support & Resources

### Documentation
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md) - Technical reference
- [README.md](README.md) - Quick start and overview
- [GOOGLE_SHEET_GUIDE.md](GOOGLE_SHEET_GUIDE.md) - Sheet integration
- [CHANGELOG.md](CHANGELOG.md) - Version history

### Quick Answers
- **How to install?** → [README.md](README.md#-quick-start)
- **How to configure?** → [.env.example](.env.example)
- **How to set up sheet?** → [GOOGLE_SHEET_GUIDE.md](GOOGLE_SHEET_GUIDE.md)
- **Getting errors?** → [README.md - Troubleshooting](README.md#-troubleshooting)
- **Need API details?** → [API_DOCUMENTATION.md](API_DOCUMENTATION.md)

### File Information

| File | Size | Purpose |
|------|------|---------|
| gofood.py | ~25KB | Main application |
| API_DOCUMENTATION.md | 14KB | Full technical reference |
| README.md | 5KB | Quick start guide |
| GOOGLE_SHEET_GUIDE.md | 7.5KB | Sheet setup guide |
| CHANGELOG.md | 8KB | Release notes |
| requirements.txt | 55B | Python dependencies |
| .env.example | 1.9KB | Config template |

---

## 🎓 Learning Path

**Beginner Level:**
1. Read [README.md](README.md) overview
2. Copy [.env.example](.env.example) and fill in your details
3. Run `python3 gofood.py` with default settings
4. Check output files

**Intermediate Level:**
1. Study [GOOGLE_SHEET_GUIDE.md](GOOGLE_SHEET_GUIDE.md)
2. Set up your Google Sheet properly
3. Try custom date ranges
4. Select specific outlets

**Advanced Level:**
1. Read [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
2. Understand data processing flow
3. Modify code for custom requirements
4. Integrate with other systems

---

## ✅ Verification Checklist

Before running GoScrapper, verify:

- [ ] Python 3.10+ installed
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] .env file configured with BEARER_TOKENs
- [ ] Outlet names added to .env (or will use sheet mapping)
- [ ] Google Sheet published and accessible
- [ ] Google Sheet has required columns (see GOOGLE_SHEET_GUIDE.md)
- [ ] Phone numbers in Column AA
- [ ] Internet connection stable

---

## 📈 Success Metrics

After successful run, you should see:

✅ "Ditemukan X akun untuk diproses"  
✅ "Ditemukan X entri pada sheet untuk dicocokkan"  
✅ "Berhasil mengambil data Revenue"  
✅ "Berhasil menyimpan data ke: [path/to/file.xlsx]"  
✅ Output files (Excel + CSV) created

---

## 🔄 Version Information

- **Current Version:** 1.0.0
- **Release Date:** May 11, 2026
- **Status:** ✅ Production Ready
- **Python:** 3.10+
- **Dependencies:** See [requirements.txt](requirements.txt)

For version history, see [CHANGELOG.md](CHANGELOG.md)

---

**Last Updated:** May 11, 2026  
**Documentation Version:** 1.0.0

For questions or issues, refer to the appropriate documentation file above or review the troubleshooting section.
