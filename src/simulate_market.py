"""Step 7 - SIMULATED external market data, in the style of NielsenIQ / Circana.

!! Every number written by this script is SIMULATED (random seed 42). It is NOT NielsenIQ,
!! Circana, dunnhumby, Lingaro or client data. It exists to show how such data would enter the
!! product (model, measures, pages) because real panel data is paid and not public.

Calibration on the real retail data (data/output/sql_03_hierarchy_aggregates.csv and the clean sales):
  - the retailer's quarterly revenue by category x manufacturer is the "own retailer" sales;
  - the total market is the retailer's sales divided by an ASSUMED retailer share of the market;
  - market value share by manufacturer = retailer share x a random brand-specific distortion
    (brands sell better or worse elsewhere), renormalised to 100% per category;
  - competitor average price = retailer price x (1 + brand offset + quarterly noise);
  - numeric distribution (% of stores selling) and weighted distribution (% of category sales of
    the stores selling) drawn around plausible levels: leaders near full distribution.
All assumptions are written in data/ASSUMPTIONS.md.

Output: data/output/market_sim.csv  (category x manufacturer x quarter), column data_label = SIMULATED

Usage:  python src/simulate_market.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

CLEAN, OUT = Path("data/clean"), Path("data/output")
SEED = 42
RETAILER_SHARE = 0.08          # ASSUMED share of the regional market held by the retailer
BRAND_DISTORTION_SD = 0.25     # how differently a brand sells outside this retailer (log scale)
PRICE_OFFSET_SD = 0.06         # brand-level gap between competitor and retailer prices
PRICE_NOISE_SD = 0.02          # quarter-to-quarter noise on competitor prices


def main():
    rng = np.random.default_rng(SEED)
    s = pd.read_csv(CLEAN / "sales_weekly.csv", parse_dates=["week_end_date"],
                    usecols=["week_end_date", "store_id", "upc", "units", "spend", "dq_ok"])
    p = pd.read_csv(CLEAN / "products.csv", usecols=["upc", "category", "manufacturer"])
    s = s[s["dq_ok"] == 1].merge(p, on="upc")
    s["quarter"] = s["week_end_date"].dt.to_period("Q").astype(str)
    # complete quarters only (the data starts mid-January 2009 and ends with one week of 2012)
    weeks = s.groupby("quarter")["week_end_date"].nunique()
    s = s[s["quarter"].isin(weeks[weeks >= 12].index)]
    n_stores = s["store_id"].nunique()

    q = s.groupby(["category", "manufacturer", "quarter"], as_index=False).agg(
        retailer_revenue=("spend", "sum"), retailer_units=("units", "sum"), stores_selling=("store_id", "nunique"))
    q["retailer_price"] = q["retailer_revenue"] / q["retailer_units"]

    brands = q[["category", "manufacturer"]].drop_duplicates().reset_index(drop=True)
    brands["distortion"] = np.exp(rng.normal(0, BRAND_DISTORTION_SD, len(brands)))
    brands["price_offset"] = rng.normal(0, PRICE_OFFSET_SD, len(brands))
    q = q.merge(brands, on=["category", "manufacturer"])

    # market value: retailer revenue scaled up, then re-split between brands with the distortion
    cat_q = q.groupby(["category", "quarter"])["retailer_revenue"].transform("sum")
    q["retailer_value_share"] = q["retailer_revenue"] / cat_q
    raw = q["retailer_value_share"] * q["distortion"]
    q["market_value_share"] = raw / raw.groupby([q["category"], q["quarter"]]).transform("sum")
    q["market_value"] = q["market_value_share"] * cat_q / RETAILER_SHARE

    q["competitor_avg_price"] = q["retailer_price"] * (1 + q["price_offset"]
                                                      + rng.normal(0, PRICE_NOISE_SD, len(q)))
    q["price_index_vs_competitors"] = 100 * q["retailer_price"] / q["competitor_avg_price"]

    # distribution: anchored on the real share of the retailer's stores selling the brand
    real_nd = q["stores_selling"] / n_stores
    q["numeric_distribution"] = np.clip(real_nd * rng.uniform(0.85, 1.0, len(q)), 0.05, 1.0)
    q["weighted_distribution"] = np.clip(q["numeric_distribution"] + rng.uniform(0.0, 0.08, len(q)), 0.05, 1.0)
    q["data_label"] = "SIMULATED"
    q["brand_key"] = q["category"] + " | " + q["manufacturer"]   # key to the Brand dimension

    cols = ["brand_key", "category", "manufacturer", "quarter", "market_value", "market_value_share", "retailer_revenue", "retailer_value_share",
            "retailer_price", "competitor_avg_price", "price_index_vs_competitors", "numeric_distribution",
            "weighted_distribution", "data_label"]
    q[cols].round(4).to_csv(OUT / "market_sim.csv", index=False)
    last = q[q["quarter"] == q["quarter"].max()]
    print(last[["category", "manufacturer", "market_value_share", "retailer_value_share",
                "price_index_vs_competitors"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
