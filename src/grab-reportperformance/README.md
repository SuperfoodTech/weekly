# Grab 90 Days Scraper

Script ini digunakan untuk login ke Grab Merchant, mengambil data transaksi 3 bulan terakhir, lalu menghitung ringkasan bulanan:

- Omzet per bulan berdasarkan kolom `Net Sales`
- Jumlah order per bulan berdasarkan `Long Order ID`
- Hanya data valid yang memiliki `Long Order ID` dan `Net Sales` secara bersamaan
- Hasil ringkasan diekspor ke file Excel

## Struktur file

- `grab_performance_scraper.py` — otomatisasi login dan download data dari Grab Merchant
- `result.py` — olah data CSV menjadi ringkasan bulanan
- `credential.csv` — kredensial login, jangan diunggah ke GitHub
- `downloads/` — folder hasil unduhan dari scraper
- `monthly_summary_wide.xlsx` — hasil ringkasan final di folder utama project

## Kebutuhan

- Python 3.12+
- Playwright
- pandas
- openpyxl

## Instalasi

```bash
pip install -r requirements.txt
pip install pandas openpyxl
playwright install
```

## Cara menjalankan scraper

Jalankan file berikut untuk mengunduh data transaksi:

```bash
python grab_performance_scraper.py
```

Hasil unduhan akan tersimpan di folder `downloads/`.

## Cara membuat ringkasan bulanan

Jalankan:

```bash
python result.py
```

File output akan dibuat di folder utama project sebagai:

```bash
monthly_summary_wide.xlsx
```

## Format hasil

File Excel dibuat dengan format seperti tabel spreadsheet:

- Omzet Bulan ke-1
- Omzet Bulan ke-2
- Omzet Bulan ke-3
- Order Bulan ke-1
- Order Bulan ke-2
- Order Bulan ke-3

## Catatan

- `credential.csv` sebaiknya tetap privat dan tidak dimasukkan ke GitHub
- Folder `downloads/` berisi file hasil unduhan dan akan diabaikan oleh Git
- Ringkasan hanya menghitung data valid dengan pasangan `Long Order ID` dan `Net Sales`
