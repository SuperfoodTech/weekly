# Google Sheet Integration Guide

## Overview

GoScrapper automatically integrates dengan Google Sheet yang di-publish untuk mapping antara phone numbers dan outlet information (nama, Store ID, cabang).

## Sheet Requirements

### Published Sheet URL Format

Sheet harus di-publish dengan setting:
- **File** → **Share** → **Publish to the web**
- Select sheet (default: gid=0)
- Publish as CSV

Contoh URL:
```
https://docs.google.com/spreadsheets/d/e/2PACX-1vRYSUnKOqk29LCktTxdb0wPLbWMbRaWRP3eC_UA4AwYod1FW6zDMhtLMC5ghIvot2B8upCDfBsn-TCP/pubhtml?gid=1789375209&single=true
```

### Required Columns

| Column | Position | Description | Example |
|--------|----------|-------------|---------|
| Nama Outlet | Any | Outlet/restaurant name | "Salero Minang Raya" |
| Store ID | Any | GoFood Store ID(s) | "G255151641" or "G255151641, G255151642" |
| Cabang | Any | Branch/location name | "Tanpa Cabang" or "Sudirman" |
| Aplikasi | Any | Platform filter | "GoFood" (rows with other values are filtered out) |
| Status | Any | Status filter | "Live" (only Live status rows included) |
| Phone Number | Column AA | Phone number for matching | "6285136517321" or "85136517321" |

### Column Position Mapping

GoScrapper automatically detects column positions by looking for column names:

```python
# Column AA (index 26): Phone numbers
aa_idx = 26

# Searched by name:
- "nama outlet" → outlet name
- "cabang" → branch name
- "store id" / "store_id" → Store ID (prioritized)
- "komisi" → ignored
- "status" → filter (must be "Live")
- "aplikasi" → filter (must be "GoFood")
```

## Sheet Structure Example

```
| Row | Nama Outlet | Store ID | Cabang | Aplikasi | Status | ... | Column AA (Phone) |
|-----|-------------|----------|--------|----------|--------|-----|-------------------|
| 1   | Nama Outlet | Store ID | Cabang | Aplikasi | Status | ... | (Header)          |
| 2   | Salero Minang | G255151641 | Tanpa | GoFood | Live | ... | 6285136517321     |
| 3   | Salero Minang | G255151641 | Tanpa | GoFood | Live | ... | 6285136517321     |
| 4   | Ayam Geprek | G123456789 | Sudirman | GoFood | Live | ... | 6285136517318     |
| 5   | Ayam Geprek | G987654321 | Gatot Subroto | GoFood | Live | ... | 6285136517318     |
| 6   | Restaurant | G111111111 | Bandung | Tokofood | Live | ... | 6285136517320     |
```

**Note:** Row 6 will be filtered out because Aplikasi ≠ "GoFood"

## Phone Number Matching

### Format Support

GoScrapper automatically normalizes phone numbers:

```
Input Format               → Normalized Format
62851 3651 7321          → 85136517321
+62 851 3651 7321        → 85136517321
6285136517321            → 85136517321
85136517321              → 85136517321
(851) 365-17321          → 85136517321
```

### Matching Algorithm

1. **Normalize** all phone numbers (remove non-digits, strip leading 62)
2. **Exact match** first: `normalized_sheet_phone == normalized_env_phone`
3. **Partial match** fallback: Check if one ends with the other
4. **Combination lookup**: Use `outlet_name|phone` as composite key

### Example Matching

```
.env Entry:
  BEARER_TOKEN_85136517321_salero=...

Sheet Entry:
  Phone: 6285136517321
  Name: Salero Minang Raya
  Store ID: G255151641

Match Result:
  ✅ Found! (after normalizing 6285136517321 → 85136517321)
  Outlet: Salero Minang Raya
  Store ID: G255151641
```

## Multi-Store ID Handling

If an outlet has multiple Store IDs, they can be stored in one cell or separate rows:

### Option 1: Multiple rows (recommended)
```
| Nama Outlet | Store ID | Phone |
|-------------|----------|-------|
| Ayam Geprek | G123456789 | 6285136517318 |
| Ayam Geprek | G987654321 | 6285136517318 |
| Ayam Geprek | G111222333 | 6285136517318 |
| Ayam Geprek | G444555666 | 6285136517318 |
```

Result: 4 Store IDs automatically grouped and listed as [4 Store ID]

### Option 2: Comma-separated (also supported)
```
| Nama Outlet | Store ID | Phone |
|-------------|----------|-------|
| Ayam Geprek | G123456789, G987654321, G111222333, G444555666 | 6285136517318 |
```

Result: Same - 4 Store IDs recognized

### Option 3: Mixed delimiters
Supported delimiters: `,` `;` `/` `\` `|`

```
Store ID: "G123456789; G987654321 / G111222333 | G444555666"
Result: 4 Store IDs
```

## Filtering Rules

### Aplikasi Filter
Only rows with `Aplikasi = "GoFood"` are processed:
```
Aplikasi: "GoFood"     → ✅ Included
Aplikasi: "Tokofood"   → ❌ Filtered out
Aplikasi: "gofood"     → ❌ Filtered out (case-sensitive)
Aplikasi: ""           → ✅ Included (empty = no filter)
```

### Status Filter
Only rows with `Status = "Live"` are processed:
```
Status: "Live"         → ✅ Included
Status: "live"         → ❌ Filtered out (case-sensitive)
Status: "Active"       → ❌ Filtered out
Status: ""             → ✅ Included (empty = no filter)
```

## Data Deduplication

GoScrapper automatically deduplicates Store IDs:

```
Sheet Data:
  Row 1: Store ID = "G255151641"
  Row 2: Store ID = "G255151641"  (duplicate)
  Row 3: Store ID = "G255151642"

Result: 2 unique Store IDs (G255151641, G255151642)
```

## Setting Up Your Sheet

### Step-by-Step

1. **Create Google Sheet** with your outlet data
2. **Add Headers** in first row
3. **Populate Data**:
   - Column A onwards: Outlet info
   - Column AA: Phone numbers
4. **Publish Sheet**:
   - File → Share → Publish to web
   - Select your sheet
   - Copy the URL
5. **Update Code** (if using custom URL):
   ```python
   SHEET_PUBLISHED_URL = 'your_published_url_here'
   ```
6. **Test**:
   ```bash
   python3 gofood.py
   # Should show: "Ditemukan X entri pada sheet untuk dicocokkan"
   ```

## Troubleshooting

### "Gagal mengambil sheet publik"
- ❌ Sheet not published
- ❌ Wrong URL
- ❌ Network error

**Solution:**
- Verify sheet is published (File → Share → Publish to web)
- Check URL format
- Test network connectivity

### "Tidak menemukan entri yang valid di sheet"
- ❌ Column AA is empty
- ❌ No "Nama Outlet" column

**Solution:**
- Verify Column AA contains phone numbers
- Add "Nama Outlet" column
- Check sheet has data rows

### "Outlet tidak punya Store ID"
- ❌ Store ID column not found
- ❌ Store ID value is empty

**Solution:**
- Add "Store ID" column
- Populate Store ID values
- Verify column name spelling

### Phone number not matching
- ❌ Format mismatch (e.g., 62 vs 85)
- ❌ Extra characters (spaces, dashes)

**Solution:**
- Use consistent format in both .env and sheet
- Remove extra characters from sheet
- GoScrapper will normalize automatically

## Best Practices

✅ **Do:**
- Use consistent phone number format in sheet
- Include all required columns
- Keep data updated
- Test publishing before running scraper
- Use "Live" status for active outlets

❌ **Don't:**
- Mix "GoFood" with "gofood" (case-sensitive)
- Leave Column AA empty
- Skip "Nama Outlet" column
- Duplicate Store IDs in same row
- Mix multiple phone formats inconsistently

## Example: Complete Sheet

```
A              | B          | C          | D       | E       | ... | AA
---------------|------------|------------|---------|---------|-----|----------
Nama Outlet    | Store ID   | Cabang     | Aplikasi| Status  | ... | Phone
Salero Minang  | G255151641 | Tanpa      | GoFood  | Live    | ... | 6285136517321
Ayam Geprek    | G123456789 | Sudirman   | GoFood  | Live    | ... | 6285136517318
Ayam Geprek    | G987654321 | Gatot      | GoFood  | Live    | ... | 6285136517318
Warung Bakaran | G111111111 | Bandung    | GoFood  | Live    | ... | 6285182003794
```

---

For API details, see [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
