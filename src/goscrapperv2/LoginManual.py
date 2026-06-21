import os
import re
import sys
import json
import time
import csv
import requests
from urllib.request import urlopen
from urllib.parse import urlparse, urlencode, urlunparse, parse_qsl
from dotenv import load_dotenv, set_key
from playwright.sync_api import sync_playwright


# Muat file .env jika ada
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(env_path)

# Master credential Google Sheet — sama dengan yang dipakai Grab & Shopee
MASTER_SHEET_URL = "https://docs.google.com/spreadsheets/d/14eCb8DAEXhmbYj9MFj2KzC7AhkulbCbSNPltN2m-go0/export?format=csv&gid=0"


def normalisasi_nomor_hp(nomor_hp):
    if not nomor_hp:
        return ""
    nomor_hp = str(nomor_hp).strip()
    if "@" in nomor_hp:
        return nomor_hp
    nomor_hp = re.sub(r'\D', '', nomor_hp)
    if nomor_hp.startswith("62"):
        return nomor_hp[2:]
    if nomor_hp.startswith("0"):
        return nomor_hp[1:]
    return nomor_hp


def fetch_gofood_outlets():
    """
    Mengambil semua outlet GoFood Live dari master Google Sheet.
    Mengembalikan list of dict:
      {
        'nama_outlet': str,
        'cabang'     : str,
        'email'      : str,   # kolom Y (index 24) — email login
        'phone'      : str,   # kolom AA (index 26) — nomor HP
        'store_id'   : str,
      }
    """
    try:
        import time
        cache_buster_url = MASTER_SHEET_URL + f"&t={int(time.time())}"
        resp = requests.get(cache_buster_url, timeout=30)
        resp.raise_for_status()
        reader_rows = list(csv.reader(resp.text.splitlines()))
    except Exception as e:
        print(f"❌ Gagal mengambil Google Sheet master: {e}")
        return []

    if not reader_rows:
        return []

    header = [str(h).strip().lower() for h in reader_rows[0]]

    def col_idx(names):
        for n in names:
            for i, h in enumerate(header):
                if n in h:
                    return i
        return None

    idx_aplikasi = col_idx(['aplikasi'])
    idx_status   = col_idx(['status'])
    idx_outlet   = col_idx(['nama outlet'])
    idx_cabang   = col_idx(['cabang'])
    idx_store    = col_idx(['store id', 'store_id', 'merchant id'])
    idx_email    = 24   # Kolom Y (0-indexed)
    idx_phone    = 26   # Kolom AA (0-indexed)

    outlets = []
    for row in reader_rows[1:]:
        if len(row) <= idx_phone:
            continue

        aplikasi = str(row[idx_aplikasi]).strip().lower() if idx_aplikasi is not None and len(row) > idx_aplikasi else ''
        status   = str(row[idx_status]).strip().lower()   if idx_status is not None and len(row) > idx_status else ''

        if 'gofood' not in aplikasi:
            continue
        if 'live' not in status:
            continue

        email    = str(row[idx_email]).strip() if len(row) > idx_email else ''
        phone    = str(row[idx_phone]).strip() if len(row) > idx_phone else ''
        nama     = str(row[idx_outlet]).strip() if idx_outlet is not None and len(row) > idx_outlet else ''
        cabang   = str(row[idx_cabang]).strip() if idx_cabang is not None and len(row) > idx_cabang else ''
        store_id = str(row[idx_store]).strip()  if idx_store is not None  and len(row) > idx_store  else ''

        outlets.append({
            'nama_outlet': nama,
            'cabang'     : cabang,
            'email'      : email,
            'phone'      : phone,
            'store_id'   : store_id,
        })

    return outlets


def ambil_otp_dari_endpoint(url_dasar, action="getOtp", label_email=None):
    """
    Mengambil OTP terbaru dari endpoint Google Apps Script atau langsung dari Google Sheets CSV.
    """
    if not url_dasar:
        raise ValueError("URL endpoint OTP kosong.")

    # Jika URL mengarah langsung ke Google Sheets CSV
    if "docs.google.com/spreadsheets" in url_dasar:
        try:
            with urlopen(url_dasar, timeout=30) as response:
                content = response.read().decode("utf-8").strip()
                lines = content.splitlines()
                if not lines or len(lines) < 2:
                    return ""
                reader = csv.reader(lines)
                rows = list(reader)
                headers = [h.strip().lower() for h in rows[0]]
                
                otp_idx = -1
                for idx, h in enumerate(headers):
                    if "otp" in h:
                        otp_idx = idx
                        break
                
                if otp_idx == -1:
                    otp_idx = 1 if len(rows[0]) > 1 else 0
                    
                last_row = rows[-1]
                if len(last_row) > otp_idx:
                    return last_row[otp_idx].strip()
                return ""
        except Exception as e:
            print(f"⚠️ Gagal membaca OTP dari Sheets: {e}")
            return ""

    parsed = urlparse(url_dasar)
    query_params = dict(parse_qsl(parsed.query))
    query_params["action"] = action
    if label_email:
        query_params["label"] = label_email
    url_final = urlunparse(parsed._replace(query=urlencode(query_params)))

    with urlopen(url_final, timeout=30) as response:
        return response.read().decode("utf-8").strip()


def tunggu_otp_terbaru(url_dasar, action="getOtp", label_email=None, timeout_detik=90, interval_detik=3):
    """
    Menunggu OTP terbaru yang berbeda dari nilai awal agar tidak memakai OTP sebelumnya.
    """
    try:
        otp_awal = ambil_otp_dari_endpoint(url_dasar, action=action, label_email=label_email)
    except Exception:
        otp_awal = ""
    
    batas_waktu = time.time() + timeout_detik
    print("🤖 Menunggu OTP baru masuk ke inbox...")

    while time.time() < batas_waktu:
        time.sleep(interval_detik)
        try:
            otp_baru = ambil_otp_dari_endpoint(url_dasar, action=action, label_email=label_email)
            if otp_baru and otp_baru != otp_awal:
                return otp_baru
        except Exception:
            pass

    return otp_awal





def login_outlet(outlet_info, proxy_config=None):
    """
    Membuka browser Chromium untuk login manual 1 outlet.
    Menunggu sampai access_token cookie terdeteksi.
    Mengembalikan dict session data, atau None jika gagal.
    """
    nama = outlet_info['nama_outlet']
    cabang = outlet_info.get('cabang', '')
    email = outlet_info.get('email', '')
    phone = outlet_info.get('phone', '')

    label = f"{nama} - {cabang}" if cabang else nama

    print(f"\n{'='*60}")
    print(f"  🔑 LOGIN: {label}")
    if email:
        print(f"  📧 Email: {email}")
    if phone:
        print(f"  📱 Phone: {phone}")
    print(f"{'='*60}")

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

        page = context.new_page()
        page.goto("https://portal.gofoodmerchant.co.id/", wait_until="networkidle")

        print("\n👉 Silakan tunggu, automasi sedang berjalan...")
        print("👉 Setelah masuk ke Dashboard, token akan otomatis ditangkap.\n")

        import random

        # --- STEP 1: Klik "Terima Semua Cookie" ---
        try:
            time.sleep(2)
            cookie_btn = page.locator('button:has-text("Terima Semua Cookie"), button:has-text("Accept All Cookies")')
            if cookie_btn.count() > 0:
                cookie_btn.first.click()
                print("   ✅ Klik 'Terima Semua Cookie'")
                time.sleep(1)
        except Exception:
            print("   ⚠️ Cookie popup tidak ditemukan, skip.")

        # --- STEP 2: Close popup "Perlu bantuan?" ---
        try:
            time.sleep(1)
            # Cari tombol close (X) pada popup bantuan
            close_btns = page.locator('[aria-label="close"], [aria-label="Close"], button.close, .dismiss-button, button[class*="close"]')
            if close_btns.count() > 0:
                close_btns.first.click()
                print("   ✅ Tutup popup bantuan")
                time.sleep(0.5)
            else:
                # Coba cari X text button di area bawah
                x_btn = page.locator('button:has-text("×"), button:has-text("✕")')
                if x_btn.count() > 0:
                    x_btn.first.click()
                    print("   ✅ Tutup popup bantuan (×)")
                    time.sleep(0.5)
        except Exception:
            pass

        # --- STEP 3: Klik "Masuk dengan email" ---
        if email:
            try:
                email_link = page.locator('text="Masuk dengan email"')
                if email_link.count() > 0:
                    email_link.first.click()
                    print("   ✅ Klik 'Masuk dengan email'")
                    time.sleep(2)
                else:
                    # Alternatif selector
                    email_link2 = page.locator('a:has-text("email"), button:has-text("email")')
                    if email_link2.count() > 0:
                        email_link2.first.click()
                        print("   ✅ Klik link email login")
                        time.sleep(2)
            except Exception as e:
                print(f"   ⚠️ Gagal klik 'Masuk dengan email': {e}")

            # --- STEP 4: Ketik email secara human-like ---
            try:
                email_input = page.wait_for_selector(
                    'input[type="email"], input[name="email"], input[placeholder*="email" i], input[placeholder*="Email" i]',
                    timeout=10000
                )
                if email_input:
                    email_input.click()
                    time.sleep(0.3)
                    # Ketik karakter satu per satu dengan delay random
                    for char in email:
                        email_input.type(char, delay=0)
                        time.sleep(random.uniform(0.05, 0.15))
                    print(f"   ✅ Email '{email}' diketik (human-like)")
                    time.sleep(0.5)

                    # Klik tombol Lanjut / Submit
                    submit_btn = page.locator('button:has-text("Lanjut"), button:has-text("Submit"), button:has-text("Masuk"), button[type="submit"]')
                    if submit_btn.count() > 0:
                        submit_btn.first.click()
                        print("   ✅ Klik tombol 'Lanjut'")
                    time.sleep(3)

                    # Jika ada halaman pilihan login (password/OTP)
                    try:
                        btn_otp = page.locator('button:has-text("Masuk dengan OTP"), a:has-text("Masuk dengan OTP")').first
                        if btn_otp.count() > 0 and btn_otp.is_visible():
                            btn_otp.click()
                            print("   ✅ Tombol 'Masuk dengan OTP' diklik. OTP telah dikirim.")
                            time.sleep(2)
                    except Exception:
                        pass

                    # --- STEP 5: Automated OTP Polling & Fill ---
                    otp_endpoint = os.getenv("OTP_ENDPOINT_URL")
                    if otp_endpoint:
                        try:
                            print("   🤖 Menunggu field OTP muncul...")
                            otp_input_selector = 'input[autocomplete="one-time-code"], input[aria-label*="digit" i], div[class*="otp" i] input, input[name*="otp" i], input[maxlength="1"]'
                            page.locator(otp_input_selector).first.wait_for(state="visible", timeout=15000)
                            time.sleep(2)
                            
                            print("   🤖 Mengambil OTP terbaru dari endpoint...")
                            label_email = os.getenv("GMAIL_OTP_LABEL", "OTP-GO")
                            action_type = "getOtpEmail" if email else "getOtp"
                            
                            otp_code = tunggu_otp_terbaru(otp_endpoint, action=action_type, label_email=label_email, timeout_detik=90, interval_detik=3)
                            
                            if otp_code and not (otp_code.isdigit() and len(otp_code) in (4, 6)):
                                print(f"   ⚠️ OTP dari endpoint bukan format angka valid: {otp_code[:50]}...")
                                otp_code = None
                                
                            if otp_code:
                                print(f"   🤖 OTP didapat: {otp_code}. Memasukkan OTP...")
                                otp_fields = page.locator(otp_input_selector).all()
                                if len(otp_fields) > 0:
                                    otp_fields[0].focus()
                                    time.sleep(0.5)
                                    otp_fields[0].type(otp_code, delay=300)
                                    print("   ✅ OTP berhasil diisi otomatis.")
                                    
                                    # Coba klik tombol submit/konfirmasi/masuk OTP
                                    time.sleep(1)
                                    submit_otp_btn = page.locator('button:has-text("Masuk"), button:has-text("Konfirmasi"), button:has-text("Verifikasi"), button:has-text("Lanjut"), button[type="submit"]')
                                    clicked = False
                                    for i in range(submit_otp_btn.count()):
                                        btn = submit_otp_btn.nth(i)
                                        if btn.is_visible() and btn.is_enabled():
                                            print(f"   🤖 Mengklik tombol OTP: '{btn.text_content().strip()}'")
                                            btn.click()
                                            clicked = True
                                            break
                                    if not clicked:
                                        print("   🤖 Mengirim Enter sebagai fallback...")
                                        page.keyboard.press("Enter")
                                    time.sleep(2)
                            else:
                                print("   ⚠️ Gagal mendapatkan OTP otomatis. Silakan isi manual di browser.")
                        except Exception as e:
                            print(f"   ⚠️ Gagal melakukan automasi OTP: {e}. Silakan isi manual.")
                    else:
                        print("   👉 Silakan isi kode OTP secara MANUAL di browser.")
            except Exception as e:
                print(f"   ⚠️ Gagal ketik email: {e}")




        access_token = None
        start_time = time.time()

        try:
            while True:
                if page.is_closed():
                    print("⚠️ Browser ditutup sebelum login selesai.")
                    break

                cookies = context.cookies()
                for cookie in cookies:
                    if cookie['name'] == 'access_token':
                        access_token = cookie['value']
                        break

                if access_token:
                    break

                time.sleep(1.0)

                if time.time() - start_time > 600:
                    print("❌ Timeout 10 menit.")
                    break

        except KeyboardInterrupt:
            print("\n⚠️ Dibatalkan oleh pengguna.")
        except Exception as e:
            print(f"❌ Error: {e}")

        result = None

        if access_token:
            print(f"🎉 LOGIN SUKSES untuk {label}!")

            # Fetch user profile
            user_data = None
            try:
                user_data = page.evaluate("""async (token) => {
                    try {
                        const res = await fetch("https://api.gobiz.co.id/v1/users/me", {
                            headers: {
                                "Authorization": "Bearer " + token,
                                "Authentication-Type": "go-id"
                            }
                        });
                        return await res.json();
                    } catch (e) { return null; }
                }""", access_token)
            except Exception:
                pass

            if user_data and "user" in user_data:
                user = user_data["user"]
                print(f"   👤 User: {user.get('full_name', '?')} | Phone: {user.get('phone', '?')}")

            # Ambil semua cookies & storage
            all_cookies = context.cookies()
            local_storage = {}
            session_storage = {}
            try:
                local_storage = page.evaluate("() => ({...localStorage})")
                session_storage = page.evaluate("() => ({...sessionStorage})")
            except Exception:
                pass

            result = {
                'access_token': access_token,
                'user_data': user_data,
                'cookies': all_cookies,
                'localStorage': local_storage,
                'sessionStorage': session_storage,
            }
        else:
            print(f"❌ Gagal mendapatkan token untuk {label}.")

        try:
            browser.close()
        except Exception:
            pass

        return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="GoFood Multi-Outlet Manual Login")
    parser.add_argument("--no-proxy", action="store_true", help="Nonaktifkan proxy/WARP")
    args_cli = parser.parse_args()

    print("=" * 60)
    print("  🔑 GOFOOD MULTI-OUTLET LOGIN (dari Google Sheet)  ")
    print("=" * 60)

    # Proxy config
    use_proxy = os.getenv("USE_PROXY", "false").lower() in ("true", "1", "yes")
    proxy_server = os.getenv("PROXY_SERVER")

    if args_cli.no_proxy:
        use_proxy = False
        print("🚫 Proxy dinonaktifkan.")

    proxy_config = None
    if use_proxy and proxy_server:
        print(f"🔄 Menggunakan proxy: {proxy_server}")
        parsed = urlparse(proxy_server)
        if parsed.username and parsed.password:
            server_url = f"{parsed.scheme}://{parsed.hostname}"
            if parsed.port:
                server_url += f":{parsed.port}"
            proxy_config = {"server": server_url, "username": parsed.username, "password": parsed.password}
        else:
            proxy_config = {"server": proxy_server}

    # Ambil daftar outlet dari Google Sheet
    print("\n📋 Mengambil daftar outlet GoFood dari Google Sheet...")
    outlets = fetch_gofood_outlets()

    if not outlets:
        print("❌ Tidak ada outlet GoFood Live yang ditemukan.")
        return

    # Filter hanya yang punya email
    outlets_with_email = [o for o in outlets if o['email'] and '@' in o['email']]

    if not outlets_with_email:
        print("❌ Tidak ada outlet GoFood dengan email kredensial yang tersedia.")
        return

    # Cek token yang sudah ada di .env
    existing_tokens = {}
    for key, value in os.environ.items():
        if key.startswith('BEARER_TOKEN_') and value:
            suffix = key[len('BEARER_TOKEN_'):]
            phone_part = suffix.split('_')[0]
            phone_norm = normalisasi_nomor_hp(phone_part)
            if phone_norm:
                existing_tokens[phone_norm] = True

    # Tampilkan daftar
    print(f"\n📋 Ditemukan {len(outlets_with_email)} outlet GoFood Live dengan email:\n")
    for i, o in enumerate(outlets_with_email, 1):
        phone_norm = normalisasi_nomor_hp(o['phone'])
        has_token = "✅ Sudah Login" if phone_norm in existing_tokens else "❌ Belum Login"
        cabang_str = f" - {o['cabang']}" if o['cabang'] else ""
        store_str = f" (Store: {o['store_id']})" if o['store_id'] else ""
        print(f"  [{i:2d}] {o['nama_outlet']}{cabang_str}{store_str}")
        print(f"       📧 {o['email']}  |  {has_token}")

    # Pilihan user
    print(f"\n  Pilih outlet untuk login (contoh: 1,3,5 atau 'all' atau 'new' untuk yang belum login):")
    pilihan = input("  Pilihan: ").strip().lower()

    selected = []
    if pilihan in ['all', 'semua']:
        selected = list(range(len(outlets_with_email)))
    elif pilihan == 'new':
        for i, o in enumerate(outlets_with_email):
            phone_norm = normalisasi_nomor_hp(o['phone'])
            if phone_norm not in existing_tokens:
                selected.append(i)
        if not selected:
            print("\n✅ Semua outlet sudah memiliki token login.")
            return
    else:
        for p in pilihan.split(','):
            p = p.strip()
            if p.isdigit():
                idx = int(p) - 1
                if 0 <= idx < len(outlets_with_email):
                    selected.append(idx)

    if not selected:
        print("⚠️ Tidak ada outlet yang dipilih.")
        return

    print(f"\n🚀 Akan login ke {len(selected)} outlet secara berurutan.\n")

    # Login satu per satu
    success_count = 0
    for seq, idx in enumerate(selected, 1):
        outlet = outlets_with_email[idx]
        print(f"\n[{seq}/{len(selected)}] ", end="")

        result = login_outlet(outlet, proxy_config)

        if result and result.get('access_token'):
            token = result['access_token']
            phone_norm = normalisasi_nomor_hp(outlet['phone'])
            sanitized_name = re.sub(r'[^a-zA-Z0-9]', '', outlet['nama_outlet'])
            suffix = f"_{phone_norm}_{sanitized_name}"

            # Simpan ke .env
            try:
                set_key(env_path, "BEARER_TOKEN", token)
                set_key(env_path, f"BEARER_TOKEN{suffix}", token)
                set_key(env_path, "ACTIVE_NOMOR_HP", phone_norm)
                set_key(env_path, f"NAMA_OUTLET{suffix}", outlet['nama_outlet'])
                if outlet['cabang']:
                    set_key(env_path, f"CABANG{suffix}", outlet['cabang'])
                if outlet['store_id']:
                    set_key(env_path, f"STORE_ID{suffix}", outlet['store_id'])

                print(f"   ✅ Token disimpan: BEARER_TOKEN{suffix}")
                success_count += 1
            except Exception as e:
                print(f"   ❌ Gagal simpan ke .env: {e}")
                print(f"   Token: {token[:50]}...")

            # Dump session JSON
            try:
                dump = {
                    'timestamp': time.time(),
                    'outlet': outlet,
                    'user': result.get('user_data'),
                    'cookies': result.get('cookies', []),
                    'localStorage': result.get('localStorage', {}),
                    'sessionStorage': result.get('sessionStorage', {}),
                }
                json_file = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    f"session_{phone_norm}.json"
                )
                with open(json_file, 'w') as f:
                    json.dump(dump, f, indent=4)
                print(f"   💾 Session dump: session_{phone_norm}.json")
            except Exception:
                pass

        if seq < len(selected):
            print(f"\n   ⏳ Lanjut ke outlet berikutnya dalam 2 detik...")
            time.sleep(2)

    # Summary
    print(f"\n{'='*60}")
    print(f"  ✅ SELESAI: {success_count}/{len(selected)} outlet berhasil login.")
    print(f"{'='*60}")
    print(f"\n  Jalankan 'uv run python gofood.py' untuk menarik data analytics.")


if __name__ == "__main__":
    main()
