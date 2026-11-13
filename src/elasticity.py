"""Step 3 - price elasticity with a log-log regression (statsmodels).

Model (one regression per segment, on store x product x week rows):

    log(units) = e * log(price) + b1*feature + b2*display
                 + store x product effects + month effects + trend + error

  - e is the price elasticity: the % change in units for a 1% change in price, all else equal.
    e = -1.8 means: +1% price -> about -1.8% units (so revenue falls when price rises).
  - feature / display are controls: we do not want their volume to be credited to the price cut.
  - store x product effects give every product in every store its own normal sales level
    ("big SKU in a big store"); so e is learnt only from price moves over time inside the same
    store and product. One effect per pair, not store + product separately: the assortment differs
    by store (Texas stores carry 9 of the 15 snack products), and additive effects then mix
    "which products a store sells" with "how shoppers react to price".
  - month effects absorb seasonality; the trend absorbs slow growth or decline.
  - The pair effects are removed by demeaning ("within" estimator): every variable minus its
    store x product average. Same estimate as one dummy per pair, without a huge matrix.
  - Standard errors are clustered by store (weeks of the same store are not independent).

Caveat: this is an OBSERVATIONAL estimate (a correlation on historical data), not an experiment.
Prices were set by the retailer, often together with other actions we cannot see.

Outputs (data/output):
  elasticity.csv        one row per segment (category, brand, product, market x category)
  elasticity_split.csv  regular-price vs promo-depth elasticity per category
  cross_elasticity.csv  brand vs rest-of-category price, per category

Usage:  python src/elasticity.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

CLEAN, OUT = Path("data/clean"), Path("data/output")

# Business rule BR-06 - minimum evidence before an elasticity is published
MIN_OBS = 1000          # store x product x week rows
MIN_WEEKS = 52          # distinct weeks
MIN_PRICE_SD = 0.05     # std. dev. of log(price) inside the segment (about 5% price variation)
MAX_CI_WIDTH = 1.5      # width of the 95% interval
MIN_STORES = 5          # stores: errors are clustered by store, too few clusters make them unreliable
ALPHA = 0.05


def load():
    s = pd.read_csv(CLEAN / "sales_weekly.csv", parse_dates=["week_end_date"])
    p = pd.read_csv(CLEAN / "products.csv")
    st = pd.read_csv(CLEAN / "stores.csv")
    df = (s.merge(p[["upc", "category", "manufacturer", "brand_key", "product_name", "phase_out"]], on="upc")
           .merge(st[["store_id", "state", "segment"]], on="store_id", how="left"))
    df = df[df["dq_ok"] == 1].copy()
    df["log_units"] = np.log(df["units"])
    df["log_price"] = np.log(df["price"])
    df["log_base_price"] = np.log(df["base_price"])
    df["log_discount"] = np.log(df["price"] / df["base_price"])   # 0 when no price cut
    df["month"] = df["week_end_date"].dt.month
    first = df["week_end_date"].min()
    df["trend"] = (df["week_end_date"] - first).dt.days / 365.25
    return df


def last52_totals(d):
    """Revenue and volume of the last 52 weeks: the base the simulator applies % changes to."""
    cut = d["week_end_date"].max() - pd.Timedelta(weeks=52)
    r = d[d["week_end_date"] > cut]
    units, rev = r["units"].sum(), r["spend"].sum()
    return units, rev, rev / units if units else np.nan


def fit(d, price_terms="log_price"):
    """Fit the log-log model on rows d with store x product fixed effects (within estimator).

    Every variable is demeaned inside its store x product pair, then OLS runs without a constant.
    The pair effects are nested in the store clusters, so the clustered errors need no extra
    degrees-of-freedom correction. R-squared is the "within" R-squared (variation over time).
    """
    terms = [t.strip() for t in price_terms.split("+")]
    X = d[terms + ["feature", "display", "trend"]].astype(float)
    months = pd.get_dummies(d["month"], prefix="m", drop_first=True, dtype=float)
    X = pd.concat([X, months], axis=1)
    X = X.loc[:, X.std() > 0]                      # drop controls that never move in this segment
    pair = [d["store_id"], d["upc"]]
    y = d["log_units"] - d.groupby(pair)["log_units"].transform("mean")
    Xw = X - X.groupby(pair).transform("mean")
    return sm.OLS(y, Xw).fit(cov_type="cluster", cov_kwds={"groups": d["store_id"]})


def status(n_obs, n_weeks, price_sd, e, lo, hi, p):
    """Business rule BR-06 turned into code. Returns (status, reason)."""
    if n_obs < MIN_OBS or n_weeks < MIN_WEEKS:
        return "Insufficient data", f"needs >= {MIN_OBS} rows and >= {MIN_WEEKS} weeks"
    if price_sd < MIN_PRICE_SD:
        return "Insufficient data", "price barely moved"
    if e > 0 and p < ALPHA:
        return "Review", "positive and significant: check promotions, mix or data errors"
    if p >= ALPHA:
        return "Review", "not significantly different from zero"
    if hi - lo > MAX_CI_WIDTH:
        return "Review", "interval too wide"
    return "Published", ""


def plain_english(e, lo, hi):
    if e >= 0:
        return "No price sensitivity detected (see review note)."
    rev = "falls" if e < -1 else "rises"
    return (f"+1% price -> about {e:.1f}% units (95% CI {lo:.1f} to {hi:.1f}); "
            f"revenue {rev} when price goes up.")


def estimate(d, level, segment, **keys):
    n_obs, n_weeks = len(d), d["week_end_date"].nunique()
    price_sd = d.groupby("upc")["log_price"].std().mean() if len(d) else 0
    units52, rev52, price52 = last52_totals(d)
    row = dict(level=level, segment=segment, n_obs=n_obs, n_stores=d["store_id"].nunique(),
               n_products=d["upc"].nunique(), n_weeks=n_weeks, price_sd=round(float(price_sd or 0), 3),
               base_units_52w=units52, base_revenue_52w=round(rev52, 2), avg_price_52w=round(price52, 3), **keys)
    if n_obs < 200 or n_weeks < 26 or row["n_stores"] < MIN_STORES:
        why = "too few rows to fit" if row["n_stores"] >= MIN_STORES else f"fewer than {MIN_STORES} stores"
        row.update(elasticity=np.nan, se=np.nan, ci_low=np.nan, ci_high=np.nan, p_value=np.nan, r2=np.nan,
                   status="Insufficient data", status_reason=why, plain_english="")
        return row
    res = fit(d)
    e, se = res.params["log_price"], res.bse["log_price"]
    lo, hi = res.conf_int().loc["log_price"]
    p = res.pvalues["log_price"]
    st, why = status(n_obs, n_weeks, price_sd, e, lo, hi, p)
    if st == "Published" and level in ("Brand", "Product") and d["phase_out"].min() == 1:
        st, why = "Review", "phased out before the end of the data: recent sales are not a valid base"
    row.update(elasticity=round(e, 3), se=round(se, 3), ci_low=round(lo, 3), ci_high=round(hi, 3),
               p_value=round(p, 4), r2=round(res.rsquared, 3),
               feature_effect=round(np.exp(res.params.get("feature", 0)) - 1, 3),
               display_effect=round(np.exp(res.params.get("display", 0)) - 1, 3),
               status=st, status_reason=why, plain_english=plain_english(e, lo, hi))
    return row


def cross_elasticity(df):
    """Brand units vs own price and the average price of the rest of the category (same store-week).
    A positive cross coefficient means the brands are substitutes."""
    rows = []
    for cat, dc in df.groupby("category"):
        # brand x store x week: units and units-weighted average price
        g = (dc.assign(rev=dc["price"] * dc["units"])
               .groupby(["manufacturer", "store_id", "week_end_date"], as_index=False)
               .agg(units=("units", "sum"), rev=("rev", "sum"), feature=("feature", "max"), display=("display", "max")))
        g["price"] = g["rev"] / g["units"]
        tot = g.groupby(["store_id", "week_end_date"]).agg(cat_rev=("rev", "sum"), cat_units=("units", "sum"))
        g = g.join(tot, on=["store_id", "week_end_date"])
        g["other_units"] = g["cat_units"] - g["units"]
        g = g[g["other_units"] > 0].copy()
        g["other_price"] = (g["cat_rev"] - g["rev"]) / g["other_units"]
        g["month"] = g["week_end_date"].dt.month
        for brand, d in g.groupby("manufacturer"):
            if len(d) < MIN_OBS or d["week_end_date"].nunique() < MIN_WEEKS:
                continue
            res = smf.ols("np.log(units) ~ np.log(price) + np.log(other_price) + feature + display"
                          " + C(month) + C(store_id)", data=d).fit(
                cov_type="cluster", cov_kwds={"groups": d["store_id"]})
            k = "np.log(other_price)"
            lo, hi = res.conf_int().loc[k]
            rows.append(dict(category=cat, manufacturer=brand, n_obs=len(d),
                             own_elasticity=round(res.params["np.log(price)"], 3),
                             cross_elasticity=round(res.params[k], 3), ci_low=round(lo, 3), ci_high=round(hi, 3),
                             p_value=round(res.pvalues[k], 4),
                             reading=("substitute" if res.params[k] > 0 and res.pvalues[k] < ALPHA else
                                      "complement?" if res.params[k] < 0 and res.pvalues[k] < ALPHA else
                                      "no clear link")))
    return pd.DataFrame(rows)


def split_elasticity(df):
    """Regular (base) price elasticity vs promo-depth elasticity, per category.
    Promo elasticity is usually larger: shoppers stock up during short price cuts."""
    rows = []
    for cat, d in df.groupby("category"):
        # the regular price must move inside each product, otherwise there is nothing to learn from
        base_sd = d.groupby("upc")["log_base_price"].std().mean()
        if not base_sd >= 0.02:
            rows.append(dict(category=cat, component="Regular price", status="Insufficient data",
                             note="regular price barely moved", n_obs=len(d)))
            continue
        res = fit(d, "log_base_price + log_discount")
        for term, label in [("log_base_price", "Regular price"), ("log_discount", "Promo price cut")]:
            lo, hi = res.conf_int().loc[term]
            rows.append(dict(category=cat, component=label, elasticity=round(res.params[term], 3),
                             ci_low=round(lo, 3), ci_high=round(hi, 3), p_value=round(res.pvalues[term], 4),
                             n_obs=len(d), base_price_sd=round(base_sd, 3), status="Estimated", note=""))
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = load()
    rows = []
    rows.append(estimate(df, "All", "All categories (pooled)", category="All"))
    for cat, d in df.groupby("category"):
        rows.append(estimate(d, "Category", cat, category=cat))
        for brand, db in d.groupby("manufacturer"):
            rows.append(estimate(db, "Brand", f"{cat} | {brand}", category=cat, manufacturer=brand))
        for mkt, dm in d.groupby("state"):
            rows.append(estimate(dm, "Market", f"{mkt} | {cat}", category=cat, market=mkt))
    for (upc, name, cat, brand), d in df.groupby(["upc", "product_name", "category", "manufacturer"]):
        rows.append(estimate(d, "Product", name, category=cat, manufacturer=brand, upc=upc))
    el = pd.DataFrame(rows)
    el.insert(0, "segment_id", range(1, len(el) + 1))
    el.to_csv(OUT / "elasticity.csv", index=False)
    split_elasticity(df).to_csv(OUT / "elasticity_split.csv", index=False)
    cross_elasticity(df).to_csv(OUT / "cross_elasticity.csv", index=False)

    show = ["level", "segment", "n_obs", "elasticity", "ci_low", "ci_high", "status"]
    print(el[el["level"].isin(["All", "Category", "Brand"])][show].to_string(index=False))
    print(el.groupby(["level", "status"]).size().to_string())


if __name__ == "__main__":
    main()
