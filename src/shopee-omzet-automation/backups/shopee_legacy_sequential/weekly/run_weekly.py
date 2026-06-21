import os
import time
import json
import pandas as pd
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests

from core.browser import get_session, return_to_selector, refresh_tokens, auto_switch_merchant
from core.client import ShopeeClient
from core.logger import get_logger
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# Load environment variables
load_dotenv()
log = get_logger("omzet_pipeline")

def subtract_months(dt, months):
    """Helper to subtract calendar months."""
    for _ in range(months):
        dt = (dt - timedelta(days=1)).replace(day=1)
    return dt

def get_live_merchants(app_name="ShopeeFood", max_age_hours=24):
    """
    Fetches live merchants from Google Sheets and caches them locally.
    Uses cached data if it's less than max_age_hours old.
    """
    import os
    from datetime import datetime
    
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRUOPDeyWtcCQT2OaNTmplVoIs0FxGFT-6UA3W-AJ_-RAG3H57UTADOyK2O1YnwMhphQPL2Nj86s7N6/pub?gid=0&single=true&output=csv"
    cache_path = "data/master_merchants_cache.csv"
    os.makedirs("data", exist_ok=True)
    
    # Cek cache
    if os.path.exists(cache_path):
        mtime = os.path.getmtime(cache_path)
        age_hours = (time.time() - mtime) / 3600
        if age_hours < max_age_hours:
            log.info(f"🔄 [DATA] Using cached merchant list (Age: {age_hours:.1f}h)")
            df = pd.read_csv(cache_path)
            sf_df = df[(df['Aplikasi'] == app_name) & (df['Status'] == 'Live')]
            sf_df = sf_df[(sf_df['Merchant Name'] != '-') & (sf_df['Merchant Name'].notna())]
            sf_df = sf_df.drop_duplicates(subset=['Merchant Name'])
            return sf_df['Merchant Name'].tolist()
            
    # Jika tidak ada cache atau sudah usang, download ulang
    log.info("🌐 [DATA] Downloading fresh merchant list from Google Sheets...")
    try:
        df = pd.read_csv(url)
        df.to_csv(cache_path, index=False)
        
        sf_df = df[(df['Aplikasi'] == app_name) & (df['Status'] == 'Live')]
        sf_df = sf_df[(sf_df['Merchant Name'] != '-') & (sf_df['Merchant Name'].notna())]
        sf_df = sf_df.drop_duplicates(subset=['Merchant Name'])
        
        return sf_df['Merchant Name'].tolist()
    except Exception as e:
        log.error(f"⚠️ Failed to fetch/parse merchants: {e}")
        return []

def download_file(url, filename, cookies=None, max_retries=3):
    """Downloads a file from a URL with optional cookies and retries."""
    import requests
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, stream=True, cookies=cookies, headers=headers, timeout=30)
            response.raise_for_status()
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                log.warning(f"⚠️ Download attempt {attempt+1} failed for {filename}: {e}. Retrying in 5s...")
                time.sleep(5)
            else:
                log.error(f"❌ Failed to download {filename} after {max_retries} attempts: {e}")
    return False


def run_pipeline():
    import argparse
    parser = argparse.ArgumentParser(description="Shopee Omzet Weekly Pipeline")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)", default=None)
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)", default=None)
    parser.add_argument("--output-dir", type=str, help="Override output directory for reports", default=None)
    args = parser.parse_args()

    # Determine output directory
    report_dir = args.output_dir or "data/reports/weekly"

    # Determine date range
    now = datetime.now()
    if args.start and args.end:
        start_dt = datetime.strptime(args.start, "%Y-%m-%d")
        end_dt = datetime.strptime(args.end, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        label = f"{start_dt.strftime('%d %b %Y')} - {end_dt.strftime('%d %b %Y')}"
    else:
        # Default to last 7 days (including today)
        end_dt = now.replace(hour=23, minute=59, second=59)
        start_dt = (end_dt - timedelta(days=6)).replace(hour=0, minute=0, second=0)
        label = f"{start_dt.strftime('%d %b %Y')} - {end_dt.strftime('%d %b %Y')} (Last 7 Days)"
        
    global_ranges = [{"start": int(start_dt.timestamp()), "end": int(end_dt.timestamp()), "label": label}]
    
    print("\n" + "=" * 60)
    print(f"  Shopee Omzet - WEEKLY Report Pipeline")
    print(f"  Range: {label}")
    print("=" * 60)

    phone    = os.getenv("SHOPEE_PHONE", "").strip()
    username = os.getenv("SHOPEE_USERNAME", "").strip()
    password = os.getenv("SHOPEE_PASSWORD", "").strip()
    headless = os.getenv("HEADLESS", "false").lower() == "true"

    # ── 1. Determine Merchants to Process (Data-Driven via G-Sheets) ────
    target_merchants = get_live_merchants(app_name="ShopeeFood", max_age_hours=24)
    log.info(f"📋 [PROGRESS] Found {len(target_merchants)} live merchants ready to process.")

    if not target_merchants:
        log.error("❌ No merchants to process. Aborting.")
        return

    # ── 2. Phase 1: Rapid Trigger (Trigger exports for all) ────────────
    log.info(f"🚀 [PROGRESS] PHASE 1: Triggering Exports for {len(target_merchants)} merchants...")
    
    # Initialize session
    session_data = get_session(username=username or None, password=password or None, phone=phone or None, 
                               headless=headless, close_browser=False, target_name=target_merchants[0])
    if not session_data: return
    driver = session_data.get("driver")

    merchants_context = {} # Store tokens/ids for each merchant
    start_time_all = int(time.time())

    for i, merchant_name in enumerate(target_merchants):
        log.info(f"  [{i+1}/{len(target_merchants)}] Triggering: {merchant_name}")
        
        # Switch if not already there
        if i > 0:
            switch_success = False
            for retry in range(2):
                if auto_switch_merchant(driver, merchant_name):
                    switch_success = True
                    break
                else:
                    log.warning(f"  ⚠️ Retrying switch for {merchant_name} (Attempt {retry+2}/2)...")
                    time.sleep(3)
            
            if not switch_success:
                log.warning(f"  ❌ Skipping {merchant_name} after 2 failed switch attempts.")
                continue
            time.sleep(3) # Wait for cookies to sync
        
        # Get tokens and VERIFY ID
        session = refresh_tokens(driver)
        active_id = str(session.get("shopee_tob_entity_id") or "")
        
        # Double check if the ID actually changed from previous
        if i > 0 and active_id == merchants_context.get(target_merchants[i-1], {}).get("entity_id"):
             log.warning("  ⚠️ ID hasn't changed yet. Retrying token refresh...")
             time.sleep(3)
             session = refresh_tokens(driver)
             active_id = str(session.get("shopee_tob_entity_id") or "")

        log.debug(f"  📍 Confirmed ID for {merchant_name}: {active_id}")
        
        # Store context for polling
        merchants_context[merchant_name] = {
            "entity_id": active_id,
            "tob_token": session["shopee_tob_token"],
            "cookies": session.get("extra_cookies", {}),
            "start_trigger_time": int(time.time())
        }

        # Initialize client and trigger
        client = ShopeeClient(tob_token=session["shopee_tob_token"], entity_id=active_id, extra_cookies=session.get("extra_cookies", {}))
        
        # Assign ranges based on CLI arguments
        ranges = global_ranges
        
        merchants_context[merchant_name]["ranges"] = ranges
        merchants_context[merchant_name]["downloaded"] = []

        # Trigger with retry on network error
        for r in ranges:
            success = False
            for trigger_retry in range(3):
                res = client.export_transaction_report(merchant_ids=[active_id], start_time=r["start"], end_time=r["end"])
                if res is True:
                    success = True
                    break
                elif res is None: # Network Error
                    log.warning(f"  ⚠️ Network error during trigger for {merchant_name}. Retrying in 10s... ({trigger_retry+1}/3)")
                    time.sleep(10)
                else: # API Error (res is False)
                    break
            
            if not success:
                log.error(f"  ❌ Failed to trigger export for {merchant_name} range {r.get('label')}")
            time.sleep(1)

    # ── 3. Phase 2: Global Polling & Download ──────────────────────────
    log.info(f"⏳ [PROGRESS] PHASE 2: Global Polling for all reports...")
    os.makedirs(report_dir, exist_ok=True)
    
    total_expected = len(merchants_context) * len(global_ranges)
    download_count = 0
    start_poll = time.time()
    
    consecutive_network_errors = 0
    while download_count < total_expected and (time.time() - start_poll) < 1800: # Increased timeout to 30m
        found_new = False
        poll_iteration += 1
        has_network_issue = False
        
        for m_name, ctx in merchants_context.items():
            if len(ctx["downloaded"]) >= len(global_ranges): continue
            
            client = ShopeeClient(tob_token=ctx["tob_token"], entity_id=ctx["entity_id"], extra_cookies=ctx["cookies"])
            reports = client.get_report_list()
            
            if reports is None: # Network/Connection Error
                has_network_issue = True
                continue
                
            consecutive_network_errors = 0 # Reset on any successful API response
            
            for rep in reports:
                # Match: status ready (2 or 3), has download URL, created after our trigger
                if rep.get("status") in [2, 3] and rep.get("download_url"):
                    if rep.get("create_time", 0) and rep["create_time"] >= ctx["start_trigger_time"]:
                        # Use report name for file naming (e.g. "Transactions_01022026_28022026_ShopeeFood.xlsx")
                        report_name = rep.get("name", f"report_{rep.get('id')}.xlsx")
                        target_path = os.path.join(report_dir, f"{m_name.replace(' ', '_')}_{report_name}")
                        
                        if target_path not in [d[0] for d in ctx["downloaded"]]:
                            if download_file(rep.get("download_url"), target_path):
                                log.info(f"  ✅ [DOWNLOAD] SUCCESS: {m_name} -> {report_name}")
                                ctx["downloaded"].append((target_path, report_name))
                                download_count += 1
                                found_new = True
            
            # Log progress every 3 iterations (~30 seconds)
            if not found_new and poll_iteration % 3 == 0:
                 log.info(f"  ⏳ [PROGRESS] Waiting for {m_name}... ({len(ctx['downloaded'])}/{len(global_ranges)} ready)")
        
        if has_network_issue:
            consecutive_network_errors += 1
            wait_time = min(10 * (2 ** (consecutive_network_errors - 1)), 60) # Exp backoff: 10, 20, 40, 60s
            log.warning(f"🌐 [NETWORK] API connection issues detected. Waiting {wait_time}s before next poll...")
            time.sleep(wait_time)
        elif download_count < total_expected:
            time.sleep(10)

    # ── Summary ──────────────────────────────────────────────────────────
    log.info("📋 [PROGRESS] Download Phase Complete. Summary:")
    for m_name, ctx in merchants_context.items():
        log.info(f"  🏪 {m_name}: {len(ctx['downloaded'])}/{len(global_ranges)} files")
        for fpath, label in ctx["downloaded"]:
            log.info(f"     📄 {fpath}")

    # ── 4. Phase 3: Data Transformation ──────────────────────────────────
    log.info("📊 [PROGRESS] PHASE 3: Data Transformation & Analysis...")
    all_analyzed_data = []
    
    for m_name, ctx in merchants_context.items():
        for fpath, label in ctx["downloaded"]:
            try:
                log.info(f"  📝 [DATA] Analyzing {os.path.basename(fpath)}...")
                df = pd.read_excel(fpath, dtype=str)
                
                if "Nilai Transaksi" in df.columns and "Harga Makanan" in df.columns:
                    # List of exact monetary columns in ShopeeFood reports
                    monetary_cols = [
                        'Harga Makanan', 'Diskon', 'Diskon Flash Sale', 'Biaya Tambahan', 
                        'Subsidi Merchant untuk Voucher Deals', 'Subsidi Platform untuk Flash Sale', 
                        'Subsidi Voucher Makanan', 'Diskon Langsung', 'Nilai Transaksi', 
                        'Harga Checkout Murah'
                    ]
                    
                    # Fix monetary columns: handle Shopee's inconsistent thousand separator/decimal format
                    # Some values are "decimalized" (e.g., 33.558 means 33558) while others are absolute (e.g., 300 means 300).
                    # The "decimalized" ones always contain a dot in the raw string.
                    def clean_shopee_monetary(val):
                        if pd.isna(val) or str(val).lower() == 'nan': return 0
                        s = str(val).strip()
                        if not s or s == '-': return 0
                        
                        has_dot = '.' in s
                        try:
                            # Standardize to float (handling Indonesian comma as decimal separator if any)
                            num = float(s.replace(',', '.'))
                            if has_dot:
                                return int(round(num * 1000))
                            else:
                                return int(num)
                        except:
                            return 0

                    for col in monetary_cols:
                        if col in df.columns:
                            df[col] = df[col].apply(clean_shopee_monetary)
                    
                    # Calculate new metrics based on corrected raw values (allow decimals for Commission)
                    commission_real = df['Nilai Transaksi'] * 0.25
                    revenue_real = df['Nilai Transaksi'] - commission_real
                    ofd_fees_real = df['Harga Makanan'] - revenue_real
                    
                    # Insert new columns
                    df['Commission'] = commission_real
                    df['Revenue'] = revenue_real
                    df['OFD Fees'] = ofd_fees_real
                    
                    # Add Merchant Name column at the beginning
                    df.insert(0, "Merchant Name", m_name)
                    
                    # Fix scientific notation for Order IDs
                    # Excel sometimes formats long numbers as 1.23E+15. Converting to string fixes this.
                    if "No. Pesanan" in df.columns:
                        # Convert to string and remove any trailing '.0' if pandas parsed it as float
                        df["No. Pesanan"] = df["No. Pesanan"].astype(str).str.replace(r'\.0$', '', regex=True)
                        
                    # Reformat Waktu Penyelesaian from "07 Mei 2026 23:16" to "2026-05-07 at 23:16"
                    if "Waktu Penyelesaian" in df.columns:
                        indo_months = {
                            'Januari': 'January', 'Februari': 'February', 'Maret': 'March', 
                            'April': 'April', 'Mei': 'May', 'Juni': 'June', 'Juli': 'July', 
                            'Agustus': 'August', 'September': 'September', 'Oktober': 'October', 
                            'November': 'November', 'Desember': 'December'
                        }
                        temp_dates = df["Waktu Penyelesaian"].astype(str)
                        for indo, eng in indo_months.items():
                            temp_dates = temp_dates.str.replace(indo, eng, case=False)
                        
                        # Parse to datetime and format
                        parsed_dates = pd.to_datetime(temp_dates, format="%d %B %Y %H:%M", errors='coerce')
                        
                        # Where parsing succeeded, apply the new format. Where it failed, keep original.
                        df["Waktu Penyelesaian"] = parsed_dates.dt.strftime('%Y-%m-%d at %H:%M').fillna(df["Waktu Penyelesaian"])
                    # Reorder columns to match Google Sheets format
                    desired_order = [
                        'Merchant Name', 'Store ID', 'Nama Toko', 'Tipe Transaksi', 'No. Pesanan', 
                        'Waktu Penyelesaian', 'Status', 'Harga Makanan', 'Diskon', 'Diskon Flash Sale', 
                        'Biaya Tambahan', 'Subsidi Merchant untuk Voucher Deals', 
                        'Subsidi Platform untuk Flash Sale', 'Subsidi Voucher Makanan', 
                        'Diskon Langsung', 'Nilai Transaksi', 'Harga Checkout Murah', 'Notes', 
                        'Commission', 'OFD Fees', 'Revenue'
                    ]
                    final_cols = [c for c in desired_order if c in df.columns] + [c for c in df.columns if c not in desired_order]
                    df = df[final_cols]
                    
                    # Save as new file
                    out_path = fpath.replace(".xlsx", "_Analyzed.xlsx")
                    df.to_excel(out_path, index=False)
                    log.info(f"     ✅ [DATA] Saved analyzed data: {os.path.basename(out_path)}")
                    
                    all_analyzed_data.append(df)
                else:
                    log.warning(f"     ⚠️ Missing required columns in {fpath}")
            except Exception as e:
                log.error(f"  ❌ Error processing {fpath}: {e}")

    # ── 5. Phase 4: Master Aggregation ───────────────────────────────────
    if all_analyzed_data:
        log.info("📑 [PROGRESS] PHASE 4: Combining all analyzed reports...")
        master_df = pd.concat(all_analyzed_data, ignore_index=True)
        
        # Determine date range for filename from global_ranges
        min_start = min([r['start'] for r in global_ranges])
        max_end = max([r['end'] for r in global_ranges])
        
        # Convert unix timestamp to readable date (DDMMYYYY)
        min_start_str = datetime.fromtimestamp(min_start).strftime('%d%m%Y')
        max_end_str = datetime.fromtimestamp(max_end).strftime('%d%m%Y')
        
        master_filename = f"Master_Weekly_Report_ShopeeFood_{min_start_str}_{max_end_str}.xlsx"
        master_filepath = os.path.join(report_dir, master_filename)
        
        master_df.to_excel(master_filepath, index=False)
        log.info(f"🎉 [SUCCESS] Master report created: {master_filepath}")
        log.info(f"   Total rows: {len(master_df)}")

        # ── 6. Phase 5: Distribution to Google Sheets ──────────────────────
        apps_script_url = os.getenv("APPS_SCRIPT_URL")
        if apps_script_url:
            log.info("📤 [PROGRESS] PHASE 5: Sending data to Google Sheets...")
            
            # Mapping columns to match 'Shopee' sheet headers
            # Target Headers: Flag,Month,Store ID,Store name,Transaction type,Transaction ID (Order ID),Complete Time,Status,Food original price,Item discounts,Flash sale discount,Surcharge fee,Merchant Voucher Deals Subsidy,Platform Flash Sale Subsidy,Food Voucher Subsidy,Food Direct Discount,Transaction amount,Checkout Murah Price,Notes,Net Sales,Commission,Revenue,Move to OE/OP
            
            # Prepare data for mapping
            dist_df = master_df.copy()
            
            # Calculate Month and Flag
            def get_month_from_str(date_str):
                try:
                    # Date format is "YYYY-MM-DD at HH:MM"
                    return date_str.split(" ")[0][:7] # YYYY-MM
                except:
                    return ""

            dist_df["Flag"] = "Final OP"
            dist_df["Month"] = dist_df["Waktu Penyelesaian"].apply(get_month_from_str)
            dist_df["Net Sales"] = dist_df["Harga Makanan"] - dist_df["Diskon"]
            dist_df["Move to OE/OP"] = ""

            mapping = {
                "Flag": "Flag",
                "Month": "Month",
                "Store ID": "Store ID",
                "Nama Toko": "Store name",
                "Tipe Transaksi": "Transaction type",
                "No. Pesanan": "Transaction ID (Order ID)",
                "Waktu Penyelesaian": "Complete Time",
                "Status": "Status",
                "Harga Makanan": "Food original price",
                "Diskon": "Item discounts",
                "Diskon Flash Sale": "Flash sale discount",
                "Biaya Tambahan": "Surcharge fee",
                "Subsidi Merchant untuk Voucher Deals": "Merchant Voucher Deals Subsidy",
                "Subsidi Platform untuk Flash Sale": "Platform Flash Sale Subsidy",
                "Subsidi Voucher Makanan": "Food Voucher Subsidy",
                "Diskon Langsung": "Food Direct Discount",
                "Nilai Transaksi": "Transaction amount",
                "Harga Checkout Murah": "Checkout Murah Price",
                "Notes": "Notes",
                "Net Sales": "Net Sales",
                "Commission": "Commission",
                "Revenue": "Revenue",
                "Move to OE/OP": "Move to OE/OP"
            }

            # Select and rename columns
            final_df = dist_df[list(mapping.keys())].rename(columns=mapping)
            
            # Convert to list of dicts for JSON (Handle NaN values)
            payload = final_df.fillna("").to_dict(orient="records")
            
            # Send to Apps Script with retries
            success_send = False
            for send_attempt in range(3):
                try:
                    response = requests.post(
                        f"{apps_script_url}?sheet=Shopee",
                        json=payload,
                        timeout=90 # Increased timeout
                    )
                    if response.status_code == 200:
                        res_json = response.json()
                        if res_json.get("status") == "success":
                            log.info(f"✅ [SUCCESS] Sent {res_json.get('rows_added')} rows to Shopee sheet.")
                            success_send = True
                            break
                        else:
                            log.error(f"❌ [ERROR] Apps Script error: {res_json.get('message')}")
                            break # If it's a logic error, don't retry
                    else:
                        log.warning(f"⚠️ Failed to send data (Attempt {send_attempt+1}/3): HTTP {response.status_code}")
                except Exception as e:
                    log.warning(f"⚠️ Connection error to Apps Script (Attempt {send_attempt+1}/3): {e}")
                
                if send_attempt < 2:
                    time.sleep(10)
            
            if not success_send:
                log.error("❌ Failed to send data to Google Sheets after multiple attempts.")
        else:
            log.warning("⚠️ [SKIP] APPS_SCRIPT_URL not found in .env. Skipping distribution.")

    driver.quit()


if __name__ == "__main__":
    run_pipeline()
