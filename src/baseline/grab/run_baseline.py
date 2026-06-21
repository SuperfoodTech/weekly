import argparse
import asyncio
import io
import os
import shutil
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
import sys
import os

# --- Toggle Konfigurasi Global ---
ENABLE_GSHEETS_PUSH = False  # Set ke True untuk mengizinkan unggah ke Google Sheets

# Add grab-reportperformance directory to sys.path to allow importing grab_api_scraper
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../grab-reportperformance')))

import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

from grab_api_scraper import run_api_download_for_portal, validate_credentials

# --- Logging Setup ---
def setup_logger():
    os.makedirs("logs", exist_ok=True)
    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = f"logs/grab_run_{timestamp}.log"
    
    # Only clean up non-log files (like old screenshots)
    for f in Path("logs").glob("*"):
        if f.is_file() and not f.name.endswith(".log"):
            try: f.unlink()
            except: pass

    logger = logging.getLogger("GrabAuto")
    logger.setLevel(logging.INFO)
    # Clear existing handlers if any (for notebook/interactive environments)
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File
    fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    return logger

log = setup_logger()

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

CSV_URL = "https://docs.google.com/spreadsheets/d/14eCb8DAEXhmbYj9MFj2KzC7AhkulbCbSNPltN2m-go0/export?format=csv&gid=880434015"

async def run_all(date_start: str = None, date_end: str = None, output_dir: str = None, user_filter: str = None, outlet_filter: str = None, branch_filter: str = None):
    # Reload env just in case
    load_dotenv(override=True)
    
    log.info(f"Fetching merchant list from spreadsheet...")
    try:
        df = robust_read_csv(CSV_URL, expected_cols=9)
        
        # Filter for GrabFood
        grab_df = df[df["aplikasi"].str.contains("grab", na=False, case=False)]
        
        portals = []
        for idx, row in grab_df.iterrows():
            user = row.get("nama pengguna")
            pwd = row.get("kata sandi")
            
            if pd.notna(user) and pd.notna(pwd) and str(user).strip() != "-" and str(pwd).strip() != "-":
                u_str = str(user).strip()
                p_str = str(pwd).strip()
                outlet = str(row.get("nama outlet", "Unknown")).strip()
                
                # Di Master DB, kolom Cabang tidak ada, gunakan Brand
                branch_val = row.get("cabang", row.get("brand", ""))
                branch = str(branch_val).strip() if pd.notna(branch_val) else ""
                
                # Apply custom outlet and branch filters internally
                if outlet_filter:
                    if "|" in outlet_filter:
                        valid_outlets = [o.strip().lower() for o in outlet_filter.split("|")]
                        if str(outlet).strip().lower() not in valid_outlets: continue
                    elif str(outlet).strip().lower() != str(outlet_filter).strip().lower():
                        continue
                if branch_filter:
                    if "|" in branch_filter:
                        valid_branches = [b.strip().lower() for b in branch_filter.split("|")]
                        if str(branch).strip().lower() not in valid_branches: continue
                    elif str(branch).strip().lower() != str(branch_filter).strip().lower():
                        continue
                
                # Smart credential validation
                is_valid, err_msg = validate_credentials(u_str, p_str)
                if not is_valid:
                    log.warning(f"⚠️  [VALIDATION WARNING] Row #{idx+1} for '{outlet} ({branch})' has invalid credentials: {err_msg}")
                    
                portals.append({
                    "id": len(portals) + 1,
                    "outlet": outlet,
                    "branch": branch,
                    "user": u_str,
                    "pwd": p_str
                })

        
    except Exception as e:
        log.error(f"Failed to fetch or parse spreadsheet: {e}")
        return

    # Determine output directory
    if output_dir:
        laporan_dir = Path(output_dir)
    else:
        start_str = date_start or "all"
        end_str = date_end or "all"
        laporan_dir = Path("laporan") / f"{start_str}_{end_str}"
    
    # Auto-cleanup old CSV files
    if laporan_dir.exists():
        if outlet_filter or branch_filter:
            for p_info in portals:
                portal_safe_name = str(p_info['user']).replace("/", "_").replace("\\", "_")
                for ext in [".csv", ".xlsx"]:
                    f = laporan_dir / f"{portal_safe_name}{ext}"
                    if f.exists():
                        try: f.unlink()
                        except: pass
            
            outlet_safe = str(outlet_filter or "").strip().replace(" ", "_").replace("/", "_").replace("\\", "_").replace("|", "_")
            branch_safe = str(branch_filter or "").strip().replace(" ", "_").replace("/", "_").replace("\\", "_").replace("|", "_")
            filename_prefix = f"BASELINE_CUSTOM_{outlet_safe}_{branch_safe}"
            if len(filename_prefix) > 50:
                filename_prefix = "BASELINE_CUSTOM_MULTIPLE_OUTLETS"
            for ext in [".csv", ".xlsx"]:
                f = laporan_dir / f"{filename_prefix}{ext}"
                if f.exists():
                    try: f.unlink()
                    except: pass
        else:
            old_files = list(laporan_dir.glob("*.csv")) + list(laporan_dir.glob("*.xlsx"))
            if old_files:
                log.info(f"Cleaning up {len(old_files)} old files in {laporan_dir}...")
                for f in old_files:
                    try: f.unlink()
                    except: pass

    log.info("="*60)
    log.info(f"  GRAB MULTI-PORTAL AUTOMATION ({len(portals)} portals)")
    
    unique_users = {}
    for p_info in portals:
        u = p_info["user"]
        if user_filter and user_filter.lower() not in u.lower():
            continue

        if u not in unique_users:
            unique_users[u] = {"pwd": p_info["pwd"], "portals": []}
        unique_users[u]["portals"].append(p_info)
    
    log.info(f"  Unique Accounts: {len(unique_users)}")
    log.info("="*60)
    
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        # Load headless setting and concurrency from config.json walk-up
        headless_env = True
        concurrency_limit = 1
        try:
            import json
            for parent in Path(__file__).resolve().parents:
                config_file = parent / "config.json"
                if config_file.exists():
                    with open(config_file, "r") as f:
                        config_data = json.load(f)
                        headless_env = config_data.get("headless_grab", True)
                        concurrency_limit = config_data.get("max_concurrency", 1)
                    break
        except Exception:
            pass
        browser = await p.chromium.launch(headless=headless_env)
        semaphore = asyncio.Semaphore(concurrency_limit)
        failures = []

        async def process_user(username, info, is_retry=False):
            password = info["pwd"]
            related_portals = info["portals"]
            first_outlet = related_portals[0]["outlet"]
            
            async with semaphore:
                log.info(f"[ACCOUNT] Starting for: {username} ({first_outlet})")
                try:
                    downloaded_file, err = await run_api_download_for_portal(
                        username, password, 
                        start_date=date_start, 
                        end_date=date_end,
                        browser=browser,
                        is_retry=is_retry
                    )

                    if not downloaded_file:
                        log.error(f"  ✗ [ACCOUNT] {username} Failed: {err}")
                        failures.append({"user": username, "error": err, "outlets": [p["outlet"] for p in related_portals]})
                        return

                    for portal in related_portals:
                        portal_id = portal["id"]
                        outlet_name = f"{portal['outlet']} ({portal['branch']})" if portal['branch'] else portal['outlet']
                        laporan_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Gunakan murni Username Akun sebagai nama file (Merchant label)
                        portal_safe_name = str(portal['user']).replace("/", "_").replace("\\", "_")
                        dest_xlsx = laporan_dir / f"{portal_safe_name}.xlsx"
                        
                        # Convert S3 CSV to Cleaned XLSX per portal
                        tmp_df = pd.read_csv(downloaded_file)
                        
                        # Bersihkan spasi di nama kolom
                        tmp_df.columns = [str(c).strip() for c in tmp_df.columns]
                        
                        # Tambahkan kolom Month
                        if "Date" in tmp_df.columns:
                            parsed_date = pd.to_datetime(tmp_df["Date"], errors="coerce", format="%d/%m/%Y")
                            # Memasukkan kolom Month dengan nama bulan bahasa Inggris (March, April, dst)
                            col_idx = tmp_df.columns.get_loc("Date") + 1
                            tmp_df.insert(col_idx, "Month", parsed_date.dt.strftime('%B'))
                            
                        # Filter hanya untuk GrabFood
                        if "Grab Service" in tmp_df.columns:
                            tmp_df = tmp_df[tmp_df["Grab Service"].astype(str).str.contains("grabfood", case=False, na=False)]
                            
                        tmp_df.to_excel(dest_xlsx, index=False)
                        log.info(f"  ✓ [PORTAL {portal_id}] {outlet_name} — Saved Clean XLSX to: {dest_xlsx.name}")

                except Exception as e:
                    log.error(f"  ✗ [ACCOUNT] {username} CRITICAL ERROR: {str(e)}")

        tasks = [process_user(u, info) for u, info in unique_users.items()]
        await asyncio.gather(*tasks)
        
        # --- Sequential Retry for Failed Accounts ---
        if failures:
            log.info("\n" + "="*60)
            log.info(f"  [RETRY] Attempting to re-run {len(failures)} failed accounts sequentially to resolve network/concurrency issues...")
            log.info("="*60)
            
            retry_failures = list(failures)
            failures.clear() # Clear so it only contains true failures after retry
            
            for f in retry_failures:
                username = f["user"]
                info = unique_users[username]
                log.info(f"\n  [RETRY ACCOUNT] Re-running sequentially for: {username}")
                await process_user(username, info, is_retry=True)
                
        await browser.close()

    log.info("="*60)
    log.info("  ALL PORTALS FINISHED PROCESSING")
    if failures:
        log.info("-" * 60)
        log.info(f"  FAILED ACCOUNTS ({len(failures)}):")
        for f in failures:
            log.info(f"  - {f['user']}: {f['error']}")
    else:
        log.info("  ✓ ALL ACCOUNTS PROCESSED SUCCESSFULLY")
    log.info("="*60)

    # --- Gabungkan semua CSV menjadi file master ---
    if output_dir:
        laporan_dir = Path(output_dir)
    else:
        start_str = date_start or "all"
        end_str = date_end or "all"
        laporan_dir = Path("laporan") / f"{start_str}_{end_str}"

    xlsx_files = sorted(laporan_dir.glob("*.xlsx")) if laporan_dir.exists() else []
    # Exclude master file jika sudah ada dari run sebelumnya
    xlsx_files = [f for f in xlsx_files if f.stem != "MASTER" and not f.stem.startswith("BASELINE_CUSTOM_") and not f.stem.startswith("CUSTOM_")]
    if outlet_filter or branch_filter:
        valid_stems = []
        for p_info in portals:
            # Gunakan murni Username Akun sebagai nama file (Merchant label)
            portal_safe_name = str(p_info['user']).replace("/", "_").replace("\\", "_")
            valid_stems.append(portal_safe_name)
        xlsx_files = [f for f in xlsx_files if f.stem in valid_stems]

    if not xlsx_files:
        print("\n[SKIP] Tidak ada file XLSX untuk digabung.")
        return

    print(f"\nScanning and validating {len(xlsx_files)} raw XLSX files for master merging...")
    frames = []
    for xlsx_path in xlsx_files:
        try:
            df = pd.read_excel(xlsx_path)
            if df.empty or len(df) == 0:
                print(f"  ⚠️ [CHECK] Raw file '{xlsx_path.name}' is EMPTY (no transaction rows). Skipping merger.")
                continue
                
            print(f"  🔍 [CHECK] Raw file '{xlsx_path.name}' has {len(df)} rows. Including in MASTER...")
            # Selalu timpa kolom Merchant bawaan S3 dengan nama file (Akun) agar tergabung per akun
            if "Merchant" in df.columns:
                df["Merchant"] = xlsx_path.stem
            else:
                df.insert(0, "Merchant", xlsx_path.stem)
            frames.append(df)
        except Exception as e:
            print(f"  ❌ [CHECK] Gagal membaca atau memproses '{xlsx_path.name}': {e}")

    if not frames:
        log.info("⏭️ [SKIP] Tidak ada file CSV yang memiliki data untuk digabung.")
        return

    master_df = pd.concat(frames, ignore_index=True)

    # --- APPLY BASELINE LOGIC (From result.py) ---
    working = master_df.copy()
    
    # Preprocess columns for both Old format and New S3 Insights format
    if "Date" in working.columns and "Updated On" not in working.columns:
        working["Updated On"] = pd.to_datetime(working["Date"], errors="coerce", format="%d/%m/%Y")
    elif "Created On" in working.columns and "Updated On" not in working.columns:
        working["Updated On"] = pd.to_datetime(working["Created On"], errors="coerce", format="%d %b %Y %I:%M %p")
    elif "Update Time" in working.columns and "Updated On" not in working.columns:
        working["Updated On"] = pd.to_datetime(working["Update Time"], errors="coerce", format="%d %b %Y %I:%M %p")
    elif "Updated On" in working.columns:
        # Menghilangkan format agar bisa robust untuk berbagai variasi data (misal: "1 Mar 2026")
        working["Updated On"] = pd.to_datetime(working["Updated On"], errors="coerce")
        
    if "Long Order ID" in working.columns:
        working["Long Order ID"] = working["Long Order ID"].fillna("").astype(str).str.strip()
        
    if "Grab Service" in working.columns and "Category" not in working.columns:
        working["Category"] = working["Grab Service"].fillna("").astype(str).str.strip().str.casefold()
    elif "Main Category" in working.columns and "Category" not in working.columns:
        working["Category"] = working["Main Category"].fillna("").astype(str).str.strip().str.casefold()
    elif "Category" in working.columns:
        working["Category"] = working["Category"].fillna("").astype(str).str.strip().str.casefold()
        
    if "Net Sales (Rp)" in working.columns and "Net Sales" not in working.columns:
        # Hapus koma/titik ribuan jika ada
        working["Net Sales (Rp)"] = working["Net Sales (Rp)"].astype(str).str.replace(',', '').str.replace('.', '')
        working["Net Sales"] = pd.to_numeric(working["Net Sales (Rp)"], errors="coerce").fillna(0)
    elif "Net Sales" in working.columns:
        working["Net Sales"] = pd.to_numeric(working["Net Sales"], errors="coerce").fillna(0)
        
    if "Status" in working.columns:
        working["Status"] = working["Status"].fillna("").astype(str).str.strip().str.casefold()

    # Mengikuti rumus sheet User: (O7:O <> "") * REGEXMATCH(O7:O,"[^A-Za-z0-9]")
    # Yaitu tidak kosong dan mengandung karakter non-alphanumeric (seperti tanda strip)
    if "Long Order ID" in working.columns:
        # Menghapus spasi awal/akhir dulu untuk memastikan, lalu cek regex
        valid_long_id = working["Long Order ID"].astype(str).str.strip()
        is_valid_order_id = (valid_long_id != "") & valid_long_id.str.contains(r'[^A-Za-z0-9]', regex=True, na=False)
    else:
        is_valid_order_id = pd.Series(True, index=working.index)
        
    # Rule 3: Tanpa filter category (Semua category diikutkan)
    is_order_category = pd.Series(True, index=working.index)
    
    # Rule 4: Filter status cancelled
    is_not_cancelled = working["Status"].ne("cancelled") if "Status" in working.columns else pd.Series(True, index=working.index)
    
    # Apply filters
    valid_orders = working.loc[is_valid_order_id & is_order_category & is_not_cancelled].copy()
    
    # Parse Number of Transactions if S3 format
    if "Number of Transactions" in valid_orders.columns:
        # S3 format has aggregated order counts
        valid_orders["Number of Transactions"] = valid_orders["Number of Transactions"].astype(str).str.replace(',', '').str.replace('.', '')
        valid_orders["Order_Counter"] = pd.to_numeric(valid_orders["Number of Transactions"], errors="coerce").fillna(0)
    else:
        # Karena filter valid_orders di atas sudah membuang baris yang tidak memiliki tanda strip,
        # maka semua baris di sini dipastikan adalah pesanan asli (bukan iklan/adjustment)
        valid_orders["Order_Counter"] = 1
    
    if "Updated On" in valid_orders.columns:
        valid_orders = valid_orders.loc[valid_orders["Updated On"].notna()].copy()
    
    # Filter Custom Date Range (No Hardcoding)
    if date_start and "Updated On" in valid_orders.columns:
        valid_orders = valid_orders.loc[valid_orders["Updated On"] >= pd.Timestamp(date_start)].copy()
    if date_end and "Updated On" in valid_orders.columns:
        end_ts = pd.Timestamp(date_end).replace(hour=23, minute=59, second=59)
        valid_orders = valid_orders.loc[valid_orders["Updated On"] <= end_ts].copy()

    if valid_orders.empty:
        log.warning("⚠️ Tidak ada transaksi valid yang masuk dalam range tanggal dan filter ini untuk dihitung baseline-nya.")
        return

    valid_orders["Month"] = valid_orders["Updated On"].dt.to_period("M").dt.to_timestamp()

    # Aggregate by Merchant and Month
    summary = (
        valid_orders.groupby(["Merchant", "Month"], as_index=False)
        .agg(
            Order_Count=("Order_Counter", "sum"),
            Omzet_Net_Sales=("Net Sales", "sum"),
        )
        .sort_values(["Merchant", "Month"])
        .reset_index(drop=True)
    )

    # Convert to Wide Format
    months = sorted(summary["Month"].unique())
    wide_rows = []
    
    for merchant, group in summary.groupby("Merchant"):
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
    wide_summary.insert(1, "Aplikasi", "Grab")

    # Simpan sebagai Excel Lokal
    if outlet_filter or branch_filter:
        outlet_safe = str(outlet_filter or "").strip().replace(" ", "_").replace("/", "_").replace("\\", "_").replace("|", "_")
        branch_safe = str(branch_filter or "").strip().replace(" ", "_").replace("/", "_").replace("\\", "_").replace("|", "_")
        filename_prefix = f"BASELINE_CUSTOM_{outlet_safe}_{branch_safe}"
        if len(filename_prefix) > 50:
            filename_prefix = "BASELINE_CUSTOM_MULTIPLE_OUTLETS"
    else:
        filename_prefix = "BASELINE_MASTER"

    master_xlsx = laporan_dir / f"{filename_prefix}.xlsx"
    
    # Save with formatting
    with pd.ExcelWriter(master_xlsx, engine="openpyxl") as writer:
        wide_summary.to_excel(writer, index=False, sheet_name="Baseline Summary")

    log.info(f"✓ Laporan Baseline Excel: {master_xlsx}")
    log.info(f"  Total merchant diproses: {len(wide_summary)}")

    # Matikan push ke GSheets dan PostgreSQL
    log.info("⏭️ [SKIP] Push ke Google Sheets dan database dimatikan secara global untuk mode Baseline.")

    # === UNGGAH KE GOOGLE DRIVE ===
    DRIVE_PARENT_FOLDER_ID = "13Fg6prqaP2Xzfxsd_Qut-4cjrtxm9FMS"
    # Nama subfolder diambil dari nama laporan_dir (misal: "2026-03-01_to_2026-05-31")
    subfolder_name = laporan_dir.name 
    
    webhook_url = os.getenv("GRAB_DRIVE_UPLOAD_WEBHOOK_URL")
    if webhook_url:
        log.info("\n" + "="*60)
        log.info("  MENGUNGGAH HASIL KE GOOGLE DRIVE")
        log.info("="*60)
        
        import base64
        import requests
        
        def _upload_file(filepath):
            try:
                with open(filepath, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                payload = {
                    "parentFolderId": DRIVE_PARENT_FOLDER_ID,
                    "subFolderName": subfolder_name,
                    "fileName": filepath.name,
                    "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "fileData": encoded
                }
                log.info(f"  Mengunggah: {filepath.name} ...")
                res = requests.post(webhook_url, json=payload, timeout=60)
                if res.status_code == 200 and res.json().get("status") == "success":
                    log.info(f"  ✓ Berhasil: {res.json().get('url')}")
                else:
                    log.error(f"  ✗ Gagal: {res.text}")
            except Exception as e:
                log.error(f"  ✗ Error mengunggah {filepath.name}: {e}")

        # Unggah master baseline
        if master_xlsx.exists():
            _upload_file(master_xlsx)
        
        # Unggah file raw per-portal
        for xlsx_path in xlsx_files:
            if xlsx_path.exists():
                _upload_file(xlsx_path)
                
        log.info("="*60)
    else:
        log.info("\n⏭️ [SKIP] GRAB_DRIVE_UPLOAD_WEBHOOK_URL tidak ditemukan di .env. Lewati proses unggah otomatis ke Google Drive.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Jalankan scraper Grab multi-portal dan hitung omzet."
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Filter awal (inklusif), format YYYY-MM-DD. Contoh: 2026-02-01",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="Filter akhir (inklusif), format YYYY-MM-DD. Contoh: 2026-04-30",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override output directory for reports.",
    )
    parser.add_argument(
        "--user",
        default=None,
        help="Filter specific username to run.",
    )
    parser.add_argument(
        "--outlet",
        default=None,
        help="Filter specific outlet name to run.",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Filter specific branch name to run.",
    )
    args = parser.parse_args()
    asyncio.run(run_all(
        date_start=args.start_date, 
        date_end=args.end_date, 
        output_dir=args.output_dir, 
        user_filter=args.user,
        outlet_filter=args.outlet,
        branch_filter=args.branch
    ))
