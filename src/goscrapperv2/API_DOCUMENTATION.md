# GoScrapper - GoFood Analytics API Documentation

## Overview

**GoScrapper** adalah aplikasi Python yang mengintegrasikan dengan GoFood Merchant Portal untuk mengumpulkan dan menganalisis data penjualan multi-outlet. Aplikasi ini mendukung:

- Multi-account session management
- Per-outlet Store ID mapping dari published Google Sheet
- Scraping data analytics per Store ID/cabang
- Export hasil ke format Excel (.xlsx) dan CSV (.csv)
- Automatic Store ID deduplication dan normalisasi data
- Phone number normalization (support variasi format Indonesia)

---

## Installation & Setup

### Prerequisites
- Python 3.10+
- pip (Python package manager)

### Dependencies
```bash
pip install requests openpyxl python-dotenv
```

### Quick Start
```bash
# 1. Clone repository
git clone https://github.com/superfoodtechid/goscrapper.git
cd goscrapper

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure .env file (see Configuration section below)
cp .env.example .env
nano .env

# 4. Run application
python3 gofood.py
```

---

## Configuration

### Environment Variables (.env file)

#### Session Tokens
Multiple BEARER_TOKEN entries for multi-account support:
```
BEARER_TOKEN_{HP}_{UNIQUE_ID}=your_bearer_token_here
```

**Example:**
```env
BEARER_TOKEN_85136517321_salero_minang=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
BEARER_TOKEN_85136517318_ayam_geprek=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Outlet Information
```
NAMA_OUTLET_{HP}_{UNIQUE_ID}=Outlet Name
CABANG_{HP}_{UNIQUE_ID}=Branch Name
```

**Example:**
```env
NAMA_OUTLET_85136517321_salero_minang=Salero Minang Raya
CABANG_85136517321_salero_minang=Tanpa Cabang
```

#### Google Sheet Configuration
The application automatically fetches outlet-to-Store ID mapping from a published Google Sheet. The sheet must contain:
- **Column AA**: Phone numbers (format: 62xxxxx or 85xxxxx)
- **Column with "Nama Outlet"**: Outlet names
- **Column with "Store ID"**: Store IDs (can have multiple per outlet)
- **Column with "Cabang"**: Branch names
- **Column with "Aplikasi"**: Must be "GoFood"
- **Column with "Status"**: Must be "Live"

---

## Core Functions

### Data Fetching

#### `ambil_data_analytics(write_header=True, start_date=None, end_date=None)`
Main function to fetch and process analytics data from GoFood Portal.

**Parameters:**
- `write_header` (bool): Whether to create new Excel file with headers. Default: `True`
- `start_date` (datetime): Custom start date. If None, uses default 3 months back
- `end_date` (datetime): Custom end date. If None, uses default 3 months back

**Data Fetched:**
1. **Revenue Data** (Gross omzet)
   - Endpoint: `/analytics-backend/api/datasources/proxy/63/_msearch`
   - Panel ID: 2
   
2. **Orders Data** (Jumlah pesanan)
   - Endpoint: `/analytics-backend/api/datasources/proxy/46/_msearch`
   - Includes completed and cancelled orders
   
3. **Net Revenue** (Omzet bersih setelah potongan)
   - Endpoint: `/analytics-backend/api/datasources/proxy/63/_msearch`
   - Panel ID: 7
   
4. **Commission Data** (Biaya komisi)
   - Endpoint: `/analytics-backend/api/datasources/proxy/63/_msearch`
   - Panel ID: 4
   
5. **Cancelled Orders** (Order batal)
   - Endpoint: `/analytics-backend/api/datasources/proxy/46/_msearch`
   - Panel ID: 42

**Output:**
- Excel file: `revenue_{start_date}_sampai_{end_date}.xlsx` atau `revenue_3_bulan.xlsx`
- CSV file: `revenue_{start_date}_sampai_{end_date}.csv` atau `revenue_3_bulan.csv`

#### `ambil_data_dashboard()`
Validates current session by fetching user information.

**Returns:**
- `True`: Session valid
- `False`: Session invalid or expired

**API Endpoint:**
```
GET https://api.gobiz.co.id/v1/users/me
Header: Authorization: Bearer {BEARER_TOKEN}
```

### Sheet Mapping Functions

#### `build_sheet_mapping(rows)`
Builds phone-to-outlet and name-to-outlet mapping from Google Sheet data.

**Parameters:**
- `rows`: CSV rows from published sheet

**Returns:**
```python
{
    'by_phone': {
        '85136517321': {
            'name': 'Salero Minang Raya',
            'store_ids': [
                {'id': 'G255151641', 'cabang': 'Tanpa Cabang'},
                ...
            ]
        }
    },
    'by_name': {
        'salero minang raya|85136517321': {...}
    }
}
```

#### `get_sheet_entry(mapping, num, current_name=None)`
Retrieves outlet information from mapping by phone number or name.

**Parameters:**
- `mapping`: Result from `build_sheet_mapping()`
- `num`: Phone number
- `current_name`: Optional outlet name for name|phone lookup

**Returns:**
```python
{
    'name': 'Outlet Name',
    'store_ids': [
        {'id': 'STORE_ID_1', 'cabang': 'Branch 1'},
        {'id': 'STORE_ID_2', 'cabang': 'Branch 2'}
    ]
}
```

### Utility Functions

#### `normalize_phone(s)`
Normalizes phone number by stripping non-digits and removing leading country code.

**Examples:**
```python
normalize_phone('6285136517321')  # → '85136517321'
normalize_phone('+62 851 3651 7321')  # → '85136517321'
normalize_phone('85136517321')  # → '85136517321'
```

#### `normalize_name(s)`
Normalizes outlet name to lowercase and removes extra whitespace.

**Examples:**
```python
normalize_name('  Salero Minang Raya  ')  # → 'salero minang raya'
normalize_name('AYAM GEPREK')  # → 'ayam geprek'
```

---

## Output Format

### Excel File Structure
| Nomor HP | Outlet Name | Store ID | Tanggal | Penjualan Kotor | Biaya Komisi | ... | Total Order |
|----------|-------------|----------|---------|-----------------|--------------|-----|-------------|
| 85136517321 | Salero Minang Raya | G255151641 | 2026-05-01 | 500000 | 25000 | ... | 15 |
| 85136517321 | Salero Minang Raya | G255151641 | 2026-05-02 | 600000 | 30000 | ... | 18 |

### Columns Description

| Column | Description |
|--------|-------------|
| Nomor HP | Phone number from .env |
| Outlet Name | Outlet name (from Google Sheet) |
| Store ID | Merchant Store ID (from Google Sheet) |
| Tanggal | Date (YYYY-MM-DD or DD MMM YYYY) |
| Penjualan Kotor | Gross revenue before deductions |
| Biaya Komisi | Commission fee charged |
| Pengeluaran Iklan & Diskon | Advertising & discount spending |
| Total Potongan Ojol | Ojol/delivery commission deduction |
| Penjualan Bersih | Net revenue after all deductions |
| Rata-Rata Order per Cust | Average order value per customer |
| Order Sukses | Successful orders |
| Order Batal | Cancelled orders |
| Total Order | Total orders (successful + cancelled) |

---

## API Endpoints Used

### GoFood Portal Analytics API

**Base URL:** `https://portal.gofoodmerchant.co.id/analytics-backend/api`

#### 1. Revenue Data
```
POST /datasources/proxy/63/_msearch
```

**Headers:**
- `Authentication-Type: go-id`
- `Authorization: Bearer {token}`
- `x-panel-id: 2` (for gross revenue)
- `x-range-from: {epoch_ms}`
- `x-range-to: {epoch_ms}`

**Query Parameters:**
- `merchant_ids`: Store ID (if available)

#### 2. Orders Data
```
POST /datasources/proxy/46/_msearch
```

**Headers:**
- `x-panel-id: 38` (for orders summary)
- `x-range-from: {epoch_ms}`
- `x-range-to: {epoch_ms}`

**Payload:** Elasticsearch query with date histogram aggregation

#### 3. Net Revenue
```
POST /datasources/proxy/63/_msearch
```

**Headers:**
- `x-panel-id: 7` (for net revenue/bottomline)

#### 4. Commission
```
POST /datasources/proxy/63/_msearch
```

**Headers:**
- `x-panel-id: 4` (for commission amount)

#### 5. Cancelled Orders
```
POST /datasources/proxy/46/_msearch
```

**Headers:**
- `x-panel-id: 42` (for cancelled orders)

### User Validation API

```
GET https://api.gobiz.co.id/v1/users/me
```

**Response:**
```json
{
    "user": {
        "full_name": "Nama Pengguna",
        "phone_number": "85136517321",
        ...
    }
}
```

---

## Usage Examples

### Example 1: Basic Usage (Default 3 months)
```bash
python3 gofood.py
```

**Output:**
```
Mencari akun yang tersimpan di file .env...
Ditemukan 11 akun untuk diproses.

Daftar Cabang yang tersedia (dari sesi aktif):
[1] Salero Minang Raya - Tanpa Cabang (85136517321)
[2] Ayam Geprek Suroboyo Ampel [4 Store ID] - Tanpa Cabang (85136517318)
...

Pilih nomor urut cabang yang ingin ditarik datanya: all

✅ Berhasil mengambil data Revenue dari 01 Feb 2026 hingga 11 May 2026
✅ Berhasil menyimpan data ke:
   /mnt/DATA/Proyek/Agency/gofood v2/revenue_3_bulan.xlsx (Format Vertikal)
✅ Juga di-export ke CSV (untuk Google Sheets):
   /mnt/DATA/Proyek/Agency/gofood v2/revenue_3_bulan.csv
```

### Example 2: Custom Date Range
```bash
python3 gofood.py
# When prompted:
# Gunakan range tanggal custom? (y/n): y
# Masukkan tanggal mulai (format YYYY-MM-DD): 2026-05-01
# Masukkan tanggal akhir (format YYYY-MM-DD): 2026-05-10
```

### Example 3: Select Specific Outlets
```bash
python3 gofood.py
# When prompted:
# Pilih nomor urut cabang: 1,3,5
# ✅ Melanjutkan penarikan data untuk 3 cabang pilihan.
```

---

## Data Processing Flow

```
┌─────────────────────────────────────┐
│  Read .env configuration            │
│  Load BEARER_TOKEN_* entries        │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Fetch Google Sheet mapping         │
│  - Normalize phone numbers          │
│  - Group by outlet + phone combo    │
│  - Filter: Aplikasi=GoFood          │
│  - Filter: Status=Live              │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Display available outlets/cabang   │
│  Allow user selection               │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  For each selected outlet:          │
│  - Get all Store IDs                │
│  - Loop each Store ID               │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  For each Store ID:                 │
│  - Set ACTIVE_STORE_ID env var      │
│  - Validate session (ambil_data...  │
│  - Fetch 5 data types:              │
│    • Revenue                        │
│    • Orders                         │
│    • Net Revenue                    │
│    • Commission                     │
│    • Cancelled Orders               │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Parse & aggregate data             │
│  Calculate totals & averages        │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Save results:                      │
│  - Excel (.xlsx) file               │
│  - CSV (.csv) file                  │
└─────────────────────────────────────┘
```

---

## Error Handling

### Common Issues & Solutions

#### 1. Session Invalid/Expired
**Error:** `❌ Gagal: Sesi kedaluwarsa atau tidak valid.`

**Solution:**
```bash
# Run OTP login to get new token
python3 otp_receiver.py  # (if available)
# Or manually update BEARER_TOKEN in .env
```

#### 2. File Locked/Corrupted
**Error:** `⚠️ File Excel terkunci atau terkorupsi`

**Solution:**
- Close the Excel file if open
- Or delete and re-run the script to create new file

#### 3. Google Sheet Not Found
**Error:** `Peringatan: Gagal mengambil sheet publik untuk pencocokan`

**Solution:**
- Verify SHEET_PUBLISHED_URL in code is correct
- Ensure sheet is published and accessible
- Check network connection

#### 4. No Store ID in Sheet
**Warning:** `⚠️ Outlet {name} tidak punya Store ID yang terbaca dari sheet.`

**Solution:**
- Verify outlet exists in Google Sheet
- Check if "Store ID" column exists and is populated

---

## Advanced Configuration

### Custom Sheet URL
Edit `SHEET_PUBLISHED_URL` in `gofood.py`:
```python
SHEET_PUBLISHED_URL = 'https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/pubhtml?gid=0&single=true'
```

### Date Range Customization
Modify date range logic in `ambil_data_analytics()`:
```python
# Default: 3 months back
# Custom: User input during runtime
```

### Store ID Filtering
Adjust Store ID column detection in `build_sheet_mapping()`:
```python
# Currently matches: "store id", "store_id", or contains "store"/"merchant"
# Excludes: "merchant id", "merchant name"
```

---

## Performance Notes

- **Typical runtime:** 30-60 seconds per Store ID (depends on data volume)
- **Network:** Requires stable internet connection
- **Memory:** Minimal (~50MB)
- **Storage:** Each export is ~50KB-500KB depending on data size

---

## Support & Troubleshooting

For issues or questions:
1. Check error messages in terminal output
2. Verify .env configuration
3. Check network connectivity
4. Review API responses in debug output
5. Ensure Google Sheet is accessible and properly formatted

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-11 | Initial release with multi-outlet, per-Store ID, CSV export support |

---

## License

© 2026 Superfood Tech ID. All rights reserved.
