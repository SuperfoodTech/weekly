import argparse
import asyncio
import io
import os
import shutil
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from grab_api_scraper import run_api_download_for_portal

CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRUOPDeyWtcCQT2OaNTmplVoIs0FxGFT-6UA3W-AJ_-RAG3H57UTADOyK2O1YnwMhphQPL2Nj86s7N6/pub?gid=0&single=true&output=csv"

async def run_all(date_start: str = None, date_end: str = None, output_dir: str = None):
    # Reload env just in case
    load_dotenv(override=True)
    
    print(f"Fetching merchant list from spreadsheet...")
    try:
        resp = requests.get(CSV_URL, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        
        # Filter for GrabFood and Status Live
        # Note: pandas appends .1 to duplicate column names
        grab_df = df[df["Aplikasi"].str.contains("Grab", na=False, case=False)]
        grab_df = grab_df[grab_df["Status"].str.contains("Live", na=False, case=False)]
        
        portals = []
        for idx, row in grab_df.iterrows():
            # Columns logic: 
            # 1st Nama Pengguna (index 16), 2nd Nama Pengguna (index 25, usually SuperFood)
            # We take the 2nd one if available, fallback to 1st
            user_sf = row.get("Nama Pengguna.1")
            user_mt = row.get("Nama Pengguna")
            pwd_sf = row.get("Kata Sandi.1")
            pwd_mt = row.get("Kata Sandi")
            
            user = user_sf if pd.notna(user_sf) and str(user_sf).strip() != "-" else user_mt
            pwd = pwd_sf if pd.notna(pwd_sf) and str(pwd_sf).strip() != "-" else pwd_mt
            
            if pd.notna(user) and pd.notna(pwd) and str(user).strip() != "-" and str(pwd).strip() != "-":
                portals.append({
                    "id": len(portals) + 1,
                    "outlet": row.get("Nama Outlet", "Unknown"),
                    "branch": row.get("Cabang", "Unknown"),
                    "user": str(user).strip(),
                    "pwd": str(pwd).strip()
                })
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch or parse spreadsheet: {e}")
        return

    if not portals:
        print("[ERROR] No active Grab portals found in the spreadsheet.")
        return

    print("="*60)
    print(f"  GRAB MULTI-PORTAL AUTOMATION ({len(portals)} accounts from Spreadsheet)")
    print("="*60)
    
    for portal in portals:
        user = portal["user"]
        pwd = portal["pwd"]
        outlet_name = f"{portal['outlet']} ({portal['branch']})"
        
        print(f"\n\n[PORTAL {portal['id']}] Starting process for: {outlet_name}")
        print(f"User: {user}")
        print("-" * 50)
        
        try:
            # Download raw CSV via API
            print(f"Downloading data via API...")
            downloaded_file = await run_api_download_for_portal(user, pwd, start_date=date_start, end_date=date_end)

            if not downloaded_file:
                print(f"✗ [PORTAL {portal['id']}] Gagal mengunduh data.")
                continue

            # Salin file raw CSV ke folder laporan
            if output_dir:
                laporan_dir = Path(output_dir)
            else:
                start_str = date_start or "all"
                end_str = date_end or "all"
                laporan_dir = Path("laporan") / f"{start_str}_{end_str}"
            laporan_dir.mkdir(parents=True, exist_ok=True)

            safe_user = user.replace("/", "_").replace("\\", "_")
            dest = laporan_dir / f"{safe_user}.csv"
            shutil.copy2(downloaded_file, dest)

            print(f"✓ [PORTAL {portal['id']}] {outlet_name} — raw CSV disimpan ke: {dest}")

        except Exception as e:
            print(f"\n✗ [PORTAL {portal['id']}] FAILED: {str(e)}")
            continue

    print("\n" + "="*60)
    print("  ALL PORTALS FINISHED PROCESSING")
    print("="*60)

    # --- Gabungkan semua CSV menjadi file master ---
    if output_dir:
        laporan_dir = Path(output_dir)
    else:
        start_str = date_start or "all"
        end_str = date_end or "all"
        laporan_dir = Path("laporan") / f"{start_str}_{end_str}"

    csv_files = sorted(laporan_dir.glob("*.csv")) if laporan_dir.exists() else []
    # Exclude master file jika sudah ada dari run sebelumnya
    csv_files = [f for f in csv_files if f.stem != "MASTER"]

    if not csv_files:
        print("\n[SKIP] Tidak ada file CSV untuk digabung.")
        return

    print(f"\nMenggabungkan {len(csv_files)} file CSV menjadi master...")
    frames = []
    for csv_path in csv_files:
        try:
            df = pd.read_csv(csv_path)
            df.insert(0, "Merchant", csv_path.stem)
            frames.append(df)
        except Exception as e:
            print(f"  [WARN] Gagal baca {csv_path.name}: {e}")

    if not frames:
        print("[SKIP] Semua file gagal dibaca.")
        return

    master_df = pd.concat(frames, ignore_index=True)

    # Normalisasi kolom tanggal → "YYYY-MM-DD at HH:MM"
    date_cols = ["Updated On", "Created On", "Transfer Date"]
    for col in date_cols:
        if col in master_df.columns:
            parsed = pd.to_datetime(master_df[col], format="%d %b %Y %I:%M %p", errors="coerce")
            # Fallback: coba parse tanpa format eksplisit untuk varian lain
            mask_failed = parsed.isna() & master_df[col].notna()
            if mask_failed.any():
                parsed[mask_failed] = pd.to_datetime(master_df.loc[mask_failed, col], errors="coerce")
            master_df[col] = parsed.dt.strftime("%Y-%m-%d at %H:%M").where(parsed.notna(), other=master_df[col])

    # Tambah kolom OFD Fees = Net Sales - Total, disisipkan sebelum kolom Total
    if "Net Sales" in master_df.columns and "Total" in master_df.columns:
        master_df["Net Sales"] = pd.to_numeric(master_df["Net Sales"], errors="coerce")
        master_df["Total"] = pd.to_numeric(master_df["Total"], errors="coerce")
        ofd_fees = master_df["Net Sales"] - master_df["Total"]
        total_idx = master_df.columns.get_loc("Total")
        master_df.insert(total_idx, "OFD Fees", ofd_fees)
    else:
        print("  [WARN] Kolom 'Net Sales' atau 'Total' tidak ditemukan, OFD Fees dilewati.")

    # Simpan sebagai CSV
    master_csv = laporan_dir / "MASTER.csv"
    master_df.to_csv(master_csv, index=False)

    # Simpan sebagai Excel
    master_xlsx = laporan_dir / "MASTER.xlsx"
    master_df.to_excel(master_xlsx, index=False, sheet_name="All Merchants")

    print(f"✓ Master CSV  : {master_csv}")
    print(f"✓ Master Excel: {master_xlsx}")
    print(f"  Total baris : {len(master_df):,} | Merchant: {master_df['Merchant'].nunique()}")

    # --- Distribusi ke Google Sheets via Apps Script ---
    apps_script_url = os.getenv("APPS_SCRIPT_URL")
    if apps_script_url:
        print("\n📤 [PROGRESS] Mengirim data ke Google Sheets...")
        
        dist_df = master_df.copy()
        
        # Tambah Flag dan Month
        dist_df["Flag"] = "Final OP"
        
        def get_month_from_grab(date_str):
            try:
                # Format: "YYYY-MM-DD at HH:MM"
                return date_str.split(" ")[0][:7]
            except:
                return ""
        
        if "Created On" in dist_df.columns:
            dist_df["Month"] = dist_df["Created On"].apply(get_month_from_grab)
        else:
            dist_df["Month"] = ""
            
        dist_df["Move to OE/OP"] = ""
        
        # Headers target Grab (sesuai urutan di sheet)
        target_headers = [
            "Flag", "Month", "Merchant Name", "Merchant ID", "Store Name", "Store ID", 
            "Updated On", "Created On", "Type", "Category", "Subcategory", "Status", 
            "Transaction ID", "Linked Transaction ID", "Partner transaction ID 1", 
            "Partner transaction ID 2", "Long Order ID", "Short Order ID", "Booking ID", 
            "Order Channel", "Order Type", "Payment Method", "Receiving account / Source of fund", 
            "Terminal ID", "Channel", "Offer Type", "Grab Fee (%)", "Points Multiplier", 
            "Points Issued", "Settlement ID", "Transfer Date", "Amount", "Tax on Order Value", 
            "Restaurant Packaging Charge", "Non-Member Fee", "Restaurant Service Charge", 
            "Offer", "Discount (Merchant-Funded)", "Delivery Fee Discount (Merchant-Funded)", 
            "Delivery Charge (Grab Online Store)", "Delivery Charge (Merchant Delivery)", 
            "GrabExpress Delivery Service Fee", "Net Sales", "Net MDR", "Tax on MDR", 
            "Grab Fee", "Marketing success fee", "Delivery Commission", "Channel Commission", 
            "Order commission", "GrabFood / GrabMart Other Commission", "GrabKitchen Commission", 
            "GrabKitchen Other Commission", "Withholding Tax", "Total", "Tax on MDR (%)", 
            "Delivery Commission (%)", "Channel Commission (%)", "Order Commission (%)",
            "Tax on GrabFood / GrabMart Commission, Adjustments, Ads",
            "Tax on Total GrabKitchen Commission", "Cancellation Reason", "Cancelled by", 
            "Reason for Refund", "Description", "Incident group", "Incident alias", 
            "Customer refund Item", "Appeal link", "Appeal status", "Package/Voucher Used", 
            "Attributed Service Fee", "Attributed Promo", "Move to OE/OP"
        ]
        
        # Pastikan semua kolom ada (isi kosong jika tidak ada)
        for col in target_headers:
            if col not in dist_df.columns:
                dist_df[col] = ""
        
        # Pilih kolom sesuai urutan target
        final_df = dist_df[target_headers]
        
        # Payload JSON (Handle NaN values which are not JSON compliant)
        payload = final_df.fillna("").to_dict(orient="records")
        
        try:
            response = requests.post(
                f"{apps_script_url}?sheet=Grab",
                json=payload,
                timeout=60
            )
            if response.status_code == 200:
                res_json = response.json()
                if res_json.get("status") == "success":
                    print(f"✅ [SUCCESS] Berhasil mengirim {res_json.get('rows_added')} baris ke sheet Grab.")
                else:
                    print(f"❌ [ERROR] Apps Script error: {res_json.get('message')}")
            else:
                print(f"❌ [ERROR] Gagal mengirim data: HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ [ERROR] Gagal terhubung ke Apps Script: {e}")
    else:
        print("\n⚠️ [SKIP] APPS_SCRIPT_URL tidak ditemukan di .env. Melewati distribusi ke G-Sheets.")


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
    args = parser.parse_args()
    asyncio.run(run_all(date_start=args.start_date, date_end=args.end_date, output_dir=args.output_dir))
