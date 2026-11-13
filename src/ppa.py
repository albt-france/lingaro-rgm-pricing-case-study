"""Step 6 - price-pack architecture (PPA): is the price per ounce consistent across pack sizes?

Input : data/output/ppa_products.csv  (sql/04_price_per_unit.sql: regular price per ounce by product)
        data/output/elasticity.csv     (product-level elasticities)
Output: data/output/ppa.csv            one row per product with ladder checks and an opportunity flag

Checks (business rule BR-08):
  - price index per oz = product price per oz / sub-category average price per oz (100 = average)
  - inverted ladder    = a bigger pack of the same manufacturer and sub-category costs MORE per oz
  - opportunity        = combines the ladder check with the product's price sensitivity

Usage:  python src/ppa.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("data/output")


def main():
    ppa = pd.read_csv(OUT / "ppa_products.csv")
    el = pd.read_csv(OUT / "elasticity.csv")
    prod_el = el[el["level"] == "Product"][["upc", "elasticity", "ci_low", "ci_high", "status"]]
    ppa = ppa.merge(prod_el, on="upc", how="left")

    # price index per oz vs the sub-category average (units-weighted)
    avg = (ppa.assign(w=ppa["base_price_per_oz"] * ppa["units"]).groupby("sub_category")
              .agg(w=("w", "sum"), u=("units", "sum")))
    ppa = ppa.join((avg["w"] / avg["u"]).rename("subcat_price_per_oz"), on="sub_category")
    ppa["price_index_per_oz"] = (100 * ppa["base_price_per_oz"] / ppa["subcat_price_per_oz"]).round(1)

    # inverted ladder: compare every pack with the smaller packs of the same manufacturer and sub-category
    ppa["inverted_vs"] = ""
    ppa["inversion_premium"] = np.nan
    for _, g in ppa.groupby(["sub_category", "manufacturer"]):
        for i, big in g.iterrows():
            smaller = g[(g["size_oz"] < big["size_oz"]) & (g["base_price_per_oz"] < big["base_price_per_oz"])]
            if len(smaller):
                worst = smaller.loc[(big["base_price_per_oz"] / smaller["base_price_per_oz"]).idxmax()]
                ppa.loc[i, "inverted_vs"] = worst["description"]
                ppa.loc[i, "inversion_premium"] = round(big["base_price_per_oz"] / worst["base_price_per_oz"] - 1, 3)

    def opportunity(r):
        if r["inverted_vs"]:
            return "Fix ladder: bigger pack costs more per oz"
        if r["status"] == "Published" and r["ci_low"] > -1 and r["price_index_per_oz"] < 100:
            return "Price up candidate: low sensitivity, below-average price per oz"
        if r["status"] == "Published" and r["elasticity"] < -2.5:
            return "Sensitive: hold price, use targeted promotions"
        return "No action"

    ppa["opportunity"] = ppa.apply(opportunity, axis=1)
    ppa = ppa.sort_values(["category", "sub_category", "manufacturer", "size_oz"])
    ppa.to_csv(OUT / "ppa.csv", index=False)
    print(ppa[["category", "manufacturer", "description", "size_oz", "base_price_per_oz", "price_index_per_oz",
               "elasticity", "opportunity"]].to_string(index=False))


if __name__ == "__main__":
    main()
