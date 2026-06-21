"""
Login + test berbagai format tanggal ke Grab API.
"""
import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv(override=True)

START_RAW = "2026-05-11"
END_RAW   = "2026-05-17"

dt_start = datetime.strptime(START_RAW, "%Y-%m-%d")
dt_end   = datetime.strptime(END_RAW, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

formats = {
    "dd/mm/yy":   (dt_start.strftime("%d/%m/%y"),   dt_end.strftime("%d/%m/%y")),
    "unix_ms":    (int(dt_start.timestamp() * 1000), int(dt_end.timestamp() * 1000)),
    "unix_s":     (int(dt_start.timestamp()),         int(dt_end.timestamp())),
    "ISO8601":    (dt_start.isoformat() + "Z",        dt_end.isoformat() + "Z"),
    "YYYY-MM-DD": (START_RAW,                          END_RAW),
}

# Pakai satu akun weekly yang ada di spreadsheet (ambil dari env atau hardcode untuk test)
# Ganti dengan credential yang valid!
TEST_USER = os.getenv("TEST_USER", "superfoodgeprekampel")
TEST_PASS = os.getenv("TEST_PASS", "")

async def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from grab_api_scraper import GrabAPI, perform_login

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        session_path = f"sessions/{TEST_USER}.json"
        
        storage = session_path if os.path.exists(session_path) else None
        context = await browser.new_context(
            storage_state=storage,
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            await page.goto("https://merchant.grab.com/dashboard", wait_until="domcontentloaded", timeout=30000)
        except:
            pass
        
        api = GrabAPI(page, TEST_USER, TEST_PASS)
        mgid = await api.get_merchant_group_id()
        
        if not mgid and TEST_PASS:
            print(f"Session tidak aktif. Login untuk {TEST_USER}...")
            if await perform_login(page, TEST_USER, TEST_PASS):
                mgid = await api.get_merchant_group_id()
                if mgid:
                    await context.storage_state(path=session_path)
                    print(f"Login success! MGID: {mgid}")
        
        if not mgid:
            print(f"❌ Gagal mendapat MGID. Set TEST_USER dan TEST_PASS di env.")
            await context.close()
            await browser.close()
            return
        
        print(f"✅ MGID: {mgid}\n")
        print("Testing date formats...")
        
        for fmt_name, (from_val, to_val) in formats.items():
            url = "https://merchant.grab.com/mex/finances/v1/async-transactions-download"
            params = {"merchant_group_id": mgid, "store_ids": "all", "from": from_val, "to": to_val, "currency": "IDR"}
            resp = await api.call_api(url, params=params)
            st = resp.get("status")
            data = resp.get("data", {})
            if st == 200:
                ref_id = (data.get("data") or {}).get("ref_id", "?")
                print(f"  ✅ [{fmt_name}] STATUS 200 — ref_id={ref_id}")
                print(f"\n🎉 Format BENAR: {fmt_name}")
                print(f"   from = {from_val}  |  to = {to_val}")
                break
            else:
                msg = data.get("message", str(data)[:80]) if isinstance(data, dict) else str(data)[:80]
                print(f"  ❌ [{fmt_name}] STATUS {st} — {msg}")
            await asyncio.sleep(1)
        
        await context.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
