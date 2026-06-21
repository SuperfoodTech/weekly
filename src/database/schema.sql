-- Superfood Reporting System (SRS) Schema

-- 1. Master Merchant Table (Dimension)
CREATE TABLE IF NOT EXISTS dim_merchants (
    store_id TEXT PRIMARY KEY,
    platform TEXT, -- GrabFood, ShopeeFood, GoFood
    outlet_name TEXT,
    branch_name TEXT,
    group_code TEXT,
    owner_name TEXT,
    merchant_id TEXT,
    merchant_name TEXT,
    username TEXT,
    status TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Staging Grab Orders (Raw Data Lake)
CREATE TABLE IF NOT EXISTS stg_grab_orders (
    id SERIAL PRIMARY KEY,
    merchant_name TEXT,
    merchant_id TEXT,
    store_name TEXT,
    store_id TEXT,
    updated_on TEXT,
    created_on TIMESTAMP,
    status TEXT,
    transaction_id TEXT,
    long_order_id TEXT UNIQUE,
    amount NUMERIC(15,2),
    discount_merchant_funded NUMERIC(15,2),
    delivery_fee_discount_merchant_funded NUMERIC(15,2),
    net_sales NUMERIC(15,2),
    marketing_success_fee NUMERIC(15,2),
    order_commission NUMERIC(15,2),
    total NUMERIC(15,2),
    raw_metadata JSONB,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Staging Shopee Orders (Raw Data Lake)
CREATE TABLE IF NOT EXISTS stg_shopee_orders (
    id SERIAL PRIMARY KEY,
    store_id TEXT,
    store_name TEXT,
    transaction_type TEXT,
    transaction_id TEXT UNIQUE,
    complete_time TIMESTAMP,
    status TEXT,
    food_original_price NUMERIC(15,2),
    item_discounts NUMERIC(15,2),
    flash_sale_discount NUMERIC(15,2),
    surcharge_fee NUMERIC(15,2),
    merchant_voucher_subsidy NUMERIC(15,2),
    platform_flash_sale_subsidy NUMERIC(15,2),
    food_voucher_subsidy NUMERIC(15,2),
    food_direct_discount NUMERIC(15,2),
    transaction_amount NUMERIC(15,2),
    checkout_murah_price NUMERIC(15,2),
    notes TEXT,
    net_sales NUMERIC(15,2),
    commission NUMERIC(15,2),
    revenue NUMERIC(15,2),
    raw_metadata JSONB,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Unified Master Table (Tabel Gajah)
CREATE TABLE IF NOT EXISTS fact_transactions (
    id SERIAL PRIMARY KEY,
    order_id_duplicate INTEGER DEFAULT 1,
    year INTEGER,
    month TEXT,
    week TEXT,
    transaction_date DATE,
    hour INTEGER,
    platform VARCHAR(20) NOT NULL, -- 'GrabFood' or 'ShopeeFood'
    merchant_id TEXT NOT NULL,
    group_code TEXT,
    outlet_name TEXT,
    branch_name TEXT,
    store_name TEXT,
    created_on TIMESTAMP NOT NULL,
    status TEXT,
    is_success INTEGER DEFAULT 0,
    is_cancelled INTEGER DEFAULT 0,
    external_id TEXT NOT NULL,     -- Long Order ID / Transaction ID
    gross_sales NUMERIC(15,2),     -- Amount / Food Original Price
    discounts NUMERIC(15,2),       -- Discount (Merchant-Funded)
    delivery_discount NUMERIC(15,2), 
    net_sales NUMERIC(15,2),
    marketing_fee NUMERIC(15,2),
    commission NUMERIC(15,2),      -- Order Commission
    ofd_fees NUMERIC(15,2),
    revenue NUMERIC(15,2),         -- Total Payout
    gmv_vs_ofd_commission TEXT,    
    gmv_vs_ofd_fees TEXT,
    gmv_vs_revenue TEXT,
    move_to_oe_op TEXT,
    raw_record_id INTEGER,         -- Reference to stg table ID
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, external_id)
);

CREATE INDEX IF NOT EXISTS idx_fact_date ON fact_transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_fact_platform ON fact_transactions(platform);
CREATE INDEX IF NOT EXISTS idx_fact_group ON fact_transactions(group_code);
