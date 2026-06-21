import asyncio
import sys
import os
import pandas as pd
import requests
import io
from dotenv import load_dotenv
from grab_api_scraper import run_api_download_for_portal
from result import main as run_result

CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRUOPDeyWtcCQT2OaNTmplVoIs0FxGFT-6UA3W-AJ_-RAG3H57UTADOyK2O1YnwMhphQPL2Nj86s7N6/pub?gid=0&single=true&output=csv"

async def run_all():
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
            # Step 1: Download data via API
            print(f"Step 1: Downloading data via API...")
            downloaded_file = await run_api_download_for_portal(user, pwd)
            
            if not downloaded_file:
                print(f"✗ [PORTAL {portal['id']}] Gagal mengunduh data.")
                continue

            # Step 2: Process and Push
            print(f"\nStep 2: Processing and pushing to Google Sheets...")
            # run_result will automatically pick the latest file in downloads/
            run_result(username=user, outlet=portal['outlet'], branch=portal['branch'])
            
            print(f"\n✓ [PORTAL {portal['id']}] {outlet_name} COMPLETED SUCCESSFULLY")
            
        except Exception as e:
            print(f"\n✗ [PORTAL {portal['id']}] FAILED: {str(e)}")
            continue

    print("\n" + "="*60)
    print("  ALL PORTALS FINISHED PROCESSING")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_all())
