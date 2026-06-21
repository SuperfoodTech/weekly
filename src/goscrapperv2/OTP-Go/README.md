# OTP-Go: Gmail to Google Sheets Forwarder

Proyek ini adalah sistem otomatis untuk memantau email masuk (khususnya OTP) dari Gmail dan meneruskannya ke Google Sheets secara real-time menggunakan Python dan Google Apps Script.

## 🛠️ Cara Kerja
1.  **Python Script (`OTP.py`)**: Berjalan di komputer lokal/server, memantau Gmail API setiap 5 detik untuk mencari email terbaru dari pengirim tertentu (contoh: "Gojek untuk Mitra Usaha").
2.  **Extraction**: Mengambil kode OTP (4-6 digit) dari isi email menggunakan Regex.
3.  **Webhook**: Mengirimkan data OTP tersebut ke Google Apps Script melalui metode HTTP POST.
4.  **Google Apps Script (`OTP.gs`)**: Berfungsi sebagai Web App (Webhook) yang menerima data dari Python dan menuliskannya ke tab tertentu di Google Sheets.

## 📂 Struktur File
*   `OTP.py`: Script utama Python untuk monitoring Gmail.
*   `OTP.gs`: Kode JavaScript untuk di pasang di Extensions > Apps Script pada Google Sheets.
*   `credentials.json`: Kredensial dari Google Cloud Console (wajib ada untuk akses API).
*   `token.pickle`: Menyimpan sesi login Google agar tidak perlu login berulang kali.
*   `.venv/`: Virtual environment Python.

## 🚀 Panduan Instalasi

### 1. Persiapan Google Sheets (Apps Script)
1.  Buka Google Sheets Anda.
2.  Buat tab baru dengan nama **`OTP-GO`**.
3.  Pilih menu **Extensions** > **Apps Script**.
4.  Hapus kode yang ada, lalu salin isi file `OTP.gs` ke editor tersebut.
5.  Klik **Deploy** > **New Deployment**.
    *   Select type: **Web App**
    *   Execute as: **Me**
    *   Who has access: **Anyone**
6.  Salin **Web App URL** yang muncul (Anda akan membutuhkannya untuk script Python).

### 2. Persiapan Python (Local)
1.  Pastikan Anda memiliki file `credentials.json` di folder proyek.
2.  Aktifkan virtual environment:
    ```bash
    source .venv/bin/activate
    ```
3.  Install dependensi jika belum:
    ```bash
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib requests rich
    ```
4.  Buka `OTP.py` dan pastikan variabel `WEB_APP_URL` sudah berisi URL dari langkah pertama tadi.

## 🏃 Cara Menjalankan
Cukup jalankan perintah berikut di terminal:
```bash
python OTP.py
```
Saat pertama kali dijalankan, browser akan terbuka untuk meminta izin akses Gmail. Setelah berhasil, file `token.pickle` akan terbuat secara otomatis.

## ⚠️ Catatan Penting
*   **Update Deployment**: Setiap kali Anda mengubah kode di `OTP.gs`, Anda **harus** melakukan "New Deployment" agar perubahan tersebut aktif di URL Web App.
*   **Keamanan**: Jangan pernah membagikan file `credentials.json` atau `token.pickle` kepada orang lain karena berisi akses ke email Anda.
*   **Nama Tab**: Jika Anda ingin mengganti nama tab di Google Sheets, pastikan variabel `SHEET_NAME` di file `OTP.gs` juga diganti agar sesuai.

---
**Dibuat oleh:** Antigravity AI Assistant.
