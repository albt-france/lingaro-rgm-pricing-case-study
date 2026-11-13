"""Step 2 - load the clean CSVs into DuckDB (in memory) and run every query in sql/ in order.

Each .sql file may hold several statements; the result of the LAST statement is saved to
data/output/sql_<file name>.csv so it can be checked and read by Power BI.

Usage:  python src/run_sql.py
"""
from pathlib import Path

import duckdb

OUT = Path("data/output")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    for table, f in {"sales": "sales_weekly", "products": "products", "stores": "stores"}.items():
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM read_csv_auto('data/clean/{f}.csv')")
    for q in sorted(Path("sql").glob("*.sql")):
        statements = [s for s in q.read_text(encoding="utf-8").split(";") if s.strip()
                      and not all(ln.strip().startswith("--") or not ln.strip() for ln in s.splitlines())]
        for s in statements[:-1]:
            con.execute(s)
        df = con.execute(statements[-1]).df()
        df.to_csv(OUT / f"sql_{q.stem}.csv", index=False)
        print(f"== {q.name}: {len(df)} rows")
        print(df.head(10).to_string(index=False))
    # keep the promo week table for the Python steps (local, row level)
    con.execute("COPY promo_weeks TO 'data/clean/promo_weeks.parquet' (FORMAT parquet)")
    # the same rows, fewer columns, as CSV: this is the Sales fact table read by Power BI
    con.execute("""COPY (SELECT week_end_date, store_id, upc, units, spend, price, base_price, discount_pct,
                               feature, display, tpr_only, promo_type, is_promo, dq_ok,
                               ROUND(baseline_units, 3) AS baseline_units, baseline_n_weeks,
                               CAST(is_post_promo_week AS INTEGER) AS is_post_promo_week
                        FROM promo_weeks ORDER BY upc, store_id, week_end_date)
                   TO 'data/clean/sales_promo_weekly.csv' (HEADER)""")
    con.execute("COPY ppa TO 'data/output/ppa_products.csv' (HEADER)")


if __name__ == "__main__":
    main()
