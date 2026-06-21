import os
import sys
import time
import threading
import json
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Add VB directory to path so core/ imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'VB')))

from core.browser import _init_driver, load_session
from core.logger import get_logger

log = get_logger("open_dashboards_vb")

portals = ["portal_f", "portal_w", "portal_l", "portal_d"]
drivers = {}

def get_credentials(account_name):
    try:
        cred_path = Path(__file__).resolve().parent / "VB" / "shopee" / "credentials_vb.json"
        if cred_path.exists():
            with open(cred_path, "r") as f:
                data = json.load(f)
                for portal in data.get("portals", []):
                    if portal.get("account_name") == account_name:
                        return portal
    except Exception as e:
        log.warning(f"⚠️ Gagal membaca credentials_vb.json: {e}")
    return None

def autofill_login_form(driver, cred, name):
    log.info(f"✍️ Mengisi otomatis username & password untuk VB '{name}'...")
    try:
        wait = WebDriverWait(driver, 10)
        user_input = None
        for sel in ["input[name='userName']", "input[placeholder*='handphone']", "input[placeholder*='Username']", "input[type='text']"]:
            try:
                el = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, sel)))
                if el.is_displayed():
                    user_input = el
                    break
            except:
                continue
        
        if user_input:
            user_input.send_keys(cred["username"])
            
        pass_input = None
        for sel in ["input[type='password']", "input[placeholder='Password']"]:
            try:
                el = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, sel)))
                if el.is_displayed():
                    pass_input = el
                    break
            except:
                continue
                
        if pass_input:
            pass_input.send_keys(cred["password"])
    except Exception as autofill_err:
        log.warning(f"⚠️ Gagal mengisi otomatis credentials untuk '{name}': {autofill_err}")

def launch_portal_browser(name):
    log.info(f"🌐 Membuka browser untuk VB '{name}'...")
    try:
        driver = _init_driver(headless=False, account_name=name)
        drivers[name] = driver
        
        # Navigate to shopee partner home
        driver.get("https://partner.shopee.co.id/")
        time.sleep(2)
        
        # Load saved session cookies if they exist
        saved = load_session()
        if saved:
            log.info(f"🔑 Memasukkan cookie sesi tersimpan untuk VB '{name}'...")
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
                log.warning(f"⚠️ Gagal menambahkan sebagian cookie untuk '{name}': {cookie_err}")
            
            # Refresh to apply cookies and go to dashboard
            driver.get("https://partner.shopee.co.id/food/dashboard")
            time.sleep(3)
            
            # Check if redirected to login page due to expired session
            if "login" in driver.current_url.lower():
                log.warning(f"⚠️ Sesi tersimpan kedaluwarsa untuk VB '{name}'. Mengisi otomatis credentials...")
                cred = get_credentials(name)
                if cred:
                    autofill_login_form(driver, cred, name)
        else:
            log.warning(f"⚠️ Sesi tidak ditemukan untuk VB '{name}'. Silakan login manual.")
            driver.get("https://partner.shopee.co.id/login")
            cred = get_credentials(name)
            if cred:
                autofill_login_form(driver, cred, name)

    except Exception as e:
        log.error(f"❌ Gagal membuka browser untuk VB '{name}': {e}")

def main():
    threads = []
    for p in portals:
        t = threading.Thread(target=launch_portal_browser, args=(p,), daemon=True)
        threads.append(t)
        t.start()
        time.sleep(1.5) # stagger launch slightly to avoid high CPU load

    print("\n" + "="*60)
    print("🚀 Browser untuk keempat portal VB Shopee telah dibuka!")
    print("Anda dapat berinteraksi langsung dengan browser tersebut.")
    print("Tekan ENTER di terminal ini atau Ctrl+C untuk menutup semua browser secara bersamaan.")
    print("="*60 + "\n")
    
    try:
        input()
    except KeyboardInterrupt:
        pass
    
    print("🧹 Menutup semua browser...")
    for name, driver in list(drivers.items()):
        try:
            driver.quit()
            print(f"✅ Browser VB '{name}' ditutup.")
        except:
            pass

if __name__ == "__main__":
    main()
