# GoScrapper - GoFood Analytics Multi-Outlet Data Scraper

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Aplikasi Python untuk scraping dan menganalisis data penjualan GoFood dari multiple outlets secara otomatis dengan per-Store ID tracking.

## 🚀 Fitur Utama

✅ **Multi-Account Support** - Manage multiple GoFood merchant accounts  
✅ **Per-Store ID Scraping** - Scrape data terpisah untuk setiap Store ID/cabang  
✅ **Automatic Mapping** - Auto-match phone numbers ke outlet names dari Google Sheet  
✅ **Data Normalization** - Phone number & outlet name normalization (support format Indonesia)  
✅ **Dual Export** - Output Excel (.xlsx) dan CSV (.csv) untuk Google Sheets compatibility  
✅ **Session Management** - Bearer token-based authentication dengan multi-account support  
✅ **Error Recovery** - Automatic file corruption recovery & proper file closure  

## 📋 Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/superfoodtechid/goscrapper.git
cd goscrapper
pip install -r requirements.txt
```

### 2. Configure .env
```bash
# Format: BEARER_TOKEN_{PHONE}_{UNIQUE_ID}=token
BEARER_TOKEN_85136517321_salero=your_bearer_token_here
BEARER_TOKEN_85136517318_ayam_geprek=your_bearer_token_here

# Outlet info
NAMA_OUTLET_85136517321_salero=Salero Minang Raya
CABANG_85136517321_salero=Tanpa Cabang
```

### 3. Run
```bash
python3 gofood.py
```

## 📊 Output

Program akan generate:
- `revenue_3_bulan.xlsx` - Excel format (3 months default)
- `revenue_3_bulan.csv` - CSV format (untuk Google Sheets)

Atau dengan custom date range:
- `revenue_2026-05-01_sampai_2026-05-10.xlsx`
- `revenue_2026-05-01_sampai_2026-05-10.csv`

## 🔧 Configuration

### Environment Variables
```env
# Session tokens (multiple allowed)
BEARER_TOKEN_{PHONE}_{UNIQUE_ID}=token

# Outlet information
NAMA_OUTLET_{PHONE}_{UNIQUE_ID}=Outlet Name
CABANG_{PHONE}_{UNIQUE_ID}=Branch Name

# Optional: Custom Google Sheet URL
# SHEET_URL=https://docs.google.com/spreadsheets/d/...
```

### Google Sheet Requirements
Your published Google Sheet harus memiliki:
- **Column AA**: Phone numbers (format: 62xxxxx atau 85xxxxx)
- **Column "Nama Outlet"**: Outlet names
- **Column "Store ID"**: Store IDs (support multiple per outlet)
- **Column "Cabang"**: Branch names
- **Column "Aplikasi"**: Filter value "GoFood"
- **Column "Status"**: Filter value "Live"

## 📈 Data Collected

Per each Store ID, aplikasi mengumpulkan:

| Data | Endpoint | Description |
|------|----------|-------------|
| Revenue Kotor | `/proxy/63/_msearch` | Gross revenue |
| Omzet Bersih | `/proxy/63/_msearch` | Net revenue after deductions |
| Komisi | `/proxy/63/_msearch` | Commission fees |
| Orders | `/proxy/46/_msearch` | Total successful orders |
| Order Batal | `/proxy/46/_msearch` | Cancelled orders |

## 💡 Usage Examples

### Default (3 months back)
```bash
python3 gofood.py
# Select: all
```

### Custom Date Range
```bash
python3 gofood.py
# Select custom date range: y
# Start: 2026-05-01
# End: 2026-05-10
```

### Specific Outlets
```bash
python3 gofood.py
# Select: 1,3,5  (comma-separated)
```

## 🛠️ Development

### Project Structure
```
goscrapper/
├── gofood.py                 # Main application
├── API_DOCUMENTATION.md      # Full API documentation
├── README.md                 # This file
├── requirements.txt          # Python dependencies
└── .env                       # Configuration (not in git)
```

### Key Functions
- `ambil_data_analytics()` - Main data collection
- `build_sheet_mapping()` - Google Sheet parsing & mapping
- `get_sheet_entry()` - Lookup outlet by phone/name
- `normalize_phone()` - Phone number normalization
- `normalize_name()` - Outlet name normalization

## 🐛 Troubleshooting

### Session Invalid
```
❌ Error: Sesi kedaluwarsa atau tidak valid.
→ Update BEARER_TOKEN in .env file
```

### File Locked
```
⚠️ File Excel terkunci atau terkorupsi
→ Close Excel file or delete and re-run
```

### No Store ID Found
```
⚠️ Outlet tidak punya Store ID yang terbaca dari sheet
→ Verify outlet exists in Google Sheet with Store ID
```

### Cannot Import to Google Sheets / File Corrupt in Google Drive
```
❌ Error saat membuka file `.xlsx` di Google Drive (Ikon biru/File corrupt/Tidak didukung)
→ Ini adalah efek samping dari library Python (`openpyxl`) yang menulis dan menimpa file berkali-kali untuk multi-akun, sehingga struktur file kadang ditolak oleh parser ketat Google Drive.
→ Solusi: Gunakan file `.csv` yang di-generate bersamaan. File CSV 100% aman, lebih ringan, datanya tetap lengkap, dan langsung terbaca oleh Google Sheets!
→ Cara Buka: Upload file `.csv` ke Google Drive, lalu buka dengan Google Sheets. Atau File → Import → Upload → Select .csv file
```

## 📝 Data Flow

```
Load .env (11 accounts)
    ↓
Fetch Google Sheet mapping
    ↓
Display available outlets
    ↓
User selection → all/specific
    ↓
For each outlet:
  - Get Store IDs from sheet
  - For each Store ID:
    - Set session
    - Fetch 5 data types
    - Aggregate & calculate
    ↓
Save Excel + CSV
    ↓
Display summary
```

## 📞 Support

- **Documentation**: See [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- **Issues**: Check error messages and troubleshooting section

## 📄 License

MIT License © 2026 Superfood Tech ID

---

**Last Updated:** May 11, 2026  
**Version:** 1.0.1
