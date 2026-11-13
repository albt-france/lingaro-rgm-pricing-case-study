-- 03 - Aggregates along the product hierarchy: category -> manufacturer -> product.
-- Last 52 weeks only, so the numbers describe "the current year" of the data.
-- ROLLUP gives subtotals at every level in one pass (NULL = "all").

WITH last52 AS (
    SELECT *
    FROM sales_enriched
    WHERE week_idx > (SELECT MAX(week_idx) FROM sales_enriched) - 52
)
SELECT
    COALESCE(category, 'All categories')                         AS category,
    COALESCE(manufacturer, '(all)')                              AS manufacturer,
    COALESCE(product_name, '(all)')                               AS product,
    GROUPING(category, manufacturer, product_name)                AS level_id,   -- 0 = product, 1 = manufacturer, 3 = category, 7 = total
    SUM(units)                                                   AS units,
    ROUND(SUM(spend), 0)                                         AS revenue,
    ROUND(SUM(spend) / SUM(units), 2)                            AS avg_price,
    ROUND(SUM(base_price * units) / SUM(units), 2)               AS avg_base_price,
    ROUND(SUM(CASE WHEN is_promo = 1 THEN spend END) / SUM(spend), 3) AS promo_revenue_share
FROM last52
GROUP BY ROLLUP (category, manufacturer, product_name)
ORDER BY category, manufacturer, product;
