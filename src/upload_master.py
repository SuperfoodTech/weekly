import pandas as pd
import requests
import os
from dotenv import load_dotenv
import argparse
from pathlib import Path
import io

# =================================================================
# DICTIONARY MAPPING: "Nama di GSheet": "Nama di MASTER.xlsx"
# =================================================================
GRAB_COLUMN_MAP = {
    "Flag": "Flag",
    "Month": "Month",
    "Merchant Name": "Merchant Name",
    "Merchant ID": "Merchant ID",
    "Store Name": "Store Name",
    "Store ID": "Store ID",
    "Updated On": "Updated On",
    "Created On": "Created On",
    "Type": "Type",
    "Category": "Category",
    "Subcategory": "Subcategory",
    "Status": "Status",
    "Transaction ID": "Transaction ID",
    "Linked Transaction ID": "Linked Transaction ID",
    "Partner transaction ID 1": "Partner transaction ID 1",
    "Partner transaction ID 2": "Partner transaction ID 2",
    "Long Order ID": "Long Order ID",
    "Short Order ID": "Short Order ID",
    "Booking ID": "Booking ID",
    "Order Channel": "Order Channel",
    "Order Type": "Order Type",
    "Payment Method": "Payment Method",
    "Receiving account / Source of fund": "Receiving account / Source of fund",
    "Terminal ID": "Terminal ID",
    "Channel": "Channel",
    "Offer Type": "Offer Type",
    "Grab Fee (%)": "Grab Fee (%)",
    "Points Multiplier": "Points Multiplier",
    "Points Issued": "Points Issued",
    "Settlement ID": "Settlement ID",
    "Transfer Date": "Transfer Date",
    "Amount": "Amount",
    "Tax on Order Value": "Tax on Order Value",
    "Restaurant Packaging Charge": "Restaurant Packaging Charge",
    "Non-Member Fee": "Non-Member Fee",
    "Restaurant Service Charge": "Restaurant Service Charge",
    "Offer": "Offer",
    "Discount (Merchant-Funded)": "Discount (Merchant-Funded)",
    "Delivery Fee Discount (Merchant-Funded)": "Delivery Fee Discount (Merchant-Funded)",
    "Delivery Charge (Grab Online Store)": "Delivery Charge (Grab Online Store)",
    "Delivery Charge (Merchant Delivery)": "Delivery Charge (Merchant Delivery)",
    "GrabExpress Delivery Service Fee": "GrabExpress Delivery Service Fee",
    "Net Sales": "Net Sales",
    "Net MDR": "Net MDR",
    "Tax on MDR": "Tax on MDR",
    "Grab Fee": "Grab Fee",
    "Marketing success fee": "Marketing success fee",
    "Delivery Commission": "Delivery Commission",
    "Channel Commission": "Channel Commission",
    "Order commission": "Order commission",
    "GrabFood / GrabMart Other Commission": "Step-up commission",
    "GrabKitchen Commission": "GrabKitchen Commission",
    "GrabKitchen Other Commission": "GrabKitchen Other Commission",
    "Withholding Tax": "Withholding Tax",
    "Total": "Total",
    "Tax on MDR (%)": "Tax on MDR (%)",
    "Delivery Commission (%)": "Delivery Commission (%)",
    "Channel Commission (%)": "Channel Commission (%)",
    "Order Commission (%)": "Order Commission (%)",
    "Tax on GrabFood / GrabMart Commission, Adjustments, Ads": "Tax on GrabFood/GrabMart commission, adjustments, ads",
    "Tax on Total GrabKitchen Commission": "Tax on Total GrabKitchen Commission",
    "Cancellation Reason": "Cancellation Reason",
    "Cancelled by": "Cancelled by",
    "Reason for Refund": "Reason for Refund",
    "Description": "Description",
    "Incident group": "Incident group",
    "Incident alias": "Incident alias",
    "Customer refund Item": "Customer refund Item",
    "Appeal link": "Appeal link",
    "Appeal status": "Appeal status",
    "Package/Voucher Used": "Package/Voucher Used",
    "Attributed Service Fee": "Attributed Service Fee",
    "Attributed Promo": "Attributed Promo",
    "Move to OE/OP": "Move to OE/OP"
}

def upload_to_gsheets(file_path, sheet_name="Grab", clear=True):
    load_dotenv()
    apps_script_url = "https://script.google.com/macros/s/AKfycbxuqQ72VfP-5f-h-ud1XZDgG47KDwyP8gDg2AFzIjq6JrnZnWGenRs50G06RxsPiSxj/exec"
    
    if not apps_script_url:
        print("Error: APPS_SCRIPT_URL not found in .env")
        return

    print(f"Reading {file_path}...")
    df_master = pd.read_excel(file_path, dtype=str)

    # Tambah Flag dan Month jika belum ada di Master
    if "Flag" not in df_master.columns:
        df_master["Flag"] = "Final OP"
    
    if "Month" not in df_master.columns:
        def get_month(date_str):
            try: return str(date_str).split(" ")[0][:7]
            except: return ""
        col_date = "Created On" if "Created On" in df_master.columns else df_master.columns[0]
        df_master["Month"] = df_master[col_date].apply(get_month)
    
    if "Move to OE/OP" not in df_master.columns:
        df_master["Move to OE/OP"] = ""

    # Gunakan mapping dictionary untuk membuat payload JSON yang bersih
    # Kita kirim SEMUA kolom yang kita punya di dictionary
    rows_to_send = []
    for _, master_row in df_master.iterrows():
        json_row = {}
        for gsheet_col, master_col in GRAB_COLUMN_MAP.items():
            if master_col in df_master.columns:
                val = master_row[master_col]
                json_row[gsheet_col] = val if pd.notna(val) else ""
            else:
                json_row[gsheet_col] = ""
        rows_to_send.append(json_row)

    print(f"Sending {len(rows_to_send)} rows to sheet '{sheet_name}' (clear={clear})...")
    try:
        # Kirim ke Apps Script. Apps Script akan mengurus urutan kolom di GSheet.
        response = requests.post(
            f"{apps_script_url}?sheet={sheet_name}&clear={str(clear).lower()}",
            json=rows_to_send,
            timeout=120
        )
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("status") == "success":
                print(f"✅ Success: {res_json.get('rows_added')} rows added.")
            else:
                print(f"❌ Error: {res_json.get('message')}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload MASTER.xlsx to Google Sheets")
    parser.add_argument("file", help="Path to MASTER.xlsx file")
    parser.add_argument("--sheet", default="Grab", help="Target sheet name")
    parser.add_argument("--no-clear", action="store_false", dest="clear")
    
    args = parser.parse_args()
    
    if Path(args.file).exists():
        upload_to_gsheets(args.file, args.sheet, args.clear)
    else:
        print(f"Error: File {args.file} not found.")
