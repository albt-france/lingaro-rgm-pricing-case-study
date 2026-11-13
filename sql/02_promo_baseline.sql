-- 02 - Promotion baseline, uplift and post-promotion dip.
--
-- Business rule BR-03 (baseline): for each store x product, the baseline in week w is the
-- average units of "clean" non-promo weeks within +/- 8 weeks of w. A clean week is a week
-- with no promotion, not one of the 2 weeks right after a promotion (they may show a dip),
-- and that passed the quality checks.
-- BR-04 (uplift): uplift = units / baseline - 1, and incremental units = units - baseline.
-- BR-05 (post-promo dip): for the first non-promo week after a promo, dip = units / baseline - 1.

CREATE OR REPLACE TABLE promo_weeks AS
WITH flagged AS (
    SELECT *,
           -- was there a promo 1 or 2 weeks earlier for the same store x product?
           MAX(is_promo) OVER w_prev2                                           AS promo_in_prev2,
           LAG(is_promo) OVER w_order                                            AS promo_prev1
    FROM sales_enriched
    WINDOW w_order AS (PARTITION BY store_id, upc ORDER BY week_idx),
           w_prev2 AS (PARTITION BY store_id, upc ORDER BY week_idx
                       RANGE BETWEEN 2 PRECEDING AND 1 PRECEDING)
),
base AS (
    SELECT *,
           (is_promo = 0 AND COALESCE(promo_in_prev2, 0) = 0 AND dq_ok = 1)     AS is_clean_base
    FROM flagged
)
SELECT *,
       AVG(CASE WHEN is_clean_base THEN units END) OVER (
           PARTITION BY store_id, upc ORDER BY week_idx
           RANGE BETWEEN 8 PRECEDING AND 8 FOLLOWING)                          AS baseline_units,
       COUNT(CASE WHEN is_clean_base THEN 1 END) OVER (
           PARTITION BY store_id, upc ORDER BY week_idx
           RANGE BETWEEN 8 PRECEDING AND 8 FOLLOWING)                          AS baseline_n_weeks,
       (is_promo = 0 AND COALESCE(promo_prev1, 0) = 1)                           AS is_post_promo_week
FROM base;

-- Promo effectiveness by category, manufacturer and promotion type.
-- Only promo weeks with a reliable baseline (>= 4 clean weeks in the window) are used.
SELECT category,
       manufacturer,
       promo_type,
       COUNT(*)                                                      AS promo_weeks,
       ROUND(AVG(discount_pct), 3)                                   AS avg_discount,
       ROUND(SUM(units) / SUM(baseline_units) - 1, 3)                AS uplift,
       ROUND(SUM(units - baseline_units), 0)                         AS incremental_units
FROM promo_weeks
WHERE is_promo = 1 AND baseline_n_weeks >= 4 AND dq_ok = 1
GROUP BY ALL
ORDER BY category, manufacturer, promo_type;
