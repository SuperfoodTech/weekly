import os
import argparse
import subprocess
import requests
import base64
from datetime import datetime
from dotenv import load_dotenv

def upload_to_drive_via_appscript(file_path, folder_id=""):
    load_dotenv()
    # Anda bisa meletakkan APPS_SCRIPT_URL di dalam file .env
    # Atau ganti langsung string di bawah ini jika tidak pakai .env
    apps_script_url = os.getenv("APPS_SCRIPT_URL", "https://script.google.com/macros/s/AKfycbxgoG5JkbJgNapXEWU59kTmFYvTAo2oUtdVyMqziSznQ9gLj7F1pN2gwdWQmKwIHQDP/exec")
    
    if not apps_script_url or apps_script_url == "ISI_DENGAN_URL_WEB_APP_APPS_SCRIPT_ANDA":
        print("❌ Error: APPS_SCRIPT_URL belum diatur. Silakan ganti URL di dalam script atau di file .env")
        return None

    try:
        file_name = os.path.basename(file_path)
        print(f"Mengunggah {file_name} via Apps Script...")
        
        # Baca file dan encode menggunakan base64 untuk menghindari masalah karakter
        with open(file_path, 'rb') as f:
            file_content = f.read()
            
        encoded_content = base64.b64encode(file_content).decode('utf-8')
        
        payload = {
            "filename": file_name,
            "content": encoded_content,
            "folderId": folder_id
        }
        
        # Kirim request POST ke endpoint Web App Apps Script
        response = requests.post(apps_script_url, json=payload, timeout=120)
        
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("status") == "success":
                print(f"✅ Berhasil diunggah! URL File: {res_json.get('url')} (ID: {res_json.get('fileId')})")
                return res_json.get('fileId')
            else:
                print(f"❌ Error dari Apps Script: {res_json.get('message')}")
        else:
            print(f"❌ HTTP Error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Koneksi Error: {e}")
        return None

def process_csv_pipeline(file_path=None, folder_id=""):
    """Fungsi ini dapat di-import dan dipanggil dari script lain"""
    if file_path is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        file_path = f"data_{date_str}.csv"
        
    if not os.path.exists(file_path):
        print(f"❌ File tidak ditemukan: {file_path}")
        return False
        
    # 1. Upload ke Drive via Apps Script
    upload_to_drive_via_appscript(file_path, folder_id)
    
    return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Upload CSV ke GDrive via Apps Script dan Push ke Git Master")
    parser.add_argument('--file', help="Path file CSV (opsional, jika tidak ada akan mencari format otomatis)")
    parser.add_argument('--folder-id', default="", help="ID Folder Google Drive (opsional)")
    
    args = parser.parse_args()
    process_csv_pipeline(args.file, args.folder_id)
