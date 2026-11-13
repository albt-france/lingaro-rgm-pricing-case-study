"""Generate the four walkthrough notebooks in notebooks/ (then run them with nbconvert).

The notebooks do not duplicate the pipeline: they import the same functions and read the same outputs,
and explain each step in plain words. They only display aggregates (never raw dunnhumby rows).

Usage:  python src/build_notebooks.py
        jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb
"""
from pathlib import Path

import nbformat as nbf

SETUP = """import os, sys
from pathlib import Path
# run from the repository root so relative paths work
if Path.cwd().name == "notebooks":
    os.chdir("..")
sys.path.insert(0, "src")
import pandas as pd, numpy as np
pd.set_option("display.width", 160, "display.max_columns", 20)"""


def nb(cells):
    n = nbf.v4.new_notebook()
    n["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                     "language_info": {"name": "python"}}
    n["cells"] = [nbf.v4.new_markdown_cell(c[3:]) if c.startswith("md:") else nbf.v4.new_code_cell(c) for c in cells]
    return n


NOTEBOOKS = {
    "01_prepare.ipynb": [
        "md:# 1 · Preparation and data quality\nWeekly store x product sales from dunnhumby *Breakfast at the Frat* "
        "(REAL RETAIL DATA, not redistributed). `src/prepare.py` cleans it and tags promotions (BR-02) and quality "
        "issues (BR-07); `sql/` builds the baseline and aggregates in DuckDB.",
        SETUP,
        "md:## Hierarchy: category > manufacturer > product (last 52 weeks, from `sql/03_hierarchy_aggregates.sql`)",
        "h = pd.read_csv('data/output/sql_03_hierarchy_aggregates.csv')\nh[h['level_id'] >= 1]",
        "md:## Promotion mix\nShare of store-product-weeks by promotion type (BR-02).",
        "s = pd.read_csv('data/clean/sales_promo_weekly.csv')\ns['promo_type'].value_counts(normalize=True).round(3)",
        "md:## Base price vs price paid\nThe base price is the regular shelf price; the gap with the price paid is the discount.",
        "s.groupby('promo_type')[['discount_pct']].describe().round(3)",
        "md:## Quality checks (`sql/05_data_quality.sql`)",
        "pd.read_csv('data/output/sql_05_data_quality.csv')",
    ],
    "02_elasticity.ipynb": [
        "md:# 2 · Price elasticity\n**Model:** `log(units) = e·log(price) + b1·feature + b2·display + (store x product) + "
        "month + trend`. Each product in each store has its own normal level, so `e` comes only from price moves over "
        "time; the assortment differs by store, which is why store and product are not separate effects.\n\n`e` is the elasticity: +1% price changes units by about `e`%. "
        "Example: e = -1.8 means +1% price, about -1.8% units, so revenue falls.\n\n"
        "It is a **correlation on historical data**, not an experiment.",
        SETUP,
        "import elasticity as el_mod\ndf = el_mod.load()\nprint(len(df), 'clean rows')",
        "md:## One regression in full: the most-sold category\nThe price coefficient is the elasticity; feature and display "
        "are controls so their volume is not credited to the price cut.",
        "top = df.groupby('category')['units'].sum().idxmax()\nres = el_mod.fit(df[df['category'] == top])\n"
        "print(top, '- R2', round(res.rsquared, 3), '- rows', int(res.nobs))\n"
        "pd.DataFrame({'coef': res.params, 'ci_low': res.conf_int()[0], 'ci_high': res.conf_int()[1], 'p': res.pvalues})"
        ".loc[['log_price', 'feature', 'display', 'trend']].round(3)",
        "md:## All segments (business rule BR-06 decides what is published)",
        "e = pd.read_csv('data/output/elasticity.csv')\n"
        "e[e['level'].isin(['All', 'Category', 'Brand'])][['level', 'segment', 'n_obs', 'elasticity', 'ci_low', 'ci_high', "
        "'status', 'status_reason']]",
        "md:## Sanity checks\nA positive and significant elasticity is suspicious: it goes to review, never to the simulator.",
        "e.groupby(['level', 'status']).size().unstack(fill_value=0)",
        "md:## Regular price vs promotion price cut, and cross-elasticities",
        "pd.read_csv('data/output/elasticity_split.csv')",
        "pd.read_csv('data/output/cross_elasticity.csv')",
    ],
    "03_promotions.ipynb": [
        "md:# 3 · Promotion effectiveness\n- **Baseline** (BR-03): average units of clean non-promo weeks within ±8 weeks.\n"
        "- **Uplift** = units / baseline - 1.\n- **ROI** = (profit with promo - profit without) / discount cost, at an "
        "**ASSUMED** 30% margin (BR-09).",
        SETUP,
        "md:## Worked example (acceptance criterion AC-03.2)",
        "m, base, price, units, baseline = 0.30, 4.00, 3.00, 100, 40\nc = base * (1 - m)\n"
        "net = units * (price - c) - baseline * (base - c)\ncost = (base - price) * units\n"
        "print(f'net incremental profit = {net:.2f}, discount cost = {cost:.2f}, ROI = {net / cost:.0%}')",
        "md:## By mechanic, at three margin assumptions",
        "summ = pd.read_csv('data/output/promo_summary.csv')\n"
        "summ.pivot_table(index='promo_type', columns='margin_assumption', values='roi').round(3)",
        "md:## By brand and mechanic (30% margin)",
        "pd.read_csv('data/output/promo_effectiveness.csv')[['category', 'manufacturer', 'promo_type', 'promo_weeks', "
        "'avg_discount', 'uplift', 'roi', 'share_weeks_paid_back']]",
        "md:## Post-promotion dip and cannibalisation",
        "pd.read_csv('data/output/promo_dip.csv')",
        "pd.read_csv('data/output/cannibalisation.csv')",
    ],
    "04_simulator.ipynb": [
        "md:# 4 · Scenario simulator\nVolume = (1+p)^e, revenue = (1+p)^(1+e), gross profit = (1+p)^e·(m+p)/m. "
        "Ranges come from the 95% interval of e. Only published elasticities, ±10% max (BR-10).",
        SETUP,
        "from simulator import simulate, classify\nvol, rev, prof = simulate(-1.5, 0.05)\n"
        "print(f'e=-1.5, +5%: volume {vol:+.2%}, revenue {rev:+.2%}, gross profit {prof:+.2%}')",
        "md:## Why the threshold is 1/m\nGross profit rises with a small price increase while |e| < 1/m "
        "(3.3 at a 30% margin); revenue rises only while |e| < 1.",
        "pd.DataFrame([(e, *simulate(e, 0.05)) for e in [-0.5, -1.0, -2.0, -3.0, -3.5, -4.0]],\n"
        "             columns=['elasticity', 'volume', 'revenue', 'gross_profit']).round(3)",
        "md:## +5% on every published brand",
        "g = pd.read_csv('data/output/scenario_grid.csv')\n"
        "g[(g['price_change'].round(2) == 0.05) & (g['level'] == 'Brand')][['segment', 'volume_pct', 'volume_pct_low', "
        "'volume_pct_high', 'revenue_pct', 'profit_pct', 'profit_delta']].round(3)",
        "md:## Pricing stance (BR-11)",
        "pd.read_csv('data/output/pricing_stance.csv')",
        "md:## Price-pack opportunities",
        "pd.read_csv('data/output/ppa.csv')[['category', 'manufacturer', 'description', 'size_oz', 'base_price_per_oz', "
        "'price_index_per_oz', 'elasticity', 'opportunity']]",
    ],
}

if __name__ == "__main__":
    Path("notebooks").mkdir(exist_ok=True)
    for name, cells in NOTEBOOKS.items():
        nbf.write(nb(cells), Path("notebooks") / name)
    print("notebooks:", list(NOTEBOOKS))
