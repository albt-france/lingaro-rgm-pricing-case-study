-- 04 - Price-pack architecture: shelf price per ounce by pack size.
--
-- Business rule BR-08: within a category, a bigger pack of the same manufacturer should not cost
-- more per ounce than a smaller pack ("inverted pack-price ladder"). Prices use the BASE price
-- (regular shelf price), so promotions do not distort the ladder.

CREATE OR REPLACE TABLE ppa AS
SELECT category,
       sub_category,
       manufacturer,
       upc,
       product_name AS description,
       size,
       size_oz,
       SUM(units)                                               AS units,
       ROUND(SUM(base_price * units) / SUM(units), 3)           AS avg_base_price,
       ROUND(SUM(base_price * units) / SUM(units) / ANY_VALUE(size_oz), 4) AS base_price_per_oz
FROM sales_enriched
WHERE dq_ok = 1 AND size_oz IS NOT NULL
GROUP BY ALL;

-- Flag inversions: for each pack, compare with the next smaller pack of the same manufacturer
-- in the same sub-category.
SELECT a.category,
       a.sub_category,
       a.manufacturer,
       a.description                       AS bigger_pack,
       a.size_oz                           AS bigger_oz,
       a.base_price_per_oz                 AS bigger_price_per_oz,
       b.description                       AS smaller_pack,
       b.size_oz                           AS smaller_oz,
       b.base_price_per_oz                 AS smaller_price_per_oz,
       ROUND(a.base_price_per_oz / b.base_price_per_oz - 1, 3) AS premium_per_oz
FROM ppa a
JOIN ppa b
  ON a.category = b.category AND a.sub_category = b.sub_category
 AND a.manufacturer = b.manufacturer AND a.size_oz > b.size_oz
WHERE a.base_price_per_oz > b.base_price_per_oz
ORDER BY premium_per_oz DESC;
