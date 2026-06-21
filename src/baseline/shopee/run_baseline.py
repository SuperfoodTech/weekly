import os
import time
import json
import pandas as pd
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../shopee-omzet-automation'))) # Path to core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))) # Path to database manager

from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests

from pathlib import Path
try:
    sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
    from discord_notifier import send_discord_error
except:
    def send_discord_error(*args, **kwargs): pass


from core.browser import get_session, return_to_selector, refresh_tokens, auto_switch_merchant
from core.client import ShopeeClient
from core.logger import get_logger
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# Load environment variables
load_dotenv()
log = get_logger("omzet_pipeline")

# --- Toggle Konfigurasi Global ---
ENABLE_GSHEETS_PUSH = False   # Set ke True untuk mengizinkan unggah ke Google Sheets
ENABLE_POSTGRES_PUSH = False  # Set ke True untuk mengizinkan unggah ke PostgreSQL (Tabel Gajah)

def robust_read_csv(path_or_url, expected_cols=None, **kwargs):
    """
    Reads a CSV file or URL robustly.
    1. Normalizes all column headers to lowercase and strips whitespace.
    2. Gracefully handles unquoted commas by parsing line-by-line and merging extra columns.
    """
    import csv
    import io
    import pandas as pd
    import requests

    content = ""
    try:
        if isinstance(path_or_url, str) and (path_or_url.startswith("http://") or path_or_url.startswith("https://")):
            import time
            cache_buster = f"&t={int(time.time())}" if "?" in path_or_url else f"?t={int(time.time())}"
            resp = requests.get(path_or_url + cache_buster, timeout=30)
            resp.raise_for_status()
            content = resp.text
        else:
            with open(path_or_url, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
    except Exception as e:
        log.error(f"Failed to read source {path_or_url}: {e}")
        raise e

    try:
        df = pd.read_csv(io.StringIO(content), **kwargs)
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    except Exception as parse_err:
        log.warning(f"Standard pandas read_csv failed: {parse_err}. Retrying with robust line parsing...")
        try:
            lines = content.splitlines()
            if not lines:
                return pd.DataFrame()
            header_reader = csv.reader([lines[0]], skipinitialspace=True)
            headers = [c.strip().lower() for c in next(header_reader)]
            num_cols = len(headers) if expected_cols is None else expected_cols
            
            rows = []
            for line in lines[1:]:
                if not line.strip():
                    continue
                row_reader = csv.reader([line], skipinitialspace=True)
                try:
                    row = next(row_reader)
                except Exception:
                    row = [val.strip() for val in line.split(",")]
                
                if len(row) > num_cols:
                    extra_count = len(row) - num_cols
                    if num_cols == 9:  # Master sheet: merge 'merchant name' (index 5)
                        merchant_name_val = ", ".join(row[5:6 + extra_count])
                        row = row[:5] + [merchant_name_val] + row[6 + extra_count:]
                    elif num_cols == 4:  # Credentials sheet: merge 'bd' (index 3)
                        bd_val = ", ".join(row[3:])
                        row = row[:3] + [bd_val]
                elif len(row) < num_cols:
                    row += [""] * (num_cols - len(row))
                    
                rows.append(row[:num_cols])
            
            df = pd.DataFrame(rows, columns=headers[:num_cols])
            return df
        except Exception as fallback_err:
            log.error(f"Fallback robust parsing failed: {fallback_err}")
            raise parse_err

def subtract_months(dt, months):
    """Helper to subtract calendar months."""
    for _ in range(months):
        dt = (dt - timedelta(days=1)).replace(day=1)
    return dt

def resolve_bd_to_names_and_usernames(bd_filter, max_age_hours=24):
    if not bd_filter:
        return [], []
        
    import os
    import time
    import requests
    import pandas as pd
    
    creds_cache = "data/shopee_credentials_cache.csv"
    creds_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRYSUnKOqk29LCktTxdb0wPLbWMbRaWRP3eC_UA4AwYod1FW6zDMhtLMC5ghIvot2B8upCDfBsn-TCP/pub?gid=565510790&single=true&output=csv"
    
    try:
        resp = requests.get(creds_url, timeout=10)
        resp.raise_for_status()
        with open(creds_cache, "w", encoding="utf-8") as f:
            f.write(resp.text)
    except Exception as e:
        log.warning(f"⚠️ Failed to download credentials in resolve_bd_to_names_and_usernames: {e}. Will use cache if available.")
            
    if not os.path.exists(creds_cache):
        inputs = [b.strip().lower() for b in bd_filter.split("|")]
        return inputs, inputs
        
    try:
        df_creds = robust_read_csv(creds_cache)
        inputs = [b.strip().lower() for b in bd_filter.split("|")]
        resolved_users = []
        resolved_bds = []
        
        for inp in inputs:
            clean_inp = inp
            if clean_inp.startswith("bd "):
                clean_inp = clean_inp[3:].strip()
                
            matched = False
            for _, row in df_creds.iterrows():
                username_val = str(row.get('username', '')).strip().lower()
                bd_val = str(row.get('bd', '')).strip().lower()
                clean_bd = bd_val
                if clean_bd.startswith("bd "):
                    clean_bd = clean_bd[3:].strip()
                    
                if clean_bd == clean_inp or bd_val == inp or username_val == inp:
                    if username_val and username_val != 'nan':
                        resolved_users.append(username_val)
                    if bd_val and bd_val != 'nan':
                        resolved_bds.append(bd_val)
                        if clean_bd != bd_val:
                            resolved_bds.append(clean_bd)
                    matched = True
            if not matched:
                resolved_users.append(inp)
                resolved_bds.append(inp)
                
        resolved_users = list(set(resolved_users))
        resolved_bds = list(set(resolved_bds))
        return resolved_users, resolved_bds
    except Exception as e:
        log.error(f"⚠️ Error resolving BD filter: {e}")
        inputs = [b.strip().lower() for b in bd_filter.split("|")]
        return inputs, inputs

def resolve_bd_to_usernames(bd_filter, max_age_hours=24):
    users, _ = resolve_bd_to_names_and_usernames(bd_filter, max_age_hours)
    return users

def get_live_merchants(app_name="ShopeeFood", max_age_hours=24, merchant_filter=None, bd_filter=None):
    """
    Fetches live merchants from Google Sheets and caches them locally.
    Uses cached data if it's less than max_age_hours old.
    """
    import os
    from datetime import datetime
    
    url = "https://docs.google.com/spreadsheets/d/14eCb8DAEXhmbYj9MFj2KzC7AhkulbCbSNPltN2m-go0/export?format=csv&gid=880434015"
    cache_path = "data/master_merchants_cache.csv"
    os.makedirs("data", exist_ok=True)
    
    df = None
    try:
        log.info("🌐 [DATA] Downloading fresh merchant list from Google Sheets...")
        df = robust_read_csv(url, expected_cols=9)
        df.to_csv(cache_path, index=False)
    except Exception as download_err:
        log.warning(f"⚠️ [DATA] Failed to download fresh merchant list: {download_err}. Trying cache...")
        if os.path.exists(cache_path):
            df = robust_read_csv(cache_path, expected_cols=9)
        else:
            log.error(f"❌ [DATA] No cache available and download failed.")
            return []

    if df is not None:
        try:
            sf_df = df[df['aplikasi'] == app_name]
            
            if bd_filter:
                resolved_users, resolved_bds = resolve_bd_to_names_and_usernames(bd_filter, max_age_hours)
                mask_user = sf_df['nama pengguna'].astype(str).str.strip().str.lower().isin(resolved_users)
                mask_bd = pd.Series(False, index=sf_df.index)
                if 'bd' in sf_df.columns:
                    mask_bd = sf_df['bd'].astype(str).str.strip().str.lower().isin(resolved_bds)
                sf_df = sf_df[mask_user | mask_bd]
            
            if merchant_filter:
                if "|" in merchant_filter:
                    filter_vals = [m.strip().lower().rstrip('_') for m in merchant_filter.split("|")]
                    sf_df = sf_df[sf_df['merchant name'].str.strip().str.lower().str.rstrip('_').isin(filter_vals)]
                else:
                    filter_val = merchant_filter.strip().lower().rstrip('_')
                    sf_df = sf_df[sf_df['merchant name'].str.strip().str.lower().str.rstrip('_') == filter_val]
                
            sf_df = sf_df[(sf_df['merchant name'] != '-') & (sf_df['merchant name'].notna())]
            sf_df = sf_df.drop_duplicates(subset=['merchant name'])
            return sf_df['merchant name'].tolist()
        except Exception as e:
            log.error(f"⚠️ Failed to parse merchants: {e}")
            return []
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
                send_discord_error(
                    platform="Shopee", 
                    merchant=filename.split("/")[-1], 
                    error_type="DOWNLOAD_FAILED", 
                    message=f"Gagal mengunduh file laporan Excel dari Shopee Partner setelah {max_retries} percobaan: {e}"
                )
    return False


def get_shopee_baseline_credentials(merchant_name, max_age_hours=24):
    """
    Fetches the credentials for a merchant's BD by checking Google Sheets:
    Sheet 1: Master Merchants (to find BD name associated with merchant_name)
    Sheet 2: Shopee Credentials (to find shopee credentials for that BD name)
    """
    import os
    import time
    import pandas as pd
    import requests
    
    # Fallback/Default credentials
    phone_fallback    = os.getenv("SHOPEE_PHONE", "").strip()
    username_fallback = os.getenv("SHOPEE_USERNAME", "").strip()
    password_fallback = os.getenv("SHOPEE_PASSWORD", "").strip()
    
    if not username_fallback or not password_fallback:
        try:
            from pathlib import Path
            import json
            for parent in Path(__file__).resolve().parents:
                cred_file = parent / "credentials.json"
                if cred_file.exists():
                    with open(cred_file, "r") as f:
                        creds = json.load(f)
                        if not username_fallback:
                            username_fallback = creds.get("shopee_username", "").strip()
                        if not password_fallback:
                            password_fallback = creds.get("shopee_password", "").strip()
                        if not phone_fallback:
                            phone_fallback = creds.get("shopee_phone", "").strip()
                    break
        except Exception:
            pass
            
    default_creds = {
        "username": username_fallback or "allvbadmin",
        "password": password_fallback or "Shopee@321",
        "phone": phone_fallback or "6285136517286"
    }
    
    cache_merchants = "data/master_merchants_cache.csv"
    cache_creds = "data/shopee_credentials_cache.csv"
    os.makedirs("data", exist_ok=True)
    
    url_merchants = "https://docs.google.com/spreadsheets/d/14eCb8DAEXhmbYj9MFj2KzC7AhkulbCbSNPltN2m-go0/export?format=csv&gid=880434015"
    url_creds = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRYSUnKOqk29LCktTxdb0wPLbWMbRaWRP3eC_UA4AwYod1FW6zDMhtLMC5ghIvot2B8upCDfBsn-TCP/pub?gid=565510790&single=true&output=csv"
    
    def check_and_download(url, cache_path):
        log.info(f"🌐 [CREDENTIALS] Downloading fresh data from: {url}")
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(resp.text)
        except Exception as e:
            log.warning(f"⚠️ [CREDENTIALS] Failed to download {url}: {e}. Will use cache if available.")
            if not os.path.exists(cache_path):
                raise e
                    
    try:
        check_and_download(url_merchants, cache_merchants)
        check_and_download(url_creds, cache_creds)
        
        df_merchants = robust_read_csv(cache_merchants, expected_cols=9)
        df_creds = robust_read_csv(cache_creds, expected_cols=4)
        
        def _normalize(name):
            if pd.isna(name):
                return ""
            return str(name).strip().lower().rstrip('_').strip()
            
        # Match norm_merchant in sf_merchants
        df_merchants['norm_name'] = df_merchants['merchant name'].apply(_normalize)
        norm_merchant = _normalize(merchant_name)
        
        matched_rows = df_merchants[
            (df_merchants['norm_name'] == norm_merchant) &
            (df_merchants['aplikasi'].str.contains("Shopee", na=False, case=False))
        ]
        
        if matched_rows.empty:
            log.warning(f"⚠️ [CREDENTIALS] Merchant '{merchant_name}' not found in Master list. Using default credentials.")
            return default_creds
            
        username = str(matched_rows.iloc[0].get('nama pengguna', '')).strip()
        password = str(matched_rows.iloc[0].get('kata sandi', '')).strip()
        
        if not username or pd.isna(username) or username == "" or username == "-":
            log.info(f"ℹ️ [CREDENTIALS] No username assigned to merchant '{merchant_name}'. Using default credentials.")
            return default_creds
            
        if not password or pd.isna(password):
            password = default_creds.get("password")
            
        # Look up phone number from df_creds
        norm_username = _normalize(username)
        df_creds['norm_username'] = df_creds['username'].fillna("").apply(_normalize)
        
        matched_cred = df_creds[df_creds['norm_username'] == norm_username]
        if matched_cred.empty:
            log.warning(f"⚠️ [CREDENTIALS] Username '{username}' has no mapped credentials in Credentials sheet. Trying default phone.")
            phone = default_creds.get("phone")
        else:
            row_cred = matched_cred.iloc[0]
            phone = str(row_cred.get('phone', '')).strip()
            
        if phone.startswith("+"):
            phone = phone[1:]
            
        log.info(f"🔑 [CREDENTIALS] Successfully mapped '{merchant_name}' to staff account '{username}' (Phone: {phone})")
        return {
            "username": username,
            "password": password,
            "phone": phone
        }
    except Exception as e:
        log.error(f"❌ [CREDENTIALS] Error resolving credentials for '{merchant_name}': {e}. Using default.")
        return default_creds

def process_bd_group(username, group_info, global_ranges, report_dir, headless):
    creds = group_info["creds"]
    group_merchants = group_info["merchants"]
    
    log.info(f"🚀 [GROUP - {username}] Starting processing with {len(group_merchants)} merchants...")
    
    # Set dynamic session file Path inside core.browser
    import core.browser
    from pathlib import Path
    shopee_omzet_dir = Path(core.browser.__file__).resolve().parent.parent
    core.browser.set_session_file(shopee_omzet_dir / "data" / f"session_{username}.json")
    
    driver = None
    try:
        # ── Phase 1: Rapid Trigger ────
        log.info(f"🚀 [GROUP - {username}] PHASE 1: Triggering Exports ({len(group_merchants)} merchants)...")
        
        session_data = get_session(
            username=creds["username"], 
            password=creds["password"], 
            phone=creds["phone"], 
            headless=headless, 
            close_browser=False, 
            target_name=group_merchants[0]
        )
        if not session_data:
            log.error(f"❌ [GROUP - {username}] Failed to get session. Skipping group.")
            return False
        driver = session_data.get("driver")
        
        merchants_context = {} # Store tokens/ids for each merchant
        
        for i, merchant_name in enumerate(group_merchants):
            log.info(f"  [{username}] [{i+1}/{len(group_merchants)}] Triggering: {merchant_name}")
            
            # Switch if not already there
            if i > 0:
                switch_success = False
                for retry in range(2):
                    if auto_switch_merchant(driver, merchant_name):
                        switch_success = True
                        break
                    else:
                        log.warning(f"  [{username}] Retrying switch for {merchant_name} (Attempt {retry+2}/2)...")
                        time.sleep(3)
                
                if not switch_success:
                    log.warning(f"  [{username}] Skipping {merchant_name} after 2 failed switch attempts.")
                    continue
                time.sleep(3) # Wait for cookies to sync
            
            # Get tokens and VERIFY ID
            session = refresh_tokens(driver)
            active_id = str(session.get("shopee_tob_entity_id") or "")
            
            # Double check if the ID actually changed from previous
            if i > 0 and active_id == merchants_context.get(group_merchants[i-1], {}).get("entity_id"):
                 log.warning(f"  [{username}] ID hasn't changed yet. Retrying token refresh...")
                 time.sleep(3)
                 session = refresh_tokens(driver)
                 active_id = str(session.get("shopee_tob_entity_id") or "")
                 
            log.debug(f"  [{username}] Confirmed ID for {merchant_name}: {active_id}")
            
            # Store context for polling
            merchants_context[merchant_name] = {
                "entity_id": active_id,
                "tob_token": session["shopee_tob_token"],
                "cookies": session.get("extra_cookies", {}),
                "start_trigger_time": int(time.time())
            }
            
            # Initialize client and trigger
            client = ShopeeClient(tob_token=session["shopee_tob_token"], entity_id=active_id, extra_cookies=session.get("extra_cookies", {}))
            
            # Assign ranges
            ranges = global_ranges
            merchants_context[merchant_name]["ranges"] = ranges
            merchants_context[merchant_name]["downloaded"] = []
            
            # Trigger with retry
            for r in ranges:
                success = False
                for trigger_retry in range(3):
                    res = client.export_transaction_report(merchant_ids=[active_id], start_time=r["start"], end_time=r["end"])
                    if res is True:
                        success = True
                        break
                    elif res is None: # Network Error
                        log.warning(f"  [{username}] Network error during trigger for {merchant_name}. Retrying in 10s... ({trigger_retry+1}/3)")
                        time.sleep(10)
                    else: # API Error
                        break
                if not success:
                    log.error(f"  [{username}] Failed to trigger export for {merchant_name} range {r.get('label')}")
                time.sleep(1)
        
        # ── Phase 2: Global Polling & Download ────
        log.info(f"⏳ [GROUP - {username}] PHASE 2: Global Polling...")
        os.makedirs(report_dir, exist_ok=True)
        
        total_expected = len(merchants_context) * len(global_ranges)
        download_count = 0
        start_poll = time.time()
        
        consecutive_network_errors = 0
        poll_iteration = 0
        while download_count < total_expected and (time.time() - start_poll) < 1800:
            found_new = False
            poll_iteration += 1
            has_network_issue = False
            
            for m_name, ctx in merchants_context.items():
                if len(ctx["downloaded"]) >= len(global_ranges): continue
                
                client = ShopeeClient(tob_token=ctx["tob_token"], entity_id=ctx["entity_id"], extra_cookies=ctx["cookies"])
                reports = client.get_report_list()
                
                if reports is None: # Network Error
                    has_network_issue = True
                    continue
                    
                consecutive_network_errors = 0
                for rep in reports:
                    if rep.get("status") in [2, 3] and rep.get("download_url"):
                        if rep.get("create_time", 0) and rep["create_time"] >= ctx["start_trigger_time"]:
                            report_name = rep.get("name", f"report_{rep.get('id')}.xlsx")
                            target_path = os.path.join(report_dir, f"{m_name.replace(' ', '_')}_{report_name}")
                            
                            if target_path not in [d[0] for d in ctx["downloaded"]]:
                                if download_file(rep.get("download_url"), target_path):
                                    log.info(f"  [{username}] [DOWNLOAD] SUCCESS: {m_name} -> {report_name}")
                                    ctx["downloaded"].append((target_path, report_name))
                                    download_count += 1
                                    found_new = True
                
                if not found_new and poll_iteration % 3 == 0:
                     log.info(f"  [{username}] Waiting for {m_name}... ({len(ctx['downloaded'])}/{len(global_ranges)} ready)")
                     
            if has_network_issue:
                consecutive_network_errors += 1
                wait_time = min(10 * (2 ** (consecutive_network_errors - 1)), 60)
                log.warning(f"  [{username}] [NETWORK] API connection issues detected. Waiting {wait_time}s before next poll...")
                time.sleep(wait_time)
            elif download_count < total_expected:
                time.sleep(10)
        
        log.info(f"📋 [GROUP - {username}] Download Phase Complete. Summary:")
        for m_name, ctx in merchants_context.items():
            log.info(f"  🏪 {m_name}: {len(ctx['downloaded'])}/{len(global_ranges)} files")
            for fpath, label in ctx["downloaded"]:
                log.info(f"     📄 {fpath}")
        return download_count >= total_expected
        
    except Exception as e:
        log.error(f"❌ [GROUP - {username}] Error during processing: {e}")
        return False
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception as e:
                log.debug(f"Failed to quit driver: {e}")


def run_pipeline():
    import argparse
    parser = argparse.ArgumentParser(description="Shopee Omzet Baseline Pipeline")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)", default=None)
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)", default=None)
    parser.add_argument("--output-dir", type=str, help="Override output directory for reports", default=None)
    parser.add_argument("--skip-download", action="store_true", help="Skip browser automation and only process/merge raw files in output directory")
    parser.add_argument("--merchant", type=str, help="Filter specific merchant name to run", default=None)
    parser.add_argument("--bd", type=str, help="Filter specific BD name to run", default=None)
    args = parser.parse_args()

    # Determine output directory
    report_dir = args.output_dir or "data/reports/baseline"

    # Pre-run cleanup of old Excel files in custom or download runs to ensure clean master aggregation
    import glob
    if not args.skip_download and os.path.exists(report_dir):
        if args.merchant:
            m_underscored = args.merchant.replace(' ', '_').replace('|', '_')
            if len(m_underscored) > 50:
                old_excels = glob.glob(os.path.join(report_dir, "BASELINE_MASTER_SHOPEE*.xlsx"))
            else:
                old_excels = glob.glob(os.path.join(report_dir, f"*{m_underscored}*.xlsx"))
        else:
            old_excels = glob.glob(os.path.join(report_dir, "*.xlsx"))
            
        if old_excels:
            log.info(f"🧹 Clearing {len(old_excels)} old Excel files in {report_dir} to prepare for fresh run...")
            for f in old_excels:
                try: os.unlink(f)
                except Exception as e: log.debug(f"Failed to delete {f}: {e}")

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
    print(f"  Shopee Omzet - BASELINE Report Pipeline")
    print(f"  Range: {label}")
    print("=" * 60)

    # Load headless setting from config.json walk-up
    headless = True
    try:
        from pathlib import Path
        import json
        for parent in Path(__file__).resolve().parents:
            config_file = parent / "config.json"
            if config_file.exists():
                with open(config_file, "r") as f:
                    headless = json.load(f).get("headless_shopee", True)
                break
    except Exception:
        pass

    if os.environ.get("HEADLESS") == "true":
        headless = True

    # ── 1. Determine Merchants to Process (Data-Driven via G-Sheets) ────
    target_merchants = get_live_merchants(app_name="ShopeeFood", max_age_hours=24, merchant_filter=args.merchant, bd_filter=args.bd)
    log.info(f"📋 [PROGRESS] Found {len(target_merchants)} live merchants ready to process.")

    if not target_merchants:
        log.error("❌ No merchants to process. Aborting.")
        send_discord_error(
            platform="Shopee", 
            merchant="Global", 
            error_type="NO_DATA", 
            message="Gagal memproses data outlet. Master data Google Sheet kosong atau koneksi API Database gagal terhubung."
        )
        return

    if args.skip_download:
        log.info("⏭️ [SKIP] Bypassing browser download phase (Phases 1 & 2) as --skip-download is enabled.")
    else:
        # Group target merchants by resolved credentials username
        merchants_by_user = {}
        for m_name in target_merchants:
            creds = get_shopee_baseline_credentials(m_name)
            u = creds["username"]
            if u not in merchants_by_user:
                merchants_by_user[u] = {
                    "creds": creds,
                    "merchants": []
                }
            merchants_by_user[u]["merchants"].append(m_name)
            
        log.info(f"🚀 [PARALLEL] Processing {len(merchants_by_user)} credentials groups concurrently (max 4 workers)...")
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        with ThreadPoolExecutor(max_workers=min(4, len(merchants_by_user))) as executor:
            futures = {
                executor.submit(process_bd_group, username, group_info, global_ranges, report_dir, headless): username
                for username, group_info in merchants_by_user.items()
            }
            
            for future in as_completed(futures):
                u = futures[future]
                try:
                    success = future.result()
                    if success:
                        log.info(f"✅ [GROUP - {u}] Completed successfully.")
                    else:
                        log.error(f"❌ [GROUP - {u}] Processing failed.")
                except Exception as e:
                    log.error(f"❌ [GROUP - {u}] Processing raised exception: {e}")
    # ── 4. Phase 3: Scanning and Validating ALL Raw Files in report folder ──
    log.info("📊 [PROGRESS] PHASE 3: Scanning and Validating ALL Raw Files in report folder...")
    all_analyzed_data = []
    
    # Get all xlsx files in report_dir
    import glob
    xlsx_files = glob.glob(os.path.join(report_dir, "*.xlsx"))
    
    # Sort files to ensure deterministic merging order
    xlsx_files.sort()
    
    for fpath in xlsx_files:
        filename = os.path.basename(fpath)
        
        # Skip Master and Analyzed reports
        if filename.startswith("Master_") or filename.endswith("_Analyzed.xlsx"):
            continue
            
        # Determine Merchant Name from filename
        matched_merchant = None
        for m in target_merchants:
            m_underscored = m.replace(' ', '_')
            # Check if filename starts with underscored merchant name followed by underscore
            if filename.startswith(m_underscored + "_"):
                matched_merchant = m
                break
                
        if not matched_merchant:
            # Skip files that do not match the current target merchants to prevent merging them!
            log.info(f"  ⏭️ [SKIP] Raw file '{filename}' does not belong to target merchants. Skipping.")
            continue
                
        try:
            # Pengecekan apakah file memiliki data (tidak kosong)
            df = pd.read_excel(fpath, dtype=str)
            
            if df.empty or len(df) == 0:
                log.warning(f"  ⚠️ [CHECK] Raw file '{filename}' is EMPTY (no transaction rows). Skipping merger.")
                continue
                
            if "Nilai Transaksi" in df.columns and "Harga Makanan" in df.columns:
                log.info(f"  🔍 [CHECK] Raw file '{filename}' has {len(df)} rows. Processing & including in MASTER...")
                # List of exact monetary columns in ShopeeFood reports
                monetary_cols = [
                    'Harga Makanan', 'Diskon', 'Diskon Flash Sale', 'Biaya Tambahan', 
                    'Subsidi Merchant untuk Voucher Deals', 'Subsidi Platform untuk Flash Sale', 
                    'Subsidi Voucher Makanan', 'Diskon Langsung', 'Nilai Transaksi', 
                    'Harga Checkout Murah'
                ]
                
                # Fix monetary columns: handle Shopee's inconsistent thousand separator/decimal format
                def clean_shopee_monetary(val):
                    if pd.isna(val) or str(val).lower() == 'nan': return 0
                    s = str(val).strip()
                    if not s or s == '-': return 0
                    
                    import re
                    s = re.sub(r'[^\d\.\,\-]', '', s)
                    if not s or s == '-': return 0

                    has_dot = '.' in s
                    has_comma = ',' in s
                    try:
                        if has_dot and has_comma:
                            if s.rfind(',') > s.rfind('.'):
                                s = s.split(',')[0].replace('.', '')
                            else:
                                s = s.split('.')[0].replace(',', '')
                            return int(s)
                        elif has_dot:
                            parts = s.split('.')
                            if len(parts[-1]) == 3:
                                return int(s.replace('.', ''))
                            else:
                                return int(float(s))
                        elif has_comma:
                            parts = s.split(',')
                            if len(parts[-1]) == 3:
                                return int(s.replace(',', ''))
                            else:
                                return int(float(s.replace(',', '.')))
                        else:
                            return int(s)
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
                df.insert(0, "Merchant Name", matched_merchant)
                
                # Fix scientific notation for Order IDs
                if "No. Pesanan" in df.columns:
                    df["No. Pesanan"] = df["No. Pesanan"].astype(str).str.replace(r'\.0$', '', regex=True)
                    
                # Reformat Waktu Penyelesaian from "07 Mei 2026 23:16" to "2026-05-07 at 23:16"
                if "Waktu Penyelesaian" in df.columns:
                    indo_months = {
                        'Januari': 'Jan', 'Februari': 'Feb', 'Maret': 'Mar', 
                        'April': 'Apr', 'Mei': 'May', 'Juni': 'Jun', 'Juli': 'Jul', 
                        'Agustus': 'Aug', 'September': 'Sep', 'Oktober': 'Oct', 
                        'November': 'Nov', 'Desember': 'Dec',
                        'Jan': 'Jan', 'Feb': 'Feb', 'Mar': 'Mar', 'Apr': 'Apr',
                        'Jun': 'Jun', 'Jul': 'Jul', 'Ags': 'Aug', 'Agu': 'Aug',
                        'Sep': 'Sep', 'Okt': 'Oct', 'Nov': 'Nov', 'Des': 'Dec'
                    }
                    temp_dates = df["Waktu Penyelesaian"].astype(str)
                    for indo, eng in sorted(indo_months.items(), key=lambda x: len(x[0]), reverse=True):
                        temp_dates = temp_dates.str.replace(indo, eng, case=False, regex=False)
                    
                    # Parse to datetime using robust explicit format or fallback to generic parsing
                    parsed_dates = pd.to_datetime(temp_dates, format='%d %b %Y %H:%M', errors='coerce')
                    
                    # For dates that failed to parse with the specific format, try generic parsing
                    if parsed_dates.isna().any():
                        failed_mask = parsed_dates.isna()
                        parsed_dates.loc[failed_mask] = pd.to_datetime(temp_dates.loc[failed_mask], errors='coerce', dayfirst=True)
                        
                    # Where parsing succeeded, apply the new format. Where it failed, keep original.
                    df["Waktu Penyelesaian"] = parsed_dates.dt.strftime('%Y-%m-%d %H:%M').fillna(df["Waktu Penyelesaian"])
                    
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
                
                # Save individual analyzed report
                out_path = fpath.replace(".xlsx", "_Analyzed.xlsx")
                df.to_excel(out_path, index=False)
                log.info(f"     ✅ [DATA] Saved analyzed data: {os.path.basename(out_path)}")
                
                all_analyzed_data.append(df)
            else:
                log.warning(f"  ⚠️ [CHECK] Raw file '{filename}' is missing required columns. Skipping.")
        except Exception as e:
            log.error(f"  ❌ Error processing '{filename}': {e}")

    # ── 5. Phase 4: Master Aggregation (Baseline Logic) ───────────────────────────────────
    if all_analyzed_data:
        log.info("📑 [PROGRESS] PHASE 4: Combining all analyzed reports and applying Baseline Pivot...")
        master_df = pd.concat(all_analyzed_data, ignore_index=True)
        
        # --- APPLY BASELINE LOGIC ---
        working = master_df.copy()

        if "Waktu Penyelesaian" in working.columns:
            # First try the standardized format, then fallback to generic parsing for any that fail
            working["Updated On"] = pd.to_datetime(working["Waktu Penyelesaian"], format="%Y-%m-%d %H:%M", errors="coerce")
            if working["Updated On"].isna().any():
                failed_mask = working["Updated On"].isna()
                working.loc[failed_mask, "Updated On"] = pd.to_datetime(working.loc[failed_mask, "Waktu Penyelesaian"], errors="coerce", dayfirst=True)
        else:
            working["Updated On"] = pd.NaT

        if "No. Pesanan" in working.columns:
            working["Long Order ID"] = working["No. Pesanan"].fillna("").astype(str).str.strip()
        else:
            working["Long Order ID"] = ""
            
        if "Status" in working.columns:
            working["Status"] = working["Status"].fillna("").astype(str).str.strip().str.casefold()
        else:
            working["Status"] = ""
            
        if "Net Sales" not in working.columns:
            if "Harga Makanan" in working.columns:
                harga_makanan = pd.to_numeric(working["Harga Makanan"], errors="coerce").fillna(0)
                diskon = pd.to_numeric(working["Diskon"], errors="coerce").fillna(0) if "Diskon" in working.columns else 0
                diskon_fs = pd.to_numeric(working["Diskon Flash Sale"], errors="coerce").fillna(0) if "Diskon Flash Sale" in working.columns else 0
                working["Net Sales"] = harga_makanan - diskon - diskon_fs
            else:
                working["Net Sales"] = pd.to_numeric(working["Nilai Transaksi"], errors="coerce").fillna(0)
        else:
            working["Net Sales"] = pd.to_numeric(working["Net Sales"], errors="coerce").fillna(0)
        
        # Aturan validasi: ID pesanan valid dan bukan dibatalkan
        valid_long_order_id = working["Long Order ID"].str.match(r"^[A-Za-z0-9-]+$", na=False)
        is_not_cancelled = ~working["Status"].str.contains("batal|cancel", na=False, case=False)
        
        valid_orders = working.loc[valid_long_order_id & is_not_cancelled].copy()
        
        if "Updated On" in valid_orders.columns:
            valid_orders = valid_orders.loc[valid_orders["Updated On"].notna()].copy()

        # Filter Custom Date Range
        if args.start and "Updated On" in valid_orders.columns:
            valid_orders = valid_orders.loc[valid_orders["Updated On"] >= pd.Timestamp(args.start)].copy()
        if args.end and "Updated On" in valid_orders.columns:
            end_ts = pd.Timestamp(args.end).replace(hour=23, minute=59, second=59)
            valid_orders = valid_orders.loc[valid_orders["Updated On"] <= end_ts].copy()

        if valid_orders.empty:
            log.warning("⚠️ Tidak ada transaksi valid yang masuk dalam range tanggal dan filter ini untuk dihitung baseline-nya.")
            return

        valid_orders["Month"] = valid_orders["Updated On"].dt.to_period("M").dt.to_timestamp()

        # Aggregate by Merchant and Month
        summary = (
            valid_orders.groupby(["Merchant Name", "Month"], as_index=False)
            .agg(
                Order_Count=("Long Order ID", "count"),
                Omzet_Net_Sales=("Net Sales", "sum"),
            )
            .sort_values(["Merchant Name", "Month"])
            .reset_index(drop=True)
        )

        # Convert to Wide Format
        months = sorted(summary["Month"].unique())
        wide_rows = []
        
        for merchant, group in summary.groupby("Merchant Name"):
            row = {"Merchant": merchant}
            total_omzet = 0.0
            total_order = 0
            
            for idx, month in enumerate(months, start=1):
                month_data = group[group["Month"] == month]
                if not month_data.empty:
                    omzet = float(month_data["Omzet_Net_Sales"].iloc[0])
                    order = int(month_data["Order_Count"].iloc[0])
                else:
                    omzet = 0.0
                    order = 0
                    
                row[f"Omzet Bulan ke-{idx}"] = omzet
                row[f"Order Bulan ke-{idx}"] = order
                
                total_omzet += omzet
                total_order += order
                
            num_months = len(months)
            row["Rata-rata Omzet"] = total_omzet / num_months if num_months > 0 else 0.0
            row["Rata-rata Order"] = round(total_order / num_months) if num_months > 0 else 0
            
            wide_rows.append(row)

        wide_summary = pd.DataFrame(wide_rows)
        wide_summary.insert(1, "Aplikasi", "Shopee")

        # Output logic
        if args.merchant:
            merchant_safe = str(args.merchant).strip().replace(" ", "_").replace("/", "_").replace("\\", "_").replace("|", "_")
            if len(merchant_safe) > 50:
                master_filename = "BASELINE_MASTER_SHOPEE.xlsx"
            else:
                master_filename = f"BASELINE_CUSTOM_{merchant_safe}.xlsx"
        else:
            master_filename = "BASELINE_MASTER_SHOPEE.xlsx"
            
        master_filepath = os.path.join(report_dir, master_filename)
        
        # Save with formatting
        with pd.ExcelWriter(master_filepath, engine="openpyxl") as writer:
            wide_summary.to_excel(writer, index=False, sheet_name="Baseline Summary")
            
        log.info(f"✓ Laporan Baseline Excel: {master_filepath}")
        log.info(f"  Total merchant diproses: {len(wide_summary)}")

        # Skip push
        log.info("⏭️ [SKIP] Push ke Google Sheets dan database dimatikan secara global untuk mode Baseline.")

        # === UNGGAH KE GOOGLE DRIVE ===
        DRIVE_PARENT_FOLDER_ID = "1kHkd1N3uPRaVYaQKTotEIELaT-_nzCCS"
        subfolder_name = os.path.basename(report_dir)
        
        webhook_url = os.getenv("SHOPEE_DRIVE_UPLOAD_WEBHOOK_URL")
        if webhook_url:
            log.info("\n" + "="*60)
            log.info("  MENGUNGGAH HASIL KE GOOGLE DRIVE (SHOPEE)")
            log.info("="*60)
            
            import base64
            import requests
            import glob
            
            def _upload_file(filepath):
                try:
                    with open(filepath, "rb") as f:
                        encoded = base64.b64encode(f.read()).decode("utf-8")
                    payload = {
                        "parentFolderId": DRIVE_PARENT_FOLDER_ID,
                        "subFolderName": subfolder_name,
                        "fileName": os.path.basename(filepath),
                        "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "fileData": encoded
                    }
                    log.info(f"  Mengunggah: {os.path.basename(filepath)} ...")
                    res = requests.post(webhook_url, json=payload, timeout=60)
                    if res.status_code == 200 and res.json().get("status") == "success":
                        log.info(f"  ✓ Berhasil: {res.json().get('url')}")
                    else:
                        log.error(f"  ✗ Gagal: {res.text}")
                except Exception as e:
                    log.error(f"  ✗ Error mengunggah {os.path.basename(filepath)}: {e}")

            all_excels = glob.glob(os.path.join(report_dir, "*.xlsx"))
            for file_path in all_excels:
                if os.path.exists(file_path):
                    _upload_file(file_path)
                    
            log.info("="*60)
        else:
            log.info("\n⏭️ [SKIP] SHOPEE_DRIVE_UPLOAD_WEBHOOK_URL tidak ditemukan di .env. Lewati proses unggah otomatis ke Google Drive.")

    # Driver cleanup handled in finally block of download phase
    pass


if __name__ == "__main__":
    run_pipeline()
