import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
DB_URL = os.getenv("DATABASE_URL", "postgresql://superfood_admin:superfood_password@localhost:5433/srs_db")

class DatabaseManager:
    def __init__(self):
        self.engine = create_engine(DB_URL)

    def ingest_shopee(self, df: pd.DataFrame):
        """Ingests Shopee analyzed data into stg_shopee_orders."""
        print("📥 [DB] Ingesting Shopee data to Staging...")
        
        # Clean column names to match schema
        mapping = {
            "Month": "month",
            "Store ID": "store_id",
            "Store name": "store_name",
            "Transaction type": "transaction_type",
            "Transaction ID (Order ID)": "transaction_id",
            "Complete Time": "complete_time",
            "Status": "status",
            "Food original price": "food_original_price",
            "Item discounts": "item_discounts",
            "Flash sale discount": "flash_sale_discount",
            "Surcharge fee": "surcharge_fee",
            "Merchant Voucher Deals Subsidy": "merchant_voucher_subsidy",
            "Platform Flash Sale Subsidy": "platform_flash_sale_subsidy",
            "Food Voucher Subsidy": "food_voucher_subsidy",
            "Food Direct Discount": "food_direct_discount",
            "Transaction amount": "transaction_amount",
            "Checkout Murah Price": "checkout_murah_price",
            "Notes": "notes",
            "Net Sales": "net_sales",
            "Commission": "commission",
            "Revenue": "revenue",
            "Move to OE/OP": "move_to_oe_op"
        }
        
        # Ensure all mapping columns exist in DF
        for col in mapping.keys():
            if col not in df.columns:
                df[col] = 0 if "price" in col.lower() or "amount" in col.lower() or "sales" in col.lower() or "revenue" in col.lower() or "discount" in col.lower() or "subsidy" in col.lower() or "fee" in col.lower() or "commission" in col.lower() else ""

        # Select and rename
        df_stg = df[list(mapping.keys())].rename(columns=mapping)
        
        # Convert complete_time to datetime with safety
        df_stg['complete_time'] = pd.to_datetime(df_stg['complete_time'].astype(str).str.replace(' at ', ' '), errors='coerce')
        
        # Populate raw_metadata with the entire row as JSON
        df_stg['raw_metadata'] = df.apply(lambda x: x.to_json(), axis=1)
        
        with self.engine.begin() as conn:
            # Upsert logic to prevent duplicates in staging
            conn.execute(text("CREATE TEMP TABLE tmp_shopee (LIKE stg_shopee_orders INCLUDING ALL) ON COMMIT DROP"))
            df_stg.to_sql('tmp_shopee', conn, if_exists='append', index=False)
            
            cols = ", ".join(mapping.values()) + ", raw_metadata"
            select_cols = ", ".join(mapping.values()) + ", raw_metadata"
            
            upsert_query = f"""
                INSERT INTO stg_shopee_orders ({cols})
                SELECT {select_cols} FROM tmp_shopee
                ON CONFLICT (transaction_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    revenue = EXCLUDED.revenue,
                    raw_metadata = EXCLUDED.raw_metadata,
                    ingested_at = CURRENT_TIMESTAMP;
            """
            conn.execute(text(upsert_query))
        
        print("✅ [DB] Shopee staging ingestion completed.")

    def ingest_grab(self, df: pd.DataFrame):
        """Ingests Grab merged data into stg_grab_orders."""
        print("📥 [DB] Ingesting Grab data to Staging...")
        
        mapping = {
            "Month": "month",
            "Merchant Name": "merchant_name",
            "Merchant ID": "merchant_id",
            "Store Name": "store_name",
            "Store ID": "store_id",
            "Updated On": "updated_on",
            "Created On": "created_on",
            "Status": "status",
            "Transaction ID": "transaction_id",
            "Long Order ID": "long_order_id",
            "Amount": "amount",
            "Discount (Merchant-Funded)": "discount_merchant_funded",
            "Delivery Fee Discount (Merchant-Funded)": "delivery_fee_discount_merchant_funded",
            "Net Sales": "net_sales",
            "Marketing Success Fee": "marketing_success_fee",
            "Order Commission": "order_commission",
            "Total": "total"
        }
        
        # Ensure all mapping columns exist in DF, if not, add as empty
        for col in mapping.keys():
            if col not in df.columns:
                df[col] = ""
        
        # Select and rename
        df_stg = df[list(mapping.keys())].rename(columns=mapping)
        
        # Convert created_on to datetime with safety
        df_stg['created_on'] = pd.to_datetime(df_stg['created_on'].astype(str).str.replace(' at ', ' '), errors='coerce')
        
        # Populate raw_metadata
        df_stg['raw_metadata'] = df.apply(lambda x: x.to_json(), axis=1)

        with self.engine.begin() as conn:
            conn.execute(text("CREATE TEMP TABLE tmp_grab (LIKE stg_grab_orders INCLUDING ALL) ON COMMIT DROP"))
            df_stg.to_sql('tmp_grab', conn, if_exists='append', index=False)
            
            cols = ", ".join(mapping.values()) + ", raw_metadata"
            select_cols = ", ".join(mapping.values()) + ", raw_metadata"

            upsert_query = f"""
                INSERT INTO stg_grab_orders ({cols})
                SELECT {select_cols} FROM tmp_grab
                ON CONFLICT (long_order_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    total = EXCLUDED.total,
                    raw_metadata = EXCLUDED.raw_metadata,
                    ingested_at = CURRENT_TIMESTAMP;
            """
            conn.execute(text(upsert_query))
            
        print("✅ [DB] Grab staging ingestion completed.")

    def refresh_master(self):
        """Triggers the SQL function to normalize data to fact_transactions."""
        print("🔄 [DB] Refreshing Master Table (Tabel Gajah)...")
        with self.engine.begin() as conn:
            conn.execute(text("SELECT refresh_fact_transactions();"))
        print("✨ [DB] Master Table is now up to date!")

if __name__ == "__main__":
    # Test connection
    db = DatabaseManager()
    print("🐘 Database connection successful.")
