# Clean data (not included)

`src/prepare.py` and `src/run_sql.py` write the cleaned, row-level dunnhumby tables here
(`sales_weekly.csv`, `products.csv`, `stores.csv`, `sales_promo_weekly.csv`, `promo_weeks.parquet`).
They are derived from data that cannot be redistributed, so they stay local.
Run `python src/run_all.py` (real data) or `python src/run_all.py --sample` (SIMULATED sample) to create them.
Power BI reads its sales fact table from this folder.
