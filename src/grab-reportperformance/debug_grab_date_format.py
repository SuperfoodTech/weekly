"""
Debug script: intercept actual network request dari browser Grab untuk melihat
format parameter yang benar di endpoint async-transactions-download.
Jalankan: python debug_grab_date_format.py
"""
import asyncio
import os
import json
from datetime import datetime
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv(override=True)

TARGET_URL = "async-transactions-download"

async def main():
    captured_requests = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)  # tampilkan browser
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        # Coba pakai session tersimpan jika ada
        session_candidates = [f for f in os.listdir("sessions") if f.endswith(".json")] if os.path.exists("sessions") else []
        if session_candidates:
            s_path = os.path.join("sessions", session_candidates[0])
            print(f"[Debug] Loading session: {s_path}")
            try:
                context = await browser.new_context(
                    storage_state=s_path,
                    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
            except Exception as e:
                print(f"[Debug] Failed to load session: {e}. Using fresh context.")

        page = await context.new_page()

        # Intercept semua request ke Grab API
        async def on_request(request):
            if TARGET_URL in request.url:
                print(f"\n{'='*60}")
                print(f"[CAPTURED REQUEST] {request.method} {request.url}")
                print(f"[Headers] {json.dumps(dict(request.headers), indent=2)}")
                post_data = request.post_data
                if post_data:
                    print(f"[Body] {post_data}")
                captured_requests.append(request.url)

        async def on_response(response):
            if TARGET_URL in response.url:
                try:
                    body = await response.text()
                    print(f"[RESPONSE {response.status}] {body[:500]}")
                except:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        print("[Debug] Navigating to Grab Merchant dashboard...")
        await page.goto("https://merchant.grab.com/portal/finance/transaction-report", wait_until="domcontentloaded", timeout=30000)
        
        print("[Debug] Browser open. Please manually:")
        print("  1. Login jika perlu")
        print("  2. Pergi ke Finance > Transaction Report")  
        print("  3. Set date range dan klik 'Export'")
        print("  4. Lihat terminal ini untuk intercept request")
        print("\nMenunggu 120 detik untuk intercept...")

        await asyncio.sleep(120)
        
        if not captured_requests:
            print("\n[Debug] Tidak ada request tertangkap. Coba manual export dari UI.")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
