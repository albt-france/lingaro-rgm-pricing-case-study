"""Build a SMALL, SIMULATED workbook with the same layout as the dunnhumby file.

Why: the real dunnhumby data cannot be redistributed. This sample lets anyone run the whole
pipeline (prepare -> SQL -> models -> report) right after cloning the repository.
Every number in it is random (seed 42). It is NOT dunnhumby data and the results it gives
mean nothing commercially.

Usage:  python src/make_sample_data.py      -> data/sample/sample_breakfast.zip
        set RETAIL_ZIP=data/sample/sample_breakfast.zip   then run the pipeline
"""
import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
OUT = Path("data/sample")

products = pd.DataFrame([
    # upc, description, manufacturer, category, sub_category, size, base price, elasticity
    (1001, "SAMPLE TOASTED OATS", "BRAND A", "COLD CEREAL", "ALL FAMILY CEREAL", "12 OZ", 3.49, -1.6),
    (1002, "SAMPLE TOASTED OATS", "BRAND A", "COLD CEREAL", "ALL FAMILY CEREAL", "20 OZ", 4.99, -1.4),
    (1003, "SAMPLE HONEY FLAKES", "BRAND B", "COLD CEREAL", "ADULT CEREAL", "15 OZ", 3.79, -1.9),
    (1004, "PL CORN FLAKES", "PRIVATE LABEL", "COLD CEREAL", "ALL FAMILY CEREAL", "18 OZ", 2.29, -1.2),
    (2001, "SAMPLE PRETZEL TWISTS", "BRAND C", "BAG SNACKS", "PRETZELS", "16 OZ", 2.99, -0.9),
    (2002, "PL PRETZEL STICKS", "PRIVATE LABEL", "BAG SNACKS", "PRETZELS", "16 OZ", 1.79, -0.7),
    (3001, "SAMPLE PEPPERONI PIZZA", "BRAND D", "FROZEN PIZZA", "PIZZA/PREMIUM", "29 OZ", 6.49, -1.1),
    (3002, "SAMPLE CHEESE PIZZA", "BRAND D", "FROZEN PIZZA", "PIZZA/PREMIUM", "21 OZ", 5.49, -1.0),
    (4001, "SAMPLE MINT MOUTHWASH", "BRAND E", "ORAL HYGIENE PRODUCTS", "MOUTHWASHES (ANTISEPTIC)", "1 LT", 4.99, -0.6),
    (4002, "SAMPLE MINT MOUTHWASH", "BRAND E", "ORAL HYGIENE PRODUCTS", "MOUTHWASHES (ANTISEPTIC)", "500 ML", 3.29, -0.7),
], columns=["UPC", "DESCRIPTION", "MANUFACTURER", "CATEGORY", "SUB_CATEGORY", "PRODUCT_SIZE", "_base", "_elast"])

stores = pd.DataFrame({
    "STORE_ID": range(1, 13),
    "STORE_NAME": [f"SAMPLE STORE {i}" for i in range(1, 13)],
    "ADDRESS_CITY_NAME": ["CITY"] * 12,
    "ADDRESS_STATE_PROV_CODE": ["OH"] * 5 + ["TX"] * 4 + ["KY"] * 3,
    "MSA_CODE": [0] * 12,
    "SEG_VALUE_NAME": ["MAINSTREAM", "UPSCALE", "VALUE"] * 4,
    "PARKING_SPACE_QTY": [300] * 12,
    "SALES_AREA_SIZE_NUM": rng.integers(20000, 60000, 12),
    "AVG_WEEKLY_BASKETS": rng.integers(10000, 30000, 12),
})

weeks = pd.date_range("2009-01-14", periods=156, freq="7D")
rows = []
for _, p in products.iterrows():
    for s in stores["STORE_ID"]:
        scale = rng.uniform(5, 40)
        for i, w in enumerate(weeks):
            feature, display = int(rng.random() < 0.08), int(rng.random() < 0.08)
            tpr = int(rng.random() < 0.12)
            disc = rng.uniform(0.1, 0.35) if (tpr or feature) else 0.0
            price = round(p["_base"] * (1 - disc), 2)
            season = 1 + 0.1 * np.sin(2 * np.pi * i / 52)
            mu = scale * season * (price / p["_base"]) ** p["_elast"] * (1.3 if feature else 1) * (1.2 if display else 1)
            units = int(rng.poisson(mu))
            if units == 0:
                continue
            rows.append((w, s, p["UPC"], units, units, units, round(units * price, 2), price, p["_base"],
                         feature, display, int(tpr and not feature and not display)))
tx = pd.DataFrame(rows, columns=["WEEK_END_DATE", "STORE_NUM", "UPC", "UNITS", "VISITS", "HHS", "SPEND",
                                 "PRICE", "BASE_PRICE", "FEATURE", "DISPLAY", "TPR_ONLY"])

OUT.mkdir(parents=True, exist_ok=True)
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as xw:
    tx.to_excel(xw, sheet_name="dh Transaction Data", index=False)
    products.drop(columns=["_base", "_elast"]).to_excel(xw, sheet_name="dh Products Lookup", index=False)
    stores.to_excel(xw, sheet_name="dh Store Lookup", index=False)
with zipfile.ZipFile(OUT / "sample_breakfast.zip", "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("SIMULATED_sample_breakfast.xlsx", buf.getvalue())
print("SIMULATED sample written:", OUT / "sample_breakfast.zip", len(tx), "rows")
