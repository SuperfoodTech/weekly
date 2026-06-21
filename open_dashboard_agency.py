import os
import sys
import time
from pathlib import Path

# Add agency directory to path so core/ imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'agency')))

from core.browser import _init_driver, load_session
from core.logger import get_logger

log = get_logger("open_dashboard_agency")

def main():
    print("🚀 Membuka browser Shopee Partner Portal untuk Agency...")
    try:
        driver = _init_driver(headless=False)
        driver.get("https://partner.shopee.co.id/")
        time.sleep(2)
        
        # Load saved session cookies if they exist
        saved = load_session()
        if saved:
            log.info("🔑 Memasukkan cookie sesi tersimpan untuk Agency...")
            try:
                driver.add_cookie({"name": "shopee_tob_token", "value": saved["shopee_tob_token"]})
                if saved.get("shopee_tob_entity_id"):
                    driver.add_cookie({"name": "shopee_tob_entity_id", "value": saved["shopee_tob_entity_id"]})
                for n, v in saved.get("extra_cookies", {}).items():
                    try:
                        driver.add_cookie({"name": n, "value": v})
                    except:
                        pass
            except Exception as cookie_err:
                log.warning(f"⚠️ Gagal menambahkan sebagian cookie: {cookie_err}")
            
            driver.get("https://partner.shopee.co.id/food/dashboard")
        else:
            log.warning("⚠️ Sesi tidak ditemukan. Silakan login manual.")
            driver.get("https://partner.shopee.co.id/login")

        print("\n" + "="*60)
        print("🚀 Browser untuk Agency Shopee telah dibuka!")
        print("Tekan Ctrl+C di terminal ini atau tutup jendela browser untuk mengakhiri.")
        print("="*60 + "\n")

        while True:
            time.sleep(2)
            # Check if browser is still open
            _ = driver.current_url

    except KeyboardInterrupt:
        print("\n🛑 Dihentikan oleh pengguna.")
    except Exception as e:
        log.error(f"❌ Terjadi kesalahan: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass
        print("✅ Selesai.")

if __name__ == "__main__":
    main()
