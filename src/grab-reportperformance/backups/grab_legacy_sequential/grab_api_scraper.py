import os
import json
import asyncio
import time
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

class GrabAPI:
    def __init__(self, page, username, password):
        self.page = page
        self.username = username
        self.password = password
        self.base_url = "https://merchant.grab.com"

    async def call_api(self, url, method="GET", params=None):
        """Call Grab API from within the page context to reuse session/headers"""
        # Construct URL with params if GET
        full_url = url
        if params and method == "GET":
            query = "&".join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{url}?{query}" if "?" not in url else f"{url}&{query}"
        
        js_code = f"""
        async () => {{
            try {{
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 15000);
                
                const response = await fetch("{full_url}", {{
                    method: "{method}",
                    signal: controller.signal,
                    headers: {{
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    }}
                }});
                clearTimeout(timeoutId);
                const status = response.status;
                const text = await response.text();
                try {{
                    return {{ status, data: JSON.parse(text) }};
                }} catch (e) {{
                    return {{ status, data: text }};
                }}
            }} catch (e) {{
                return {{ status: 0, error: e.toString() }};
            }}
        }}
        """
        
        for attempt in range(3):
            try:
                # Wait for page to be relatively stable
                if self.page.is_closed():
                    return {"status": 0, "error": "Page closed"}
                
                # We don't necessarily want to wait for 'load' if the page is already there
                # but we want to avoid "Execution context was destroyed"
                return await self.page.evaluate(js_code)
            except Exception as e:
                err_msg = str(e).lower()
                if ("context was destroyed" in err_msg or "navigation" in err_msg) and attempt < 2:
                    print(f"  [Retry] Execution context lost, retrying API call... ({attempt+1})")
                    await asyncio.sleep(2)
                    continue
                return {"status": 0, "error": str(e)}

    async def get_merchant_group_id(self):
        """GET /troy/user-profile/v1/merchant-selector"""
        url = f"{self.base_url}/troy/user-profile/v1/merchant-selector"
        resp = await self.call_api(url)
        status = resp.get("status")
        if status == 200:
            data = resp.get("data", {})
            merchants = data.get("merchants", [])
            if merchants:
                mgid = merchants[0].get("id")
                return mgid
        else:
            print(f"  [API] merchant-selector returned status {status}: {str(resp.get('data'))[:100]}")
        return None

    async def start_async_download(self, mgid, start_date, end_date):
        """GET /mex/finances/v1/async-transactions-download"""
        url = f"{self.base_url}/mex/finances/v1/async-transactions-download"
        params = {
            "merchant_group_id": mgid,
            "store_ids": "all",
            "from": start_date,
            "to": end_date,
            "currency": "IDR"
        }
        resp = await self.call_api(url, params=params)
        if resp.get("status") == 200:
            data = resp.get("data", {})
            ref_id = data.get("data", {}).get("ref_id")
            if ref_id:
                print(f"Started async download, ref_id: {ref_id}")
                return ref_id, None
            return None, f"No ref_id in 200 response: {data}"
        
        err = f"Status {resp.get('status')}: {resp.get('data') or resp.get('error')}"
        return None, err

    async def poll_for_download(self, mgid, ref_id, max_retries=60):
        """Wait for report to be ready"""
        url = f"{self.base_url}/mex/finances/v1/generated-report/{ref_id}"
        params = {
            "merchant_group_id": mgid,
            "currency": "IDR"
        }
        
        last_error = "Timeout"
        for i in range(max_retries):
            resp = await self.call_api(url, params=params)
            if resp.get("status") == 200:
                outer = resp.get("data") or {}
                inner = outer.get("data") or {}
                status = inner.get("status")
                if status == "SUCCESS":
                    urls = inner.get("urls") or []
                    for u in urls:
                        if u.get("name") == "url" and u.get("url"):
                            return u.get("url"), None
                    err = f"Status SUCCESS but no valid URL found in: {urls}"
                    print(f"  [Poll] {err}")
                    return None, err
                elif status == "FAILED":
                    err = f"Report generation FAILED on Grab's end. Data: {inner}"
                    print(f"  [Poll] {err}")
                    return None, err
                else:
                    print(f"  [Poll {i+1}/{max_retries}] Status: {status}, waiting 5s...")
            else:
                last_error = f"API status {resp.get('status')}: {resp.get('data') or resp.get('error')}"
                print(f"  [Poll {i+1}/{max_retries}] {last_error}, waiting 5s...")
            
            await asyncio.sleep(5)
        
        return None, f"Timed out after {max_retries} retries. Last state: {last_error}"

    async def download_csv(self, download_url, filename):
        """Download CSV from URL"""
        import requests
        try:
            resp = requests.get(download_url, timeout=60)
            if resp.status_code == 200:
                os.makedirs("downloads", exist_ok=True)
                with open(filename, 'wb') as f:
                    f.write(resp.content)
                return True, None
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            return False, str(e)

async def perform_login(page, user, pwd):
    """Robust login steps with intensive debugging"""
    try:
        print(f"Navigating to login page for {user}...")
        resp = await page.goto("https://merchant.grab.com/login", wait_until="domcontentloaded", timeout=60000)
        if resp:
            print(f"Login page status: {resp.status}")
        
        await page.wait_for_timeout(3000)
        print(f"Current URL: {page.url}")
        print(f"Page Title: {await page.title()}")

        # Check for block pages
        content = await page.content()
        if "Attention Required" in await page.title() or "cloudflare" in content.lower() or "distil" in content.lower():
            print("✗ [BLOCK] Detected anti-bot/Cloudflare page. Headless mode might be blocked.")
            await page.screenshot(path=f"blocked_{user}.png")
            return False

        # --- Handle "Welcome back" / Saved Accounts page ---
        is_saved_accounts = "saved-accounts" in page.url
        welcome_back_locator = page.locator('h1:has-text("Welcome back"), h2:has-text("Welcome back"), div:has-text("Welcome back")')
        
        if is_saved_accounts or await welcome_back_locator.count() > 0:
            print(f"Detected 'Welcome back' page for {user}")
            content_lower = (await page.content()).lower()
            
            # Check if the saved account matches our user
            # We look for the user string in the page content
            if user.lower() in content_lower:
                print(f"Saved account matches {user}, clicking 'Continue'...")
                continue_btn = page.locator('button:has-text("Continue"), button:has-text("Lanjut")')
                if await continue_btn.count() > 0:
                    await continue_btn.first.click()
                    await page.wait_for_timeout(3000)
                    # After clicking Continue, we might be on password page or dashboard
                    if "login" not in page.url.lower():
                        print(f"Successfully bypassed login via 'Continue'. URL: {page.url}")
                        return True
                else:
                    print("Could not find Continue button even though Welcome back was detected.")
            else:
                print(f"Saved account mismatch or name not found, clicking 'Login as another user'...")
                another_user_btn = page.locator('button:has-text("another user"), [role="button"]:has-text("another user"), button:has-text("akun lain")')
                if await another_user_btn.count() > 0:
                    await another_user_btn.first.click()
                    await page.wait_for_timeout(2000)
                else:
                    print("No 'another user' button found, proceeding to normal login flow.")

        # --- Normal Login Flow ---
        # Try multiple selector variations for the email/username field
        user_selectors = [
            'input[type="email"]',
            'input[name="email"]',
            'input[type="text"]',
            'input[placeholder*="Email" i]',
            'input[placeholder*="Username" i]',
            '#email',
            '#username'
        ]
        
        user_field = None
        # Look for username field
        for sel in user_selectors:
            try:
                el = page.locator(sel).first
                # Check if it's actually visible and enabled
                if await el.is_visible(timeout=2000) and await el.is_enabled():
                    user_field = el
                    print(f"Found username field with selector: {sel}")
                    break
            except:
                continue
        
        if user_field:
            print(f"Entering username: {user}")
            await user_field.click()
            await user_field.fill("") # Clear first
            await user_field.fill(user)
            await page.wait_for_timeout(500)
            await page.keyboard.press("Enter")
            
            # Wait for transition
            await page.wait_for_timeout(2000)
        else:
            print("Username field not found, checking if we are already at the password step...")

        # Wait for Password field
        print("Waiting for password field...")
        pwd_selector = 'input[type="password"], #password'
        try:
            await page.wait_for_selector(pwd_selector, timeout=15000)
        except:
            print("Password field not found after Enter, trying to click 'Continue' button...")
            # Look for Continue/Next buttons
            continue_btns = page.locator('button:has-text("Continue"), button:has-text("Next"), button:has-text("Lanjut")')
            if await continue_btns.count() > 0:
                await continue_btns.first.click()
                try:
                    await page.wait_for_selector(pwd_selector, timeout=10000)
                except:
                    print("Still no password field after clicking Continue.")
            else:
                print("No Continue button found either.")
            
            if await page.locator(pwd_selector).count() == 0:
                await page.screenshot(path=f"login_fail_pwd_{user}.png")
                return False
        
        print("Entering password...")
        await page.fill(pwd_selector, pwd)
        await page.wait_for_timeout(500)
        await page.keyboard.press("Enter")
        
        print("Waiting for redirect away from login...")
        try:
            # Wait for either dashboard or merchant selector
            await page.wait_for_url(lambda u: "login" not in u.lower(), timeout=30000)
            await page.wait_for_load_state("networkidle")
            print(f"Successfully redirected to: {page.url}")
        except Exception as e:
            print(f"Wait for redirect timed out: {e}")
            await page.screenshot(path=f"login_fail_redirect_{user}.png")
        
        return "login" not in page.url.lower()
    except Exception as e:
        print(f"Login steps failed for {user}: {e}")
        try:
            await page.screenshot(path=f"login_error_{user}.png")
        except:
            pass
        return False

async def run_api_download_for_portal(user, pwd, start_date: str = None, end_date: str = None):
    async with async_playwright() as p:
        # isolation per user
        user_data_dir = f"browser_data/{user}"
        os.makedirs(user_data_dir, exist_ok=True)
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=True,
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print(f"\n[Isolation] Ensuring session for {user}...")
        try:
            await page.goto("https://merchant.grab.com/dashboard", wait_until="networkidle", timeout=60000)
        except Exception as e:
            print(f"Initial navigation warning: {e}")
            # Continue anyway, might be already there or redirected
        
        api = GrabAPI(page, user, pwd)
        
        # 1. Check if already logged in by trying the API
        mgid = await api.get_merchant_group_id()
        
        if not mgid:
            print(f"Session not active for {user}. Attempting login...")
            login_success = await perform_login(page, user, pwd)
            if login_success:
                print("Login successful, getting MGID...")
                await asyncio.sleep(2)
                mgid = await api.get_merchant_group_id()
            else:
                print(f"✗ Login failed or timed out for {user}.")
        else:
            print(f"Session already active for {user}.")

        if not mgid:
            print(f"✗ Failed to get MGID for {user} after all attempts.")
            await context.close()
            return None, "Failed to get MGID (possibly session/login issue)"

        # Dates: Use provided or fallback to 120-day window
        report_end = end_date or datetime.now().strftime("%Y-%m-%d")
        report_start = start_date or (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")
        
        print(f"Requesting report: {report_start} to {report_end}")
        ref_id, err = await api.start_async_download(mgid, report_start, report_end)
        if not ref_id:
            await context.close()
            return None, f"Start download failed: {err}"
            
        download_url, err = await api.poll_for_download(mgid, ref_id)
        if not download_url:
            await context.close()
            return None, f"Polling failed: {err}"
            
        filename = f"downloads/grab_transactions_api_{user}_{report_start}_to_{report_end}.csv"
        success, err = await api.download_csv(download_url, filename)
        
        await context.close()
        return (filename, None) if success else (None, f"Download file failed: {err}")

if __name__ == "__main__":
    load_dotenv()
    user = os.getenv("GRAB_USERNAME_PORTAL1")
    pwd = os.getenv("GRAB_PASSWORD_PORTAL1")
    if user and pwd:
        file, err = asyncio.run(run_api_download_for_portal(user, pwd))
        if file:
            print(f"Success: {file}")
        else:
            print(f"Failed: {err}")
