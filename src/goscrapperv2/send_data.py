import openpyxl
import requests
import os
import glob

# URL Web App Google Apps Script
WEB_APP_URL = 'https://script.google.com/macros/s/AKfycbwQHzEy_cNW_N81YwSKcnZrgWvUvc_0bD_iMw1ADUXrdwJ4Y11q0Pj-nDbWkpn9BL2IKQ/exec'

# Nama sheet tujuan di Google Sheet
SHEET_NAME = 'Gofood'

# Path folder laporan GoFood (relatif terhadap lokasi file ini)
RAW_BASE_DIR = os.path.join(os.path.dirname(__file__), '..', 'laporan', 'gofood')

# Urutan kolom yang dikirim ke GSheet (harus sesuai header di sheet GAS)
# GAS auto-buat header: Tanggal | Outlet Name | Store ID | Penjualan Kotor |
#                        Biaya Komisi | Pengeluaran Iklan & Diskon | Order Sukses | Order Batal
#
# Mapping dari kolom Excel raw (8 kolom, 0-indexed):
#  0  Tanggal           → kolom ke-1
#  1  Outlet Name       → kolom ke-2
#  2  Store ID          → kolom ke-3
#  3  Penjualan Kotor   → kolom ke-4
#  4  Biaya Komisi      → kolom ke-5
#  5  Pengeluaran Iklan & Diskon → kolom ke-6
#  6  Order Sukses      → kolom ke-7
#  7  Order Batal       → kolom ke-8


def get_folder_for_range(start_date: str, end_date: str) -> str:
    """Mengembalikan path folder raw untuk rentang tanggal yang diberikan."""
    folder_name = f"{start_date}_to_{end_date}"
    return os.path.join(RAW_BASE_DIR, folder_name)


def baca_file(excel_path: str) -> list:
    """Membaca satu file .xlsx dan mengembalikan list of rows (array of arrays).
    Setiap row = [Tanggal, Outlet Name, Store ID, Penjualan Kotor,
                  Biaya Komisi, Pengeluaran Iklan, Order Sukses, Order Batal]
    """
    try:
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    except Exception as e:
        print(f"  ❌ Gagal membaca file: {e}")
        return []

    if len(rows) < 2:
        print(f"  ⚠️  File kosong atau hanya header, dilewati.")
        return []

    result = []
    for i in range(1, len(rows)):
        raw = ["" if x is None else x for x in rows[i]]

        if len(raw) < 8:
            print(f"  ⚠️  Baris {i+1} dilewati — hanya {len(raw)} kolom (butuh 8).")
            continue

        tanggal         = str(raw[0])
        outlet_name     = raw[1]
        store_id        = raw[2]
        penjualan_kotor = raw[3]
        biaya_komisi    = raw[4]
        iklan_diskon    = raw[5]
        order_sukses    = raw[6]
        order_batal     = raw[7]

        # Lewati baris jika SEMUA kolom finansial & order bernilai 0 atau kosong
        kolom_data = [penjualan_kotor, biaya_komisi, iklan_diskon, order_sukses, order_batal]
        if all(v == 0 or v == "" for v in kolom_data):
            continue

        result.append([
            tanggal,
            outlet_name,
            store_id,
            penjualan_kotor,
            biaya_komisi,
            iklan_diskon,
            order_sukses,
            order_batal,
        ])

    return result


def kirim_batch(data_rows: list, sheet_name: str = SHEET_NAME) -> bool:
    """Mengirim semua baris sekaligus ke GSheet dalam satu POST request."""
    payload = {
        "sheetName": sheet_name,
        "data": data_rows,
    }
    try:
        response = requests.post(WEB_APP_URL, json=payload, timeout=120)
        res_json = response.json()
        if res_json.get("status") == "success":
            print(f"  ✅ {res_json.get('message')}")
            return True
        else:
            print(f"  ❌ Error dari GAS: {res_json.get('message')}")
            return False
    except Exception as e:
        print(f"  ❌ Gagal kirim ke GSheet: {e}")
        return False


def kirim_ke_google_sheet(start_date: str = None, end_date: str = None,
                           sheet_name: str = SHEET_NAME):
    """Membaca semua file .xlsx dari folder raw dan mengirimnya ke GSheet dalam satu batch.

    Args:
        start_date: Tanggal mulai format YYYY-MM-DD, misal '2026-06-15'.
                    Jika None, proses semua folder raw yang tersedia.
        end_date:   Tanggal akhir format YYYY-MM-DD, misal '2026-06-21'.
        sheet_name: Nama sheet tujuan di Google Spreadsheet (default: 'Gofood').
    """
    if start_date and end_date:
        folder = get_folder_for_range(start_date, end_date)
        if not os.path.isdir(folder):
            print(f"❌ Folder tidak ditemukan: {folder}")
            return
        folders = [folder]
    else:
        raw_abs = os.path.abspath(RAW_BASE_DIR)
        if not os.path.isdir(raw_abs):
            print(f"❌ Direktori raw tidak ditemukan: {raw_abs}")
            return
        folders = sorted([
            os.path.join(raw_abs, d)
            for d in os.listdir(raw_abs)
            if os.path.isdir(os.path.join(raw_abs, d))
        ])
        if not folders:
            print("❌ Tidak ada folder data ditemukan di direktori raw.")
            return

    all_rows = []
    total_files = 0

    for folder in folders:
        print(f"\n📂 Memproses folder: {os.path.basename(folder)}")
        xlsx_files = sorted(glob.glob(os.path.join(folder, "*.xlsx")))

        if not xlsx_files:
            print("  ⚠️  Tidak ada file .xlsx ditemukan.")
            continue

        print(f"  Ditemukan {len(xlsx_files)} file.")
        for xlsx_path in xlsx_files:
            filename = os.path.basename(xlsx_path)
            rows = baca_file(xlsx_path)
            print(f"  📄 {filename} → {len(rows)} baris")
            all_rows.extend(rows)
            total_files += 1

    if not all_rows:
        print("\n❌ Tidak ada data yang bisa dikirim.")
        return

    print(f"\n📤 Mengirim total {len(all_rows)} baris ke sheet '{sheet_name}'...")
    kirim_batch(all_rows, sheet_name=sheet_name)

    print(f"\n{'='*60}")
    print(f"✅ Selesai! Total {len(all_rows)} baris dari {total_files} file.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import sys

    # Usage:
    #   python send_data.py                          → semua folder raw
    #   python send_data.py 2026-06-15 2026-06-21   → folder rentang tertentu
    #   python send_data.py 2026-06-15 2026-06-21 MySheet → sheet custom

    if len(sys.argv) >= 3:
        _start = sys.argv[1]
        _end   = sys.argv[2]
        _sheet = sys.argv[3] if len(sys.argv) >= 4 else SHEET_NAME
        kirim_ke_google_sheet(start_date=_start, end_date=_end, sheet_name=_sheet)
    else:
        kirim_ke_google_sheet()
