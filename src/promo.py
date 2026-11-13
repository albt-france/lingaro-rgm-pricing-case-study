"""Step 4 - promotion effectiveness: uplift, post-promo dip, cannibalisation and ROI.

Input : data/clean/promo_weeks.parquet (built by sql/02_promo_baseline.sql through run_sql.py)
Output: data/output/promo_effectiveness.csv  (category x brand x promotion type)
        data/output/promo_summary.csv        (category x promotion type)
        data/output/promo_dip.csv            (post-promotion dip per category)
        data/output/cannibalisation.csv      (what happens to the other products of the category)

Definitions (product/BUSINESS_RULES.md):
  baseline units  = average units of clean non-promo weeks within +/-8 weeks       (BR-03)
  uplift          = units / baseline - 1                                            (BR-04)
  ASSUMED margin  = 30% of the regular price, for whoever funds the discount         (BR-09)
  unit cost c     = base_price * (1 - margin)
  net incremental profit = units*(price - c) - baseline*(base_price - c)
                           (profit with the promotion minus profit we would have made without it)
  discount cost   = (base_price - price) * units   (the money given away on every unit sold)
  ROI             = net incremental profit / discount cost   (> 0: the promotion paid back)

Usage:  python src/promo.py
"""
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

CLEAN, OUT = Path("data/clean"), Path("data/output")
MARGIN = 0.30                    # ASSUMED gross margin at regular price (see data/ASSUMPTIONS.md)
SENSITIVITY = [0.20, 0.30, 0.40]
MIN_BASE_WEEKS = 4               # BR-03: a baseline needs >= 4 clean weeks in its window


def money(d, margin):
    """Add profit columns for a given margin assumption."""
    c = d["base_price"] * (1 - margin)
    d = d.copy()
    d["incr_units"] = d["units"] - d["baseline_units"]
    d["incr_revenue"] = d["units"] * d["price"] - d["baseline_units"] * d["base_price"]
    d["discount_cost"] = (d["base_price"] - d["price"]).clip(lower=0) * d["units"]
    d["net_incr_profit"] = d["units"] * (d["price"] - c) - d["baseline_units"] * (d["base_price"] - c)
    return d


def summarise(d, keys):
    g = d.groupby(keys, as_index=False).agg(
        promo_weeks=("units", "size"), units=("units", "sum"), baseline_units=("baseline_units", "sum"),
        avg_discount=("discount_pct", "mean"), incr_units=("incr_units", "sum"),
        incr_revenue=("incr_revenue", "sum"), discount_cost=("discount_cost", "sum"),
        net_incr_profit=("net_incr_profit", "sum"), paid_back_weeks=("net_incr_profit", lambda x: (x > 0).sum()))
    g["uplift"] = g["units"] / g["baseline_units"] - 1
    g["roi"] = np.where(g["discount_cost"] > 0, g["net_incr_profit"] / g["discount_cost"], np.nan)
    g["share_weeks_paid_back"] = g["paid_back_weeks"] / g["promo_weeks"]
    return g.round(4)


def main():
    # DuckDB reads the parquet file written by run_sql.py (no extra library needed)
    pw = duckdb.sql(f"SELECT * FROM '{(CLEAN / 'promo_weeks.parquet').as_posix()}'").df()
    promo = pw[(pw["is_promo"] == 1) & (pw["baseline_n_weeks"] >= MIN_BASE_WEEKS) & (pw["dq_ok"] == 1)
               & (pw["baseline_units"] > 0)]
    print("promo weeks with a reliable baseline:", len(promo), "of", int(pw["is_promo"].sum()))

    # --- post-promotion dip per category (BR-05) ---
    post = pw[pw["is_post_promo_week"] & (pw["baseline_n_weeks"] >= MIN_BASE_WEEKS) & (pw["baseline_units"] > 0)]
    dip = post.groupby("category", as_index=False).agg(post_weeks=("units", "size"), units=("units", "sum"),
                                                       baseline_units=("baseline_units", "sum"))
    dip["dip"] = dip["units"] / dip["baseline_units"] - 1
    dip["dip_units"] = dip["units"] - dip["baseline_units"]
    dip.round(4).to_csv(OUT / "promo_dip.csv", index=False)

    # --- effectiveness at the assumed margin, then sensitivity ---
    eff = summarise(money(promo, MARGIN), ["category", "manufacturer", "promo_type"])
    eff.insert(0, "brand_key", eff["category"] + " | " + eff["manufacturer"])   # key to the Brand dimension
    eff.to_csv(OUT / "promo_effectiveness.csv", index=False)
    frames = []
    for m in SENSITIVITY:
        s = summarise(money(promo, m), ["category", "promo_type"])
        s["margin_assumption"] = m
        frames.append(s)
    summ = pd.concat(frames)
    # net of the post-promo dip: the units lost after each promo week also cost margin
    summ = summ.merge(dip[["category", "dip"]], on="category", how="left")
    lost = -summ["dip"].clip(upper=0) * summ["baseline_units"] / summ["promo_weeks"]  # rough: one dip week per promo week
    avg_base_price = (promo.groupby("category").apply(lambda x: np.average(x["base_price"], weights=x["units"]),
                                                       include_groups=False).rename("avg_base_price"))
    summ = summ.join(avg_base_price, on="category")
    summ["dip_profit_loss"] = lost * summ["promo_weeks"] * summ["avg_base_price"] * summ["margin_assumption"]
    summ["net_incr_profit_after_dip"] = summ["net_incr_profit"] - summ["dip_profit_loss"]
    summ["roi_after_dip"] = np.where(summ["discount_cost"] > 0,
                                     summ["net_incr_profit_after_dip"] / summ["discount_cost"], np.nan)
    summ.round(4).to_csv(OUT / "promo_summary.csv", index=False)

    # --- cannibalisation: other products of the category in a store-week where one product is on promo ---
    on_promo = (pw[pw["is_promo"] == 1].groupby(["store_id", "week_idx", "category"]).size().rename("n_on_promo"))
    others = pw.join(on_promo, on=["store_id", "week_idx", "category"])
    others = others[(others["is_promo"] == 0) & (others["baseline_n_weeks"] >= MIN_BASE_WEEKS)
                    & (others["baseline_units"] > 0) & (others["dq_ok"] == 1)]
    others["context"] = np.where(others["n_on_promo"].fillna(0) > 0,
                                 "Another product of the category on promo", "No promo in the category")
    can = others.groupby(["category", "context"], as_index=False).agg(
        weeks=("units", "size"), units=("units", "sum"), baseline_units=("baseline_units", "sum"))
    can["vs_baseline"] = can["units"] / can["baseline_units"] - 1
    can.round(4).to_csv(OUT / "cannibalisation.csv", index=False)

    print(summ[summ["margin_assumption"] == MARGIN][["category", "promo_type", "promo_weeks", "avg_discount",
                                                       "uplift", "roi", "roi_after_dip"]].to_string(index=False))
    print(dip.round(3).to_string(index=False))
    print(can.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
