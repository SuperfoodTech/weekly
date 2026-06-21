import pandas as pd
import requests
import io
from sqlalchemy import create_engine, text
import os

# Configuration
GSHEET_MASTER_URL = "https://docs.google.com/spreadsheets/d/14eCb8DAEXhmbYj9MFj2KzC7AhkulbCbSNPltN2m-go0/export?format=csv&gid=0"
DB_URL = "postgresql://superfood_admin:superfood_password@localhost:5433/srs_db"

def sync_merchants():
    import time
    print("📥 Fetching Merchant Master from Google Sheets...")
    response = requests.get(GSHEET_MASTER_URL + f"&t={int(time.time())}")
    if response.status_code != 200:
        print(f"❌ Failed to fetch data: {response.status_code}")
        return

    # Load into DataFrame
    df = pd.read_csv(io.StringIO(response.text))
    
    # 1. Clean Column Names (Handle potential duplicates/spaces)
    df.columns = [c.strip() for c in df.columns]
    
    # 2. Logic: is_active
    # If Status is 'Live' then is_active = True
    df['is_active'] = df['Status'].str.strip().str.lower() == 'live'
    
    # 3. Filter: Hanya ambil yang ada Store ID
    df = df.dropna(subset=['Store ID'])
    df = df[df['Store ID'].astype(str).str.strip() != '-']
    
    # 4. Username Logic (Priority SuperFood)
    def get_active_user(row):
        # The CSV might have duplicate column names which pandas suffix as .1
        u1 = row.get('Nama Pengguna.1') # SuperFood login
        u2 = row.get('Nama Pengguna')   # Original login
        user = u1 if pd.notna(u1) and str(u1).strip() != "-" else u2
        return str(user).strip() if pd.notna(user) else None

    df['active_user'] = df.apply(get_active_user, axis=1)
    
    # 5. Mapping
    mapping = {
        'Store ID': 'store_id',
        'Aplikasi': 'platform',
        'Nama Outlet': 'outlet_name',
        'Cabang': 'branch_name',
        'Group Code': 'group_code',
        'Owner': 'owner_name',
        'Merchant ID': 'merchant_id',
        'Merchant Name': 'merchant_name',
        'active_user': 'username',
        'Status': 'status',
        'is_active': 'is_active'
    }
    
    df_final = df.rename(columns=mapping)[list(mapping.values())]
    
    # Deduplicate based on Store ID
    df_final = df_final.drop_duplicates(subset=['store_id'], keep='first')
    
    print(f"🔄 Syncing {len(df_final)} total records (Filtering for Live in process)...")
    
    engine = create_engine(DB_URL)
    
    with engine.begin() as conn:
        conn.execute(text("CREATE TEMP TABLE tmp_merchants (LIKE dim_merchants INCLUDING ALL) ON COMMIT DROP"))
        df_final.to_sql('tmp_merchants', conn, if_exists='append', index=False)
        
        upsert_query = """
            INSERT INTO dim_merchants (store_id, platform, outlet_name, branch_name, group_code, owner_name, 
                                     merchant_id, merchant_name, username, status, is_active)
            SELECT store_id, platform, outlet_name, branch_name, group_code, owner_name, 
                   merchant_id, merchant_name, username, status, is_active FROM tmp_merchants
            ON CONFLICT (store_id) DO UPDATE SET
                platform = EXCLUDED.platform,
                outlet_name = EXCLUDED.outlet_name,
                branch_name = EXCLUDED.branch_name,
                group_code = EXCLUDED.group_code,
                owner_name = EXCLUDED.owner_name,
                merchant_id = EXCLUDED.merchant_id,
                merchant_name = EXCLUDED.merchant_name,
                username = EXCLUDED.username,
                status = EXCLUDED.status,
                is_active = EXCLUDED.is_active,
                updated_at = CURRENT_TIMESTAMP;
        """
        conn.execute(text(upsert_query))
        
        # FINAL STEP: Hapus atau sembunyikan yang tidak LIVE jika diminta
        # Sesuai permintaan Anda: "pastikan juga untuk yang kita ambil hanya status live"
        # Kita hapus yang is_active = False agar database benar-benar bersih
        conn.execute(text("DELETE FROM dim_merchants WHERE is_active = FALSE"))
        
    print("✅ Merchant sync with is_active logic completed!")

if __name__ == "__main__":
    try:
        sync_merchants()
    except Exception as e:
        print(f"❌ Error: {e}")
