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
            print(f"Started async download, ref_id: {ref_id}")
            return ref_id
        return None

    async def poll_for_download(self, mgid, ref_id, max_retries=60):
        """Wait for report to be ready"""
        url = f"{self.base_url}/mex/finances/v1/generated-report/{ref_id}"
        params = {
            "merchant_group_id": mgid,
            "currency": "IDR"
        }
        
        for i in range(max_retries):
            resp = await self.call_api(url, params=params)
            if resp.get("status") == 200:
                data = resp.get("data", {})
                status = data.get("data", {}).get("status")
                if status == "SUCCESS":
                    urls = data.get("data", {}).get("urls", [])
                    for u in urls:
                        if u.get("name") == "url" and u.get("url"):
                            return u.get("url")
                elif status == "FAILED":
                    return None
            
            await asyncio.sleep(5)
        return None

    async def download_csv(self, download_url, filename):
        """Download CSV from URL"""
        import requests
        resp = requests.get(download_url)
        if resp.status_code == 200:
            os.makedirs("downloads", exist_ok=True)
            with open(filename, 'wb') as f:
                f.write(resp.content)
            return True
        return False

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
        if "saved-accounts" in page.url or await page.locator('button:has-text("Continue")').count() > 0:
            print(f"Detected 'Welcome back' page for {user}")
            welcome_text = (await page.content()).lower()
            
            # Check if the saved account matches our user
            if user.lower() in welcome_text:
                print(f"Saved account matches {user}, clicking 'Continue'...")
                await page.locator('button:has-text("Continue")').first.click()
            else:
                print(f"Saved account mismatch, clicking 'Login as another user'...")
                another_user_btn = page.locator('button:has-text("another user"), [role="button"]:has-text("another user")')
                if await another_user_btn.count() > 0:
                    await another_user_btn.first.click()
                else:
                    # Fallback: maybe just click the Continue button anyway if it's the only choice
                    await page.locator('button').first.click()
            
            await page.wait_for_timeout(3000)
            # After clicking Continue, we might be on password page or dashboard
            if "login" not in page.url.lower():
                print(f"Successfully bypassed login via 'Continue'. URL: {page.url}")
                return True

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
        # First, check if password field is ALREADY visible (skip username)
        if await page.locator('input[type="password"], #password').is_visible(timeout=2000):
            print("Password field is already visible, skipping username step.")
        else:
            for sel in user_selectors:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        user_field = el
                        print(f"Found username field with selector: {sel}")
                        break
                except:
                    continue
            
            if not user_field:
                print(f"✗ Could not find username field for {user}.")
                await page.screenshot(path=f"login_fail_field_{user}.png")
                # Log all input fields to help debugging
                inputs = await page.locator("input").all()
                print(f"Available inputs on page: {[await i.get_attribute('name') or await i.get_attribute('type') for i in inputs]}")
                return False
            
            print(f"Entering username: {user}")
            await user_field.fill(user)
            await page.wait_for_timeout(500)
            await page.keyboard.press("Enter")
        
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

async def run_api_download_for_portal(user, pwd):
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
            return None

        # Dates: Ensure we cover from the start of February (roughly 120 days ago)
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")
        
        print(f"Requesting report: {start_date} to {end_date}")
        ref_id = await api.start_async_download(mgid, start_date, end_date)
        if not ref_id:
            await context.close()
            return None
            
        download_url = await api.poll_for_download(mgid, ref_id)
        if not download_url:
            await context.close()
            return None
            
        filename = f"downloads/grab_transactions_api_{user}_{start_date}_to_{end_date}.csv"
        success = await api.download_csv(download_url, filename)
        
        await context.close()
        return filename if success else None

if __name__ == "__main__":
    load_dotenv()
    user = os.getenv("GRAB_USERNAME_PORTAL1")
    pwd = os.getenv("GRAB_PASSWORD_PORTAL1")
    if user and pwd:
        asyncio.run(run_api_download_for_portal(user, pwd))
