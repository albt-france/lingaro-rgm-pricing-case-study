-- 01 - Weekly sales enriched with the product hierarchy and the store market.
-- One row per week x store x product. This is the base view every other query reads.
-- Tables loaded by src/run_sql.py: sales (data/clean/sales_weekly.csv), products, stores.

CREATE OR REPLACE VIEW sales_enriched AS
SELECT
    s.week_end_date,
    -- week index 0..155, handy for rolling windows
    DATE_DIFF('week', MIN(s.week_end_date) OVER (), s.week_end_date)      AS week_idx,
    s.store_id,
    st.state                                                              AS market,
    st.segment                                                            AS store_segment,
    s.upc,
    p.category,
    p.sub_category,
    p.manufacturer,
    p.brand_key,
    p.description,
    p.product_name,
    p.size,
    p.size_oz,
    s.units,
    s.spend,
    s.price,
    s.base_price,
    s.discount_pct,
    s.feature,
    s.display,
    s.tpr_only,
    s.promo_type,
    s.is_promo,
    s.dq_ok
FROM sales s
JOIN products p USING (upc)
LEFT JOIN stores st USING (store_id);

-- quick check returned to the console: rows and totals per category
SELECT category,
       COUNT(*)                         AS rows,
       COUNT(DISTINCT upc)              AS products,
       COUNT(DISTINCT store_id)         AS stores,
       ROUND(SUM(spend) / 1e6, 2)       AS revenue_musd,
       ROUND(AVG(is_promo), 3)          AS promo_week_share
FROM sales_enriched
GROUP BY category
ORDER BY revenue_musd DESC;
