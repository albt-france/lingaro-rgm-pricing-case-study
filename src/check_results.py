"""Step 9 - automated checks: business-rule unit tests + reconciliation of every output.

Each check maps to a line of product/TEST_PLAN.md. The script prints PASS/FAIL and writes
data/output/checks.csv. It exits with code 1 if any check fails.

Usage:  python src/check_results.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from prepare import size_to_oz  # noqa: E402
from simulator import classify, simulate  # noqa: E402

OUT, CLEAN = Path("data/output"), Path("data/clean")
results = []


def check(test_id, name, ok, detail=""):
    results.append(dict(test_id=test_id, check=name, result="PASS" if ok else "FAIL", detail=str(detail)))
    print(f"[{'PASS' if ok else 'FAIL'}] {test_id} {name} {detail}")


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol


# ---------- T1 unit tests of business rules (hand-computed expected values) ----------
m, base, price, units, baseline = 0.30, 4.00, 3.00, 100, 40
c = base * (1 - m)
net = units * (price - c) - baseline * (base - c)
cost = (base - price) * units
check("T1.1", "ROI example AC-03.2 = -28%", close(net / cost, -0.28), f"{net / cost:.4f}")
v, r, p = simulate(-1.5, 0.05)
check("T1.2", "Simulator example AC-05.1", close(v, -0.0706, 1e-4) and close(r, -0.0241, 1e-4) and close(p, 0.0843, 1e-4),
      f"vol {v:.4f} rev {r:.4f} profit {p:.4f}")
try:
    simulate(-1.5, 0.12)
    check("T1.3", "Simulator refuses +12% (BR-10)", False)
except ValueError:
    check("T1.3", "Simulator refuses +12% (BR-10)", True)
check("T1.4", "Size parsing: 1 LT = 33.81 fl oz, 12.25 OZ = 12.25",
      close(size_to_oz("1 LT")[0], 33.814, 1e-3) and close(size_to_oz("12.25 OZ")[0], 12.25))
check("T1.5", "Stance classes (BR-11)",
      classify(-0.6, -0.8, -0.4).startswith("Low sensitivity: price") and classify(-4.0, -4.5, -3.5).startswith("Highly")
      and classify(-1.8, -2.1, -1.5).startswith("Moderate"))
check("T1.6", "Profit rises with price when |e| < 1/m", simulate(-3.0, 0.01)[2] > 0 and simulate(-3.6, 0.01)[2] < 0)

# ---------- T2 reconciliation of data and SQL outputs ----------
s = pd.read_csv(CLEAN / "sales_promo_weekly.csv")
raw = pd.read_csv(CLEAN / "sales_weekly.csv")
check("T2.1", "Row count kept through SQL baseline", len(s) == len(raw), f"{len(s)} vs {len(raw)}")
check("T2.2", "Revenue total identical (clean CSV vs SQL output)", close(s["spend"].sum(), raw["spend"].sum(), 0.01))
h = pd.read_csv(OUT / "sql_03_hierarchy_aggregates.csv")
tot = h.loc[h["level_id"] == 7, "revenue"].iloc[0]
cats = h.loc[h["level_id"] == 3, "revenue"].sum()
check("T2.3", "Hierarchy roll-up: categories add up to total (L52W)", abs(tot - cats) <= len(h), f"{tot} vs {cats}")
dq = pd.read_csv(OUT / "sql_05_data_quality.csv").set_index("check_name")["rows_hit"]
check("T2.4", "DQ: rows passing checks = dq_ok rows", dq["Rows passing every check"] == raw["dq_ok"].sum())
bad = raw[(raw["dq_ok"] == 1) & ((raw["price"] <= 0) | (raw["units"] <= 0))]
check("T2.5", "No row with price<=0 or units<=0 marked OK", len(bad) == 0, len(bad))
pw = s[(s["is_promo"] == 0) & (s["baseline_n_weeks"] >= 4)]
check("T2.6", "Baseline of non-promo weeks is close to actual units (no bias)",
      abs(pw["units"].sum() / pw["baseline_units"].sum() - 1) < 0.05,
      f"{pw['units'].sum() / pw['baseline_units'].sum() - 1:+.3%}")

# ---------- T3 model outputs ----------
el = pd.read_csv(OUT / "elasticity.csv")
pub = el[el["status"] == "Published"]
check("T3.1", "Every published elasticity is negative", (pub["elasticity"] < 0).all())
check("T3.2", "Every published interval width <= 1.5", ((pub["ci_high"] - pub["ci_low"]) <= 1.5).all())
check("T3.3", "Every published segment has >= 1,000 rows and >= 52 weeks",
      ((pub["n_obs"] >= 1000) & (pub["n_weeks"] >= 52)).all())
check("T3.4", "Point estimate inside its interval",
      ((el["elasticity"] >= el["ci_low"]) & (el["elasticity"] <= el["ci_high"]) | el["elasticity"].isna()).all())

eff = pd.read_csv(OUT / "promo_effectiveness.csv")
summ = pd.read_csv(OUT / "promo_summary.csv")
s30 = summ[summ["margin_assumption"] == 0.30]
check("T3.5", "Promo: brand table adds up to category table (net profit, 30%)",
      close(eff["net_incr_profit"].sum(), s30["net_incr_profit"].sum(), 1.0))
promo = s[(s["is_promo"] == 1) & (s["baseline_n_weeks"] >= 4) & (s["dq_ok"] == 1) & (s["baseline_units"] > 0)]
dax_like_uplift = promo["units"].sum() / promo["baseline_units"].sum() - 1   # same logic as DAX [Promo Uplift %]
py_uplift = eff["units"].sum() / eff["baseline_units"].sum() - 1
check("T3.6", "Promo uplift: DAX logic on Sales rows = Python table", close(dax_like_uplift, py_uplift, 1e-3),
      f"{dax_like_uplift:.4f} vs {py_uplift:.4f}")

grid = pd.read_csv(OUT / "scenario_grid.csv")
zero = grid[grid["price_change"].round(3) == 0]
check("T3.7", "Simulator: 0% price change gives 0 everywhere", np.allclose(zero[["volume_pct", "revenue_pct", "profit_pct"]], 0))
check("T3.8", "Simulator: ranges contain the central value",
      ((grid["volume_pct_low"] <= grid["volume_pct"] + 1e-9) & (grid["volume_pct"] <= grid["volume_pct_high"] + 1e-9)).all())
check("T3.9", "Simulator only uses published segments",
      set(grid["segment_id"]) <= set(pub["segment_id"]))

ms = pd.read_csv(OUT / "market_sim.csv")
shares = ms.groupby(["category", "quarter"])["market_value_share"].sum()
check("T3.10", "SIM market shares add to 100% per category-quarter", np.allclose(shares, 1, atol=1e-3))
check("T3.11", "Every SIM row labelled SIMULATED", (ms["data_label"] == "SIMULATED").all())
ppa = pd.read_csv(OUT / "ppa.csv")
wavg = ppa.assign(w=ppa["price_index_per_oz"] * ppa["units"]).groupby("sub_category").apply(
    lambda g: g["w"].sum() / g["units"].sum(), include_groups=False)
check("T3.12", "PPA: units-weighted price index = 100 per sub-category", np.allclose(wavg, 100, atol=0.5))

f = json.loads((OUT / "findings.json").read_text(encoding="utf-8"))
check("T4.1", "findings.json readable and complete",
      all(k in f for k in ["data", "elasticity", "promo", "ppa", "simulator", "markets", "market_sim", "eurostat"]))

pd.DataFrame(results).to_csv(OUT / "checks.csv", index=False)
fails = sum(r["result"] == "FAIL" for r in results)
print(f"\n{len(results) - fails}/{len(results)} checks passed")
sys.exit(1 if fails else 0)
