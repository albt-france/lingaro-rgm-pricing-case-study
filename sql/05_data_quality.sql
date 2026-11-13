-- 05 - Data quality checks (business rule BR-07). Each check returns how many rows it hits.
-- A failing row is kept in the data but excluded from models (dq_ok = 0).

SELECT 'Rows in weekly sales'                       AS check_name, COUNT(*) AS rows_hit, NULL AS note FROM sales
UNION ALL
SELECT 'Missing or non-positive price',              SUM(dq_missing_price), 'excluded from models' FROM sales
UNION ALL
SELECT 'Price above base price (+5%)',               SUM(dq_price_above_base), 'excluded from models' FROM sales
UNION ALL
SELECT 'Extreme price (> 3x or < 1/3 product median)', SUM(dq_extreme_price), 'excluded from models' FROM sales
UNION ALL
SELECT 'Zero or negative units',                     SUM(dq_zero_units), 'excluded from models' FROM sales
UNION ALL
SELECT 'Duplicate week x store x product rows',      COUNT(*) - COUNT(DISTINCT (week_end_date, store_id, upc)), 'must be 0' FROM sales
UNION ALL
SELECT 'Stores listed twice in store lookup',        SUM(dq_duplicate_record), 'conflicting segment: first record kept' FROM stores
UNION ALL
SELECT 'Store not in store lookup',                  SUM(dq_unknown_store), 'excluded from market views' FROM sales
UNION ALL
-- gaps: store x product pairs that are missing some weeks (possible out-of-stock or delisting)
SELECT 'Store x product pairs with missing weeks',  COUNT(*), 'possible out-of-stock / delisting'
FROM (
    SELECT store_id, upc, COUNT(*) AS weeks
    FROM sales
    GROUP BY ALL
    HAVING COUNT(*) < (SELECT COUNT(DISTINCT week_end_date) FROM sales)
)
UNION ALL
SELECT 'Products phasing out (last 13 weeks < 25% of normal)', SUM(phase_out), 'kept in history, not simulated' FROM products
WHERE upc IN (SELECT DISTINCT upc FROM sales)
UNION ALL
SELECT 'Stores selling fewer than 52 weeks',         COUNT(*), 'thin history'
FROM (SELECT store_id FROM sales GROUP BY ALL HAVING COUNT(DISTINCT week_end_date) < 52)
UNION ALL
SELECT 'Rows passing every check',                   SUM(dq_ok), 'used by models' FROM sales;
