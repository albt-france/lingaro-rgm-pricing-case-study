"""Step 5 - scenario simulator: "what if we change the price of segment X by p%?"

With a constant elasticity e (log-log model), a price change p gives:
    volume   x (1 + p) ** e
    revenue  x (1 + p) ** (1 + e)
    gross profit x (1 + p) ** e * (m + p) / m        with m = ASSUMED gross margin at the current price
The range comes from the 95% interval of e (ci_low = more sensitive, ci_high = less sensitive).

Business rules:
  BR-06  only "Published" elasticities can be simulated
  BR-10  price changes are capped at +/-10%: the model is only trusted near observed prices
  BR-11  opportunity class from the elasticity (see classify())

The same formulas are implemented as DAX measures in the Power BI 'Scenario simulator' page,
so this script also serves as the test oracle for those measures (product/TEST_PLAN.md).

Usage:  python src/simulator.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("data/output")
MARGIN = 0.30
MAX_CHANGE = 0.10


def simulate(e, p, m=MARGIN):
    """Return (volume %, revenue %, profit %) for elasticity e and price change p (0.05 = +5%)."""
    if abs(p) > MAX_CHANGE + 1e-9:
        raise ValueError(f"BR-10: price change {p:+.0%} outside +/-{MAX_CHANGE:.0%}")
    vol = (1 + p) ** e - 1
    rev = (1 + p) ** (1 + e) - 1
    prof = (1 + p) ** e * (m + p) / m - 1
    return vol, rev, prof


def classify(e, lo, hi, m=MARGIN):
    """BR-11: turn an elasticity into a pricing stance.
    Revenue rises with price when |e| < 1; gross profit rises with a small price increase when |e| < 1/m."""
    if hi < -1 / m:
        return "Highly sensitive: protect price position, targeted promotions"
    if lo > -1:
        return "Low sensitivity: price increase candidate"
    if e > -1:
        return "Low sensitivity (uncertain): test a price increase"
    return "Moderate: price up grows profit but loses volume, test first"


def main():
    el = pd.read_csv(OUT / "elasticity.csv")
    pub = el[(el["status"] == "Published") & el["level"].isin(["Category", "Brand", "Product"])].copy()
    pub["stance"] = [classify(e, lo, hi) for e, lo, hi in zip(pub["elasticity"], pub["ci_low"], pub["ci_high"])]
    rows = []
    for _, r in pub.iterrows():
        for step in range(-10, 11):
            p = step / 100
            v, rv, pr = simulate(r["elasticity"], p)
            v_lo, rv_lo, pr_lo = simulate(r["ci_low"], p)    # more sensitive end
            v_hi, rv_hi, pr_hi = simulate(r["ci_high"], p)   # less sensitive end
            rows.append(dict(segment_id=r["segment_id"], level=r["level"], segment=r["segment"], price_change=p,
                             volume_pct=v, volume_pct_low=min(v_lo, v_hi), volume_pct_high=max(v_lo, v_hi),
                             revenue_pct=rv, revenue_pct_low=min(rv_lo, rv_hi), revenue_pct_high=max(rv_lo, rv_hi),
                             profit_pct=pr, profit_pct_low=min(pr_lo, pr_hi), profit_pct_high=max(pr_lo, pr_hi),
                             revenue_delta=rv * r["base_revenue_52w"],
                             profit_delta=pr * r["base_revenue_52w"] * MARGIN))
    grid = pd.DataFrame(rows).round(5)
    grid.to_csv(OUT / "scenario_grid.csv", index=False)
    pub[["segment_id", "level", "segment", "elasticity", "ci_low", "ci_high", "stance"]].to_csv(
        OUT / "pricing_stance.csv", index=False)
    five = grid[(grid["price_change"] == 0.05) & (grid["level"] != "Product")]
    print(five[["segment", "volume_pct", "volume_pct_low", "volume_pct_high", "revenue_pct", "profit_pct"]]
          .round(3).to_string(index=False))
    print(pub["stance"].value_counts().to_string())


if __name__ == "__main__":
    main()
