"""Step 8 - collect every number quoted in the report titles into data/output/findings.json.

Rule: no number is typed by hand in the PDF, the Power BI page titles or the README tables;
they all come from this file, which is computed from the outputs of the previous steps.

Usage:  python src/findings.py
"""
import json
from pathlib import Path

import pandas as pd

OUT, CLEAN, PUB = Path("data/output"), Path("data/clean"), Path("data/public")
MARGIN = 0.30


def main():
    f = {}
    s = pd.read_csv(CLEAN / "sales_promo_weekly.csv", parse_dates=["week_end_date"])
    p = pd.read_csv(CLEAN / "products.csv")
    st = pd.read_csv(CLEAN / "stores.csv")
    s = s.merge(p[["upc", "category", "manufacturer"]], on="upc")
    last = s["week_end_date"].max()
    l52 = s[s["week_end_date"] > last - pd.Timedelta(weeks=52)]
    f["data"] = dict(rows=len(s), weeks=int(s["week_end_date"].nunique()), stores=int(s["store_id"].nunique()),
                     products=int(s["upc"].nunique()), categories=int(s["category"].nunique()),
                     manufacturers=int(s["manufacturer"].nunique()), first_week=str(s["week_end_date"].min().date()),
                     last_week=str(last.date()), states=sorted(st["state"].dropna().unique().tolist()),
                     revenue_l52w=float(l52["spend"].sum()), units_l52w=float(l52["units"].sum()),
                     promo_revenue_share=float(s.loc[s["is_promo"] == 1, "spend"].sum() / s["spend"].sum()),
                     dq_ok_share=float(s["dq_ok"].mean()))

    el = pd.read_csv(OUT / "elasticity.csv")
    cat = el[el["level"] == "Category"].sort_values("elasticity")
    f["elasticity"] = dict(
        pooled=el.loc[el["level"] == "All", ["elasticity", "ci_low", "ci_high"]].iloc[0].to_dict(),
        categories=cat[["segment", "elasticity", "ci_low", "ci_high", "n_obs", "status"]].to_dict("records"),
        most_elastic=cat.iloc[0]["segment"], least_elastic=cat.iloc[-1]["segment"],
        published=el[el["level"].isin(["Category", "Brand", "Product"])].groupby("status").size().to_dict(),
        positive_sign=int(((el["elasticity"] > 0) & el["level"].isin(["Brand", "Product"])).sum()),
        n_segments=int(el["level"].isin(["Category", "Brand", "Product"]).sum()))
    sp = pd.read_csv(OUT / "elasticity_split.csv")
    f["elasticity"]["split"] = sp.to_dict("records")
    ce = pd.read_csv(OUT / "cross_elasticity.csv")
    f["elasticity"]["cross_substitutes"] = int((ce["reading"] == "substitute").sum()) if len(ce) else 0
    f["elasticity"]["cross_tested"] = int(len(ce))

    summ = pd.read_csv(OUT / "promo_summary.csv")
    eff = pd.read_csv(OUT / "promo_effectiveness.csv")
    pt = eff.groupby("promo_type").agg(promo_weeks=("promo_weeks", "sum"), units=("units", "sum"),
                                       baseline_units=("baseline_units", "sum"), discount_cost=("discount_cost", "sum"),
                                       net_incr_profit=("net_incr_profit", "sum"), avg_discount=("avg_discount", "mean"))
    pt["uplift"] = pt["units"] / pt["baseline_units"] - 1
    pt["roi"] = pt["net_incr_profit"] / pt["discount_cost"].where(pt["discount_cost"] > 0)
    f["promo"] = dict(by_type=pt.reset_index().to_dict("records"),
                      best_uplift_type=pt["uplift"].idxmax(), best_uplift=float(pt["uplift"].max()),
                      tpr_uplift=float(pt.loc["TPR only", "uplift"]) if "TPR only" in pt.index else None,
                      tpr_roi=float(pt.loc["TPR only", "roi"]) if "TPR only" in pt.index else None,
                      brand_mechanics=int(len(eff)),
                      brand_mechanics_paying_back=int((eff["net_incr_profit"] > 0).sum()),
                      net_profit_total=float(eff["net_incr_profit"].sum()),
                      discount_cost_total=float(eff["discount_cost"].sum()),
                      sensitivity=summ.groupby("margin_assumption").apply(
                          lambda x: float(x["net_incr_profit"].sum() / x["discount_cost"].sum()),
                          include_groups=False).to_dict())
    dip = pd.read_csv(OUT / "promo_dip.csv")
    f["promo"]["dip"] = dip[["category", "dip"]].to_dict("records")
    f["promo"]["dip_avg"] = float(dip["units"].sum() / dip["baseline_units"].sum() - 1)
    can = pd.read_csv(OUT / "cannibalisation.csv")
    f["promo"]["cannibalisation"] = can.to_dict("records")

    ppa = pd.read_csv(OUT / "ppa.csv")
    f["ppa"] = dict(products=int(len(ppa)), inversions=int((ppa["inverted_vs"].fillna("") != "").sum()),
                    price_up=int(ppa["opportunity"].str.startswith("Price up").sum()),
                    sensitive=int(ppa["opportunity"].str.startswith("Sensitive").sum()),
                    worst_inversion=(ppa.sort_values("inversion_premium", ascending=False)
                                     [["description", "inverted_vs", "inversion_premium"]].head(1)
                                     .to_dict("records")))

    grid = pd.read_csv(OUT / "scenario_grid.csv")
    brands = el[(el["level"] == "Brand") & (el["status"] == "Published")].sort_values("base_revenue_52w", ascending=False)
    if len(brands):
        top = brands.iloc[0]
        g = grid[(grid["segment_id"] == top["segment_id"]) & (grid["price_change"].round(2) == 0.05)].iloc[0]
        f["simulator"] = dict(segment=top["segment"], elasticity=float(top["elasticity"]),
                              ci=[float(top["ci_low"]), float(top["ci_high"])],
                              base_revenue=float(top["base_revenue_52w"]),
                              **{k: float(g[k]) for k in ["volume_pct", "volume_pct_low", "volume_pct_high",
                                                          "revenue_pct", "revenue_pct_low", "revenue_pct_high",
                                                          "profit_pct", "profit_pct_low", "profit_pct_high",
                                                          "revenue_delta", "profit_delta"]})
    stance = pd.read_csv(OUT / "pricing_stance.csv")
    f["simulator"]["stances"] = stance[stance["level"] == "Brand"]["stance"].value_counts().to_dict()
    low = stance[(stance["level"] == "Brand") & stance["stance"].str.startswith("Low sensitivity:")]
    f["simulator"]["low_sensitivity_brands"] = low.sort_values("elasticity", ascending=False)["segment"].tolist()
    f["promo"]["cannibalisation_avg"] = float(
        can.loc[can["context"].str.startswith("Another"), "units"].sum()
        / can.loc[can["context"].str.startswith("Another"), "baseline_units"].sum() - 1)

    # data quality facts quoted in the report
    st = pd.read_csv(CLEAN / "stores.csv")
    prod = pd.read_csv(CLEAN / "products.csv")
    sold = pd.read_csv(CLEAN / "sales_weekly.csv", usecols=["upc"])["upc"].unique()
    po = prod[prod["phase_out"].eq(1) & prod["upc"].isin(sold)]
    f["data"]["duplicate_stores"] = int(st.get("dq_duplicate_record", pd.Series(dtype=int)).sum())
    f["data"]["phase_out_brands"] = sorted(po["manufacturer"].unique().tolist())
    f["data"]["phase_out_products"] = int(len(po))

    mk = el[el["level"] == "Market"].copy()
    piv = mk.pivot_table(index="category", columns="market", values="elasticity")
    f["markets"] = dict(table=mk[["market", "category", "elasticity", "ci_low", "ci_high", "n_obs", "status"]]
                        .to_dict("records"),
                        spread=(piv.max(axis=1) - piv.min(axis=1)).round(2).to_dict(),
                        published=int((mk["status"] == "Published").sum()), segments=int(len(mk)))
    pubmk = mk[mk["status"] == "Published"].pivot_table(index="category", columns="market", values="elasticity")
    pubmk = pubmk.dropna()
    f["markets"]["published_markets"] = list(pubmk.columns)
    f["markets"]["unpublished_markets"] = sorted(set(mk["market"].dropna()) - set(pubmk.columns))
    f["markets"]["more_sensitive_everywhere"] = next(
        (m for m in pubmk.columns if len(pubmk.columns) > 1 and (pubmk[m] <= pubmk.min(axis=1)).all()), None)
    f["markets"]["n_categories"] = int(len(pubmk))

    ms = pd.read_csv(OUT / "market_sim.csv")
    lastq = ms[ms["quarter"] == ms["quarter"].max()]
    f["market_sim"] = dict(quarter=str(ms["quarter"].max()),
                           most_expensive=lastq.sort_values("price_index_vs_competitors").iloc[-1][
                               ["brand_key", "price_index_vs_competitors"]].to_dict(),
                           share_gap_max=lastq.assign(g=lastq["retailer_value_share"] - lastq["market_value_share"])
                           .sort_values("g").iloc[-1][["brand_key", "retailer_value_share", "market_value_share"]].to_dict())

    h = pd.read_csv(PUB / "hicp_annual.csv")
    eu = h[(h["geo"] == "EU27_2020")]
    food = eu[eu["coicop"] == "CP011"].set_index("year")
    allit = eu[eu["coicop"] == "CP00"].set_index("year")
    f["eurostat"] = dict(food_2022=float(food.loc[2022, "rate_pct"]), food_2023=float(food.loc[2023, "rate_pct"]),
                         food_2025=float(food.loc[2025, "rate_pct"]),
                         food_cum_2020_2025=float(food.loc[2025, "index_2015"] / food.loc[2020, "index_2015"] - 1),
                         all_cum_2020_2025=float(allit.loc[2025, "index_2015"] / allit.loc[2020, "index_2015"] - 1))

    (OUT / "findings.json").write_text(json.dumps(f, indent=2, default=float), encoding="utf-8")
    print(json.dumps({k: f[k] for k in ["data", "eurostat"]}, indent=1, default=float))
    print("category elasticities:", [(c["segment"], c["elasticity"]) for c in f["elasticity"]["categories"]])
    print("promo:", {k: v for k, v in f["promo"].items() if k not in ("by_type", "dip", "cannibalisation")})
    print("simulator:", f.get("simulator"))


if __name__ == "__main__":
    main()
