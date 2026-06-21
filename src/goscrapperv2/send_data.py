import openpyxl
import requests
import os

def kirim_ke_google_sheet():
    """Membaca revenue_3_bulan.xlsx dan mengirimnya via POST request ke Web App Google Apps Script."""
    EXCEL_FILE = 'revenue_3_bulan.xlsx'
    
    # TENTUKAN KONFIGURASI DI BAWAH INI:
    # 1. Ganti dengan URL hasil Deploy "Web App" dari Google Apps Script Anda.
    WEB_APP_URL = 'https://script.google.com/macros/s/AKfycbwZ4IZFUKjAjiVQTLFhxQGZAli66qBRUXcq_6rVaGm1d4BLgs_0fq2eKyCBCByFFr6a/exec' 
    
    print(f"\nMembaca data dari {EXCEL_FILE}...")
    
    if not os.path.exists(EXCEL_FILE):
        print(f"❌ File {EXCEL_FILE} tidak ditemukan.")
        return
    
    try:
        wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        
        if len(rows) < 2:
            print("❌ File Excel tidak memiliki baris data yang cukup.")
            return
            
        print(f"Ditemukan {len(rows) - 1} data user di dalam file Excel untuk dikirim.\n")
        
        for i in range(1, len(rows)):
            # Ganti nilai None di cell kosong menjadi string ""
            row = ["" if x is None else x for x in rows[i]]
            if len(row) < 13: # Sesuai dengan format 13 kolom yang baru
                continue
                
            USERNAME = row[0]
            
            print(f"Mengirim data untuk user: '{USERNAME}' (Tanggal: {row[3]})...")
                
            payload = {
                "nomor_hp": row[0],
                "nama_outlet": row[1],
                "store_id": row[2],
                "tanggal": row[3],
                "penjualan_kotor": row[4],
                "biaya_komisi": row[5],
                "pengeluaran_iklan": row[6],
                "total_potongan_ojol": row[7],
                "penjualan_bersih": row[8],
                "rata_rata_order_per_cust": row[9],
                "order_sukses": row[10],
                "order_batal": row[11],
                "total_order": row[12]
            }
                
            try:
                response = requests.post(WEB_APP_URL, json=payload)
                print(f"Respons server: {response.text}\n")
            except Exception as e:
                print(f"❌ Terjadi error saat mengirim HTTP request untuk user {USERNAME}: {e}\n")
                    
    except Exception as e:
        print(f"❌ Gagal membaca CSV: {e}")
        return

if __name__ == "__main__":
    kirim_ke_google_sheet()
