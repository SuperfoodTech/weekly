
--1. Master Merchant Table (Dimension)
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
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Staging Grab Orders (Raw Data Lake)
CREATE TABLE IF NOT EXISTS stg_grab_orders (
    id SERIAL PRIMARY KEY,
    month TEXT,
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
    month TEXT,
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
    move_to_oe_op TEXT,
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
    merchant_id TEXT,
    group_code TEXT,
    outlet_name TEXT,
    branch_name TEXT,
    store_name TEXT,
    created_on TIMESTAMP,
    status TEXT,
    is_success INTEGER DEFAULT 0,
    is_cancelled INTEGER DEFAULT 0,
    external_id TEXT NOT NULL,     -- Long Order ID / Transaction ID
    gross_amount NUMERIC(15,2),    -- Amount / Food Original Price
    discounts NUMERIC(15,2),       -- Discount (Merchant-Funded)
    delivery_discount NUMERIC(15,2), 
    net_sales NUMERIC(15,2),
    marketing_fee NUMERIC(15,2),
    commission NUMERIC(15,2),   
    revenue NUMERIC(15,2),         
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

-- 5. Stored Function for ETL Normalization
CREATE OR REPLACE FUNCTION refresh_fact_transactions()
RETURNS void AS $$
BEGIN
    -- 1. PROSES DATA GRABFOOD
    INSERT INTO fact_transactions (
        platform, external_id, transaction_date, created_on, year, month, week,
        merchant_id, group_code, outlet_name, branch_name, store_name, status,
        gross_amount, discounts, delivery_discount, net_sales, 
        marketing_fee, commission, ofd_fees, revenue,
        raw_record_id
    )
    SELECT 
        'GrabFood', 
        stg.long_order_id, 
        stg.created_on::DATE,
        stg.created_on,
        EXTRACT(YEAR FROM stg.created_on),
        TO_CHAR(stg.created_on, 'Month'),
        TO_CHAR(stg.created_on, 'IYYY-"W"IW'),
        COALESCE(stg.merchant_id, m.merchant_id, 'UNKNOWN'),
        COALESCE(m.group_code, 'UNKNOWN'),
        COALESCE(m.outlet_name, stg.merchant_name),
        COALESCE(m.branch_name, 'UNKNOWN'),
        stg.store_name,
        stg.status,
        stg.amount, 
        stg.discount_merchant_funded, 
        stg.delivery_fee_discount_merchant_funded,
        -- Net Sales (GMV) = Amount + Discounts + Delivery Discounts
        (COALESCE(stg.amount, 0) + COALESCE(stg.discount_merchant_funded, 0) + COALESCE(stg.delivery_fee_discount_merchant_funded, 0)) as calculated_net_sales,
        stg.marketing_success_fee,
        stg.order_commission,
        -- OFD Fees = ABS(Marketing Fee + Commission)
        ABS(COALESCE(stg.order_commission, 0) + COALESCE(stg.marketing_success_fee, 0)) as ofd_fees,
        -- Revenue = Net Sales - OFD Fees
        ((COALESCE(stg.amount, 0) + COALESCE(stg.discount_merchant_funded, 0) + COALESCE(stg.delivery_fee_discount_merchant_funded, 0)) - ABS(COALESCE(stg.order_commission, 0) + COALESCE(stg.marketing_success_fee, 0))) as calculated_revenue,
        stg.id
    FROM stg_grab_orders stg
    LEFT JOIN dim_merchants m ON stg.store_id = m.store_id
    ON CONFLICT (platform, external_id) 
    DO UPDATE SET 
        status = EXCLUDED.status,
        revenue = EXCLUDED.revenue,
        updated_at = CURRENT_TIMESTAMP;

    -- 2. PROSES DATA SHOPEEFOOD
    INSERT INTO fact_transactions (
        platform, external_id, transaction_date, created_on, year, month, week,
        merchant_id, group_code, outlet_name, branch_name, store_name, status,
        gross_amount, discounts, net_sales, 
        commission, ofd_fees, revenue,
        move_to_oe_op, raw_record_id
    )
    SELECT 
        'ShopeeFood', 
        stg.transaction_id, 
        stg.complete_time::DATE,
        stg.complete_time,
        EXTRACT(YEAR FROM stg.complete_time),
        TO_CHAR(stg.complete_time, 'Month'),
        TO_CHAR(stg.complete_time, 'IYYY-"W"IW'),
        COALESCE(m.merchant_id, 'UNKNOWN'),
        COALESCE(m.group_code, 'UNKNOWN'),
        COALESCE(m.outlet_name, stg.store_name),
        COALESCE(m.branch_name, 'UNKNOWN'),
        stg.store_name,
        stg.status,
        stg.food_original_price, 
        -- Discounts (J+K+M+O)
        (COALESCE(stg.item_discounts, 0) + COALESCE(stg.flash_sale_discount, 0) + COALESCE(stg.merchant_voucher_subsidy, 0) + COALESCE(stg.food_voucher_subsidy, 0)) as total_discounts,
        -- Net Sales (T) = Food Original Price - Item Discounts
        (COALESCE(stg.food_original_price, 0) - COALESCE(stg.item_discounts, 0)) as calculated_net_sales,
        -- Commission (U) = Transaction Amount (Q) * 25%
        (COALESCE(stg.transaction_amount, 0) * 0.25) as calculated_commission,
        -- OFD Fees = Same as Commission for Shopee
        (COALESCE(stg.transaction_amount, 0) * 0.25) as calculated_ofd_fees,
        -- Revenue (V) = Transaction Amount (Q) - Commission (U)
        (COALESCE(stg.transaction_amount, 0) - (COALESCE(stg.transaction_amount, 0) * 0.25)) as calculated_revenue,
        stg.move_to_oe_op,
        stg.id
    FROM stg_shopee_orders stg
    LEFT JOIN dim_merchants m ON stg.store_id = m.store_id
    ON CONFLICT (platform, external_id) 
    DO UPDATE SET 
        status = EXCLUDED.status,
        revenue = EXCLUDED.revenue,
        updated_at = CURRENT_TIMESTAMP;

    -- 3. HITUNG PERSENTASE GMV (AA, AB, AC)
    UPDATE fact_transactions
    SET 
        gmv_vs_ofd_commission = CASE WHEN net_sales <> 0 THEN ROUND((commission / net_sales * 100), 2) || '%' ELSE '0%' END,
        gmv_vs_ofd_fees = CASE WHEN net_sales <> 0 THEN ROUND((ofd_fees / net_sales * 100), 2) || '%' ELSE '0%' END,
        gmv_vs_revenue = CASE WHEN net_sales <> 0 THEN ROUND((revenue / net_sales * 100), 2) || '%' ELSE '0%' END
    WHERE updated_at >= (CURRENT_TIMESTAMP - INTERVAL '1 hour');

END;
$$ LANGUAGE plpgsql;
