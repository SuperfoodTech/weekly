import sys

file_path = '/home/akbarhann/project/task-weekly/src/shopee-omzet-automation/core/browser.py'
with open(file_path, 'r') as f:
    content = f.read()

import re

# We will find the definition of get_session and replace it entirely.
# Let's extract everything from `def get_session(` up to `def refresh_tokens(`

start_idx = content.find("def get_session(")
end_idx = content.find("def refresh_tokens(", start_idx)

if start_idx == -1 or end_idx == -1:
    print("Could not find functions")
    sys.exit(1)

new_get_session = """def get_session(username=None, password=None, phone=None, headless=True, close_browser=True, target_name=None) -> dict | None:
    for attempt in range(3):
        log.info(f"🌐 [BROWSER] Launching (headless={headless}, attempt={attempt+1}/3)...")
        driver = _init_driver(headless=headless)
        wait = WebDriverWait(driver, 30)
        session_success = False

        try:
            # ── Step 1: Check browser state first (Profile session) ──
            driver.get(PARTNER_DASHBOARD)
            time.sleep(4)
            
            if attempt > 0:
                log.info(f"⚠️ [SESSION] Forcing fresh login (Attempt {attempt+1})...")
                driver.delete_all_cookies()
                driver.get("https://partner.shopee.co.id/login")
                time.sleep(4)
            
            is_logged_in = False
            current_url = driver.current_url.lower()
            if ("dashboard" in current_url or "merchant-selector" in current_url) and attempt == 0:
                log.info("✅ [SESSION] Browser is already logged in.")
                is_logged_in = True
            elif attempt == 0:
                saved = load_session()
                if saved:
                    log.debug("🔍 Attempting to restore session from saved tokens...")
                    driver.add_cookie({"name": "shopee_tob_token", "value": saved["shopee_tob_token"]})
                    if saved.get("shopee_tob_entity_id"):
                        driver.add_cookie({"name": "shopee_tob_entity_id", "value": saved["shopee_tob_entity_id"]})
                    for n, v in saved.get("extra_cookies", {}).items():
                        try: driver.add_cookie({"name": n, "value": v})
                        except: pass
                    
                    driver.refresh()
                    time.sleep(4)
                    current_url = driver.current_url.lower()
                    if "dashboard" in current_url or "merchant-selector" in current_url:
                        log.info("✅ [SESSION] Restored from saved tokens.")
                        is_logged_in = True

            # ── Step 3: Login if all above failed ──
            if not is_logged_in:
                log.info("⚠️ [SESSION] No active session. Navigating to login...")
                if "/login" not in driver.current_url.lower() and "authenticate" not in driver.current_url.lower():
                    driver.get("https://partner.shopee.co.id/login")
                    time.sleep(5)
                
                current_url = driver.current_url.lower()
                if "login" in current_url or "authenticate" in current_url or "about:blank" in current_url:
                    success = _perform_login(driver, wait, username, password, phone)
                    if not success:
                        log.error("❌ [AUTH] _perform_login failed.")
                        driver.quit()
                        continue
                    
                time.sleep(3)
                if "onboarding" in driver.current_url or "merchant-selector" in driver.current_url:
                    log.info("📍 [SESSION] Detected Onboarding page. Selecting first available merchant...")
                    bypass_js = \"\"\"
                        var loaders = document.querySelectorAll('.ant-spin, [class*="loading"], .shopee-loading, .ant-spin-nested-loading');
                        loaders.forEach(el => el.remove());
                        var target = document.querySelector('.merchantInfo, .ant-list-item, .shop-name');
                        if (target) {
                            target.scrollIntoView({block: 'center'});
                            target.click();
                            setTimeout(() => {
                                var btns = document.querySelectorAll('button');
                                for (var b of btns) {
                                    var bText = (b.innerText || "").toLowerCase();
                                    if (bText.includes('masuk') || bText.includes('konfirmasi') || bText.includes('lanjutkan') || bText.includes('ok')) {
                                        b.click();
                                    }
                                }
                            }, 500);
                            return true;
                        }
                        return false;
                    \"\"\"
                    bypass_success = False
                    for _ in range(10):
                        if driver.execute_script(bypass_js):
                            log.debug("  ✅ Selection triggered via JS.")
                            try:
                                wait.until(lambda d: "/food/dashboard" in d.current_url)
                                log.debug("  ✅ Landed on dashboard.")
                                bypass_success = True
                                break
                            except: pass
                        try:
                            container = driver.find_element(By.CSS_SELECTOR, ".ant-list-items, [role='list']")
                            driver.execute_script("arguments[0].scrollTop += 300;", container)
                        except: pass
                        time.sleep(1)
                    if bypass_success: time.sleep(2)
            
            # ── Step 4: Extract current ID & Name via API ──
            log.debug("🔍 Fetching active merchant info via API...")
            active_id = None
            active_name = "Unknown Merchant"
            try:
                api_js = \"\"\"
                var done = arguments[arguments.length - 1];
                let token = document.cookie.split('; ').find(row => row.startsWith('shopee_tob_token='))?.split('=')[1];
                fetch('https://api.partner.shopee.co.id/nb/mss/web-api/PartnerAccountServer/GetUserInfo', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'x-merchant-token': token || '',
                        'x-merchant-language': 'id',
                        'x-merchant-login-from': '12'
                    },
                    body: '{}',
                    credentials: 'include'
                })
                .then(r => r.json())
                .then(j => done(j.data || null))
                .catch(() => done(null));
                \"\"\"
                driver.set_script_timeout(10)
                user_data = driver.execute_async_script(api_js)
                if user_data:
                    active_id = str(user_data.get("merchantId") or "")
                    active_name = user_data.get("merchantName") or "Unknown Merchant"
            except: pass

            # ── Step 4.5: Fallback to UI Name Matching ──
            if not active_id or active_id == "None":
                try:
                    ui_name = ""
                    for _ in range(5):
                        try:
                            el = driver.find_element(By.CLASS_NAME, "merchantName")
                            if el.text.strip():
                                ui_name = el.text.strip()
                                break
                        except: pass
                        time.sleep(1)
                    if ui_name:
                        active_name = ui_name
                        with open("API/response.json", "r") as f:
                            m_data = json.load(f)
                            for m in m_data.get("data", {}).get("selectMerchant", {}).get("merchantList", []):
                                if m["merchantName"].lower() == ui_name.lower():
                                    active_id = str(m["merchantId"])
                                    log.info(f"📍 [MERCHANT] Detected: {active_name} (ID: {active_id})")
                                    break
                except: pass

            if not active_id:
                _, active_id = extract_tokens_from_driver(driver)
            
            # ── Step 5: Decision - Switch or Stay? ──
            do_switch = False
            if target_name:
                if active_name.lower() != target_name.lower():
                    log.info(f"📍 [MERCHANT] Current: {active_name} | Target: {target_name}. Switching...")
                    do_switch = True
                else:
                    log.info(f"✅ [MERCHANT] Already as target: {active_name}")
            else:
                if active_id and active_id != "None":
                    log.info(f"📍 [MERCHANT] Current: {active_name} (ID: {active_id})")
                    choice = input(f"❓ Switch merchant? (y/N): ").strip().lower()
                    if choice == 'y': do_switch = True
                else:
                    log.info("📍 [MERCHANT] No active merchant detected. Redirecting...")
                    do_switch = True

            if do_switch:
                if target_name:
                    success = auto_switch_merchant(driver, target_name)
                    if not success:
                        log.warning(f"⚠️ [MERCHANT] auto_switch_merchant failed for target {target_name}. Initiating logout/relogin recovery...")
                        recovered = _deliberate_logout_and_relogin(
                            driver,
                            username=username,
                            password=password,
                            phone=phone,
                        )
                        if recovered:
                            log.info("🔄 [MERCHANT] Recovery successful. Retrying merchant switch...")
                            success = auto_switch_merchant(driver, target_name)
                        else:
                            log.error("❌ Recovery failed.")
                            success = False
                else:
                    if "/food/dashboard" in driver.current_url:
                        log.info("🔄 Navigating to merchant selector...")
                        return_to_selector(driver)
                    success = _handle_merchant_selection(driver, active_id_forced=active_id)
                if not success:
                    log.error("❌ Merchant selection failed.")
                    driver.quit()
                    continue
            else:
                if "/food/dashboard" not in driver.current_url:
                    driver.get(PARTNER_DASHBOARD)
                    time.sleep(2)

            # ── Step 6: Final Token Extraction ──
            t, eid = _trigger_and_extract_tokens(driver)
            if not t:
                log.warning("⚠️ Token extraction failed.")
                driver.quit()
                continue
                
            all_c = get_all_cookies_dict(driver)
            save_session(t, eid or "", extra_cookies=all_c)
            res = {"shopee_tob_token": t, "shopee_tob_entity_id": eid or "", "extra_cookies": all_c}
            if not close_browser: res["driver"] = driver
            session_success = True
            return res

        except Exception as e:
            log.error(f"Browser session error on attempt {attempt+1}: {e}")
        finally:
            if (close_browser or not session_success) and driver is not None:
                try: driver.quit()
                except: pass

    log.error("❌ Max login retries reached.")
    return None

"""

new_content = content[:start_idx] + new_get_session + content[end_idx:]

with open(file_path, 'w') as f:
    f.write(new_content)
print("Applied successfully.")
