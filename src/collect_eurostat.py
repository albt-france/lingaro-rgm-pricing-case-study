"""Download Eurostat HICP (Harmonised Index of Consumer Prices) series used on the
'Why pricing matters now' page.

Source: Eurostat dissemination API (JSON-stat 2.0), datasets
  - prc_hicp_aind : annual average index (2015 = 100) and annual average rate of change
  - prc_hicp_manr : monthly annual rate of change
Licence: Eurostat re-use policy (CC BY 4.0), see data/SOURCES.md.

Output (tidy CSV):
  data/raw/eurostat/*.json        raw API answers (dated)
  data/public/hicp_annual.csv     geo, coicop, year, index_2015, rate_pct
  data/public/hicp_monthly_food.csv  geo, month, rate_pct

Usage:  python src/collect_eurostat.py
"""
import datetime as dt
import itertools
import json
from pathlib import Path

import pandas as pd
import requests

API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
GEOS = ["EU27_2020", "DE", "FR", "IT", "ES", "PL", "NL"]
# COICOP codes: all items, food, bread & cereals, sugar/jam/confectionery, personal-care products
COICOPS = {"CP00": "All items", "CP011": "Food", "CP0111": "Bread and cereals",
           "CP0118": "Sugar, jam, honey, chocolate and confectionery",
           "CP1213": "Personal care products"}
RAW = Path("data/raw/eurostat")
PUB = Path("data/public")


def get(dataset, params):
    """Call the API and return (json, url). Params is a list of (key, value) pairs."""
    r = requests.get(API + dataset, params=[("format", "JSON"), ("lang", "EN")] + params, timeout=60)
    r.raise_for_status()
    return r.json()


def to_frame(js):
    """Flatten a JSON-stat 2.0 answer into a long DataFrame (one row per cell)."""
    dims = js["id"]
    cats = []
    for d in dims:
        idx = js["dimension"][d]["category"]["index"]
        cats.append(sorted(idx, key=idx.get))  # codes in position order
    rows = []
    for pos, combo in enumerate(itertools.product(*cats)):
        v = js["value"].get(str(pos))
        if v is not None:
            rows.append(dict(zip(dims, combo), value=v))
    return pd.DataFrame(rows)


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    PUB.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()

    base = [("geo", g) for g in GEOS] + [("coicop", c) for c in COICOPS] + [("sinceTimePeriod", "2019")]
    frames = []
    for unit in ["INX_A_AVG", "RCH_A_AVG"]:
        js = get("prc_hicp_aind", base + [("unit", unit)])
        (RAW / f"prc_hicp_aind_{unit}_{today}.json").write_text(json.dumps(js), encoding="utf-8")
        frames.append(to_frame(js))
    annual = pd.concat(frames)
    annual = (annual.pivot_table(index=["geo", "coicop", "time"], columns="unit", values="value")
              .reset_index().rename(columns={"time": "year", "INX_A_AVG": "index_2015", "RCH_A_AVG": "rate_pct"}))
    annual["coicop_label"] = annual["coicop"].map(COICOPS)
    annual["year"] = annual["year"].astype(int)
    annual.to_csv(PUB / "hicp_annual.csv", index=False)

    js = get("prc_hicp_manr", [("geo", g) for g in GEOS] + [("coicop", "CP011"), ("coicop", "CP00"),
                                                              ("sinceTimePeriod", "2019-01")])
    (RAW / f"prc_hicp_manr_{today}.json").write_text(json.dumps(js), encoding="utf-8")
    monthly = to_frame(js).rename(columns={"time": "month", "value": "rate_pct"})
    monthly = monthly[["geo", "coicop", "month", "rate_pct"]]
    monthly.to_csv(PUB / "hicp_monthly.csv", index=False)
    print(annual.query("geo == 'EU27_2020'").to_string(index=False))
    print(monthly.tail(3))


if __name__ == "__main__":
    main()
