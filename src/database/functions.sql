-- database/functions.sql

CREATE OR REPLACE FUNCTION refresh_fact_transactions()
RETURNS void AS $$
BEGIN
    -- 1. PROSES DATA GRABFOOD
    INSERT INTO fact_transactions (
        platform, external_id, transaction_date, year, month, week,
        group_code, outlet_name, branch_name, 
        gross_amount, discounts, delivery_discount, net_sales, 
        marketing_fee, commission, ofd_fees, revenue,
        raw_record_id
    )
    SELECT 
        'GrabFood', 
        stg.long_order_id, 
        stg.created_on,
        EXTRACT(YEAR FROM stg.created_on),
        TO_CHAR(stg.created_on, 'Month'),
        TO_CHAR(stg.created_on, 'IYYY-"W"IW'),
        COALESCE(m.group_code, 'UNKNOWN'),
        COALESCE(m.outlet_name, stg.merchant_name),
        COALESCE(m.branch_name, 'UNKNOWN'),
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
        revenue = EXCLUDED.revenue,
        updated_at = CURRENT_TIMESTAMP;

    -- 2. PROSES DATA SHOPEEFOOD
    INSERT INTO fact_transactions (
        platform, external_id, transaction_date, year, month, week,
        group_code, outlet_name, branch_name, 
        gross_amount, discounts, net_sales, 
        commission, ofd_fees, revenue,
        raw_record_id
    )
    SELECT 
        'ShopeeFood', 
        stg.transaction_id, 
        stg.complete_time,
        EXTRACT(YEAR FROM stg.complete_time),
        TO_CHAR(stg.complete_time, 'Month'),
        TO_CHAR(stg.complete_time, 'IYYY-"W"IW'),
        COALESCE(m.group_code, 'UNKNOWN'),
        COALESCE(m.outlet_name, stg.store_name),
        COALESCE(m.branch_name, 'UNKNOWN'),
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
        stg.id
    FROM stg_shopee_orders stg
    LEFT JOIN dim_merchants m ON stg.store_id = m.store_id
    ON CONFLICT (platform, external_id) 
    DO UPDATE SET 
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
