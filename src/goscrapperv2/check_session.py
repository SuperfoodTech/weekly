import os
import re
import sys
import json
import time
import glob
from urllib.parse import urlparse
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# Muat file .env jika ada
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(env_path)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="GoFood Session Restore Test")
    parser.add_argument("--no-proxy", action="store_true", help="Nonaktifkan proxy/WARP untuk sesi ini")
    args_cli = parser.parse_args()

    print("=" * 60)
    print("     🔄 GOFOOD SESSION RESTORE & TEST UTILITY 🔄     ")
    print("=" * 60)

    # 1. Cari berkas session JSON yang tersimpan
    active_hp = os.getenv("ACTIVE_NOMOR_HP")
    session_file = None

    if active_hp:
        target_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"session_{active_hp}.json")
        if os.path.exists(target_path):
            session_file = target_path

    # Jika tidak ditemukan lewat ACTIVE_NOMOR_HP, cari session_*.json secara umum
    if not session_file:
        files = glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "session_*.json"))
        if files:
            # Urutkan berdasarkan waktu modifikasi terbaru
            files.sort(key=os.path.getmtime, reverse=True)
            session_file = files[0]

    if not session_file:
        print("❌ Error: Tidak ada berkas session_*.json yang ditemukan!")
        print("   Silakan jalankan 'uv run python LoginManual.py' terlebih dahulu.")
        return

    print(f"📂 Menggunakan file sesi: {os.path.basename(session_file)}")
    
    # Load session data
    try:
        with open(session_file, 'r') as f:
            session_data = json.load(f)
    except Exception as e:
        print(f"❌ Gagal membaca berkas sesi: {e}")
        return

    # Cek konfigurasi proxy
    use_proxy = os.getenv("USE_PROXY", "false").lower() in ("true", "1", "yes")
    proxy_server = os.getenv("PROXY_SERVER")

    if args_cli.no_proxy:
        use_proxy = False
        print("🚫 Proxy/WARP dinonaktifkan via CLI argument.")

    proxy_config = None
    if use_proxy and proxy_server:
        print(f"🔄 Menggunakan proxy: {proxy_server}")
        parsed = urlparse(proxy_server)
        if parsed.username and parsed.password:
            server_url = f"{parsed.scheme}://{parsed.hostname}"
            if parsed.port:
                server_url += f":{parsed.port}"
            proxy_config = {
                "server": server_url,
                "username": parsed.username,
                "password": parsed.password
            }
        else:
            proxy_config = {
                "server": proxy_server
            }

    print("\nMembuka browser Chromium...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--no-sandbox'
            ]
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1366, 'height': 768},
            proxy=proxy_config
        )

        # 2. Inject Cookies
        cookies = session_data.get("cookies", [])
        if cookies:
            print(f"💉 Menyuntikkan {len(cookies)} cookies ke browser...")
            context.add_cookies(cookies)

        # 3. Inject localStorage & sessionStorage
        local_storage = session_data.get("localStorage", {})
        session_storage = session_data.get("sessionStorage", {})
        
        init_js = ""
        for k, v in local_storage.items():
            if isinstance(v, str):
                escaped_v = v.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
                init_js += f"localStorage.setItem('{k}', '{escaped_v}');\n"
        for k, v in session_storage.items():
            if isinstance(v, str):
                escaped_v = v.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
                init_js += f"sessionStorage.setItem('{k}', '{escaped_v}');\n"
        
        if init_js:
            print("💉 Menyuntikkan localStorage & sessionStorage...")
            context.add_init_script(init_js)

        page = context.new_page()
        
        # 4. Navigasi langsung ke Dashboard
        dashboard_url = "https://portal.gofoodmerchant.co.id/dashboard?date_range=today"
        print(f"🌐 Navigasi langsung ke: {dashboard_url}")
        
        try:
            page.goto(dashboard_url)
        except Exception as e:
            print(f"❌ Error saat memuat halaman: {e}")

        print("\n" + "=" * 70)
        print("✅ Browser berhasil direstore menggunakan sesi yang tersimpan!")
        print("👉 Silakan periksa apakah halaman langsung masuk ke Dashboard GoFood.")
        print("👉 Program akan menutup browser otomatis dalam 5 menit, atau")
        print("👉 Tekan Ctrl+C di terminal ini untuk menutup browser kapan saja.")
        print("=" * 70 + "\n")

        # Loop tunggu interaksi atau sampai browser ditutup manual
        try:
            for i in range(300, 0, -1):
                if page.is_closed():
                    print("🚪 Jendela browser telah ditutup manual oleh pengguna.")
                    break
                if i % 30 == 0:
                    print(f"⏳ Browser akan ditutup otomatis dalam {i} detik...")
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Menutup browser...")

        browser.close()

if __name__ == "__main__":
    main()
