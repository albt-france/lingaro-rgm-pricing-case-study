"""Step 1 - load the dunnhumby 'Breakfast at the Frat' archive and write clean tables.

Input : data/raw/retail/dunnhumby_Breakfast-at-the-Frat.zip  (download it yourself, see README)
        The archive holds one Excel workbook with three sheets:
          - transactions : one row per week x store x product (UPC)
          - products     : UPC -> description, manufacturer, category, sub-category, size
          - stores       : store -> city, state, segment, size
Output: data/clean/sales_weekly.csv, products.csv, stores.csv   (local only: raw-derived rows)

What this script does, in plain words:
  1. find the workbook inside the zip and read the three sheets (header row detected automatically);
  2. rename columns to snake_case, fix types;
  3. parse the pack size ("12.25 OZ", "1 LT") into ounces so price per ounce can be compared;
  4. tag every row with its promotion type (feature / display / TPR) and discount depth;
  5. add simple quality flags (missing price, price above base price, extreme price).

Usage:  python src/prepare.py
"""
import io
import os
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ZIP = Path(os.environ.get("RETAIL_ZIP", "data/raw/retail/dunnhumby_Breakfast-at-the-Frat.zip"))
RAW_DIR = Path("data/raw/retail")
CLEAN = Path("data/clean")

ML_PER_FL_OZ = 29.5735


def find_workbook():
    """Return (name, bytes) of the Excel workbook, from the zip or from an already-unzipped file."""
    if ZIP.exists():
        with zipfile.ZipFile(ZIP) as z:
            names = [n for n in z.namelist() if n.lower().endswith((".xlsx", ".xls"))]
            if not names:
                raise SystemExit(f"No Excel file inside {ZIP}: {z.namelist()}")
            return names[0], z.read(names[0])
    for p in RAW_DIR.rglob("*.xlsx"):
        return p.name, p.read_bytes()
    raise SystemExit(f"Dataset not found. Put the dunnhumby zip at {ZIP} (see README).")


def read_sheet(xls, keyword, must_have):
    """Read the sheet whose name contains `keyword`; the header is the first row containing `must_have`."""
    sheet = next(s for s in xls.sheet_names if keyword.lower() in s.lower())
    head = pd.read_excel(xls, sheet_name=sheet, header=None, nrows=15)
    header_row = next(i for i, row in head.iterrows()
                      if any(str(v).strip().upper() == must_have for v in row.values))
    df = pd.read_excel(xls, sheet_name=sheet, header=header_row)
    df.columns = [re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_") for c in df.columns]
    return df.dropna(how="all")


def size_to_oz(size):
    """'12.25 OZ' -> 12.25 ; '1 LT' -> 33.8 ; '500 ML' -> 16.9. Liquids are converted to fluid ounces."""
    if not isinstance(size, str):
        return np.nan, None
    m = re.match(r"\s*([\d.]+)\s*([A-Z]+)", size.upper())
    if not m:
        return np.nan, None
    qty, unit = float(m.group(1)), m.group(2)
    if unit in ("OZ", "Z"):
        return qty, "oz"
    if unit in ("LT", "L", "LTR"):
        return qty * 1000 / ML_PER_FL_OZ, "fl oz"
    if unit == "ML":
        return qty / ML_PER_FL_OZ, "fl oz"
    if unit in ("LB",):
        return qty * 16, "oz"
    if unit in ("CT",):
        return np.nan, "count"
    return np.nan, unit.lower()


def promo_type(row_feature, row_display, row_tpr):
    if row_feature and row_display:
        return "Feature + Display"
    if row_feature:
        return "Feature"
    if row_display:
        return "Display"
    if row_tpr:
        return "TPR only"
    return "No promo"


def main():
    CLEAN.mkdir(parents=True, exist_ok=True)
    name, blob = find_workbook()
    print("workbook:", name)
    xls = pd.ExcelFile(io.BytesIO(blob))
    print("sheets:", xls.sheet_names)

    tx = read_sheet(xls, "transaction", "UPC")
    products = read_sheet(xls, "product", "UPC")
    stores = read_sheet(xls, "store", "STORE_ID")
    print("raw rows:", len(tx), "products:", len(products), "stores:", len(stores))

    # ---------- products ----------
    products = products.rename(columns={"product_size": "size"})
    products["upc"] = products["upc"].astype("int64")
    parsed = products["size"].apply(size_to_oz)
    products["size_oz"] = [p[0] for p in parsed]
    products["size_unit"] = [p[1] for p in parsed]
    for c in ["description", "manufacturer", "category", "sub_category", "size"]:
        products[c] = products[c].astype(str).str.strip()
    products["category"] = products["category"].str.title()
    products["sub_category"] = products["sub_category"].str.title()
    products["manufacturer"] = products["manufacturer"].str.title()
    # the raw file truncates some manufacturer names: complete them for readable labels (BR-01)
    products["manufacturer"] = products["manufacturer"].replace(
        {"General Mi": "General Mills", "Snyder S": "Snyder's", "Tonys": "Tony's", "P & G": "P&G"})
    products["brand_key"] = products["category"] + " | " + products["manufacturer"]
    # readable product name: description + pack size (same description can exist in several sizes)
    products["product_name"] = products["description"].str.title() + " " + products["size"].str.lower()
    products["is_private_label"] = products["manufacturer"].str.contains("Private", case=False)

    # ---------- stores ----------
    stores = stores.rename(columns={"store_id": "store_id", "address_city_name": "city",
                                    "address_state_prov_code": "state", "seg_value_name": "segment",
                                    "sales_area_size_num": "sales_area_sqft",
                                    "avg_weekly_baskets": "avg_weekly_baskets"})
    stores["store_id"] = stores["store_id"].astype("int64")
    stores["segment"] = stores["segment"].astype(str).str.title()
    # The raw store lookup lists some stores twice with different segments (e.g. Mainstream and Upscale).
    # Joining on it would duplicate their sales, so keep the first record and flag the store (BR-07).
    dup_ids = stores.loc[stores["store_id"].duplicated(), "store_id"].unique()
    stores = stores.drop_duplicates("store_id", keep="first").copy()
    stores["dq_duplicate_record"] = stores["store_id"].isin(dup_ids).astype(int)
    print("stores listed more than once in the lookup (first record kept):", list(dup_ids))

    # ---------- weekly sales ----------
    tx = tx.rename(columns={"store_num": "store_id"})
    tx["week_end_date"] = pd.to_datetime(tx["week_end_date"]).dt.date
    for c in ["store_id", "upc"]:
        tx[c] = tx[c].astype("int64")
    for c in ["units", "visits", "hhs", "spend", "price", "base_price"]:
        tx[c] = pd.to_numeric(tx[c], errors="coerce")
    for c in ["feature", "display", "tpr_only"]:
        tx[c] = pd.to_numeric(tx[c], errors="coerce").fillna(0).astype(int)

    # Promotion tagging (business rule BR-02, see product/BUSINESS_RULES.md)
    tx["discount_pct"] = (1 - tx["price"] / tx["base_price"]).clip(lower=0).round(4)
    tx["is_price_cut"] = (tx["discount_pct"] >= 0.05).astype(int)
    tx["promo_type"] = [promo_type(f, d, t) for f, d, t in zip(tx["feature"], tx["display"], tx["tpr_only"])]
    tx["is_promo"] = ((tx["promo_type"] != "No promo") | (tx["is_price_cut"] == 1)).astype(int)

    # Quality flags (business rule BR-07): rows are kept but flagged; the models skip flagged rows
    med = tx.groupby("upc")["price"].transform("median")
    tx["dq_missing_price"] = (tx["price"].isna() | tx["base_price"].isna() | (tx["price"] <= 0)).astype(int)
    tx["dq_price_above_base"] = (tx["price"] > tx["base_price"] * 1.05).astype(int)
    tx["dq_extreme_price"] = ((tx["price"] > 3 * med) | (tx["price"] < med / 3)).astype(int)
    tx["dq_zero_units"] = (tx["units"] <= 0).astype(int)
    tx["dq_ok"] = (tx[[c for c in tx.columns if c.startswith("dq_") and c != "dq_ok"]].sum(axis=1) == 0).astype(int)

    # attach market (state) for convenience
    tx = tx.merge(stores[["store_id", "state"]], on="store_id", how="left")
    tx["dq_unknown_store"] = tx["state"].isna().astype(int)

    # Phase-out (BR-07): units of the last 13 weeks below 25% of the product's normal 13-week volume.
    # Such products are leaving the shelf (delisting); their recent sales are not a valid base for pricing.
    wk = tx.groupby(["upc", "week_end_date"])["units"].sum().reset_index()
    last13 = sorted(wk["week_end_date"].unique())[-13:]
    normal = wk.groupby("upc")["units"].mean() * 13
    recent = wk[wk["week_end_date"].isin(last13)].groupby("upc")["units"].sum().reindex(normal.index, fill_value=0)
    products["phase_out"] = products["upc"].map((recent < 0.25 * normal).astype(int)).fillna(0).astype(int)
    print("phase-out products:", products.loc[products["phase_out"] == 1, "product_name"].tolist())

    cols = ["week_end_date", "store_id", "upc", "units", "visits", "hhs", "spend", "price", "base_price",
            "feature", "display", "tpr_only", "discount_pct", "is_price_cut", "promo_type", "is_promo",
            "dq_missing_price", "dq_price_above_base", "dq_extreme_price", "dq_zero_units", "dq_unknown_store",
            "dq_ok"]
    tx[cols].sort_values(["upc", "store_id", "week_end_date"]).to_csv(CLEAN / "sales_weekly.csv", index=False)
    products.to_csv(CLEAN / "products.csv", index=False)
    stores.to_csv(CLEAN / "stores.csv", index=False)

    print("weeks:", tx["week_end_date"].nunique(), tx["week_end_date"].min(), "->", tx["week_end_date"].max())
    print("stores in sales:", tx["store_id"].nunique(), " products in sales:", tx["upc"].nunique())
    print("rows flagged by quality checks:", int((tx["dq_ok"] == 0).sum()))
    print(tx["promo_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
