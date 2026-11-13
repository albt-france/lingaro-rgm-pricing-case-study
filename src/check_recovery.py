"""Test T5 - does the elasticity model recover KNOWN elasticities?

Runs only on the SIMULATED sample (src/make_sample_data.py), where each product's true
elasticity is set by us. If the model is right, the 95% interval should contain the truth.

Usage (after running the pipeline with RETAIL_ZIP=data/sample/sample_breakfast.zip):
    python src/check_recovery.py
"""
from pathlib import Path

import pandas as pd

TRUE = {1001: -1.6, 1002: -1.4, 1003: -1.9, 1004: -1.2, 2001: -0.9, 2002: -0.7,
        3001: -1.1, 3002: -1.0, 4001: -0.6, 4002: -0.7}   # same values as make_sample_data.py

el = pd.read_csv("data/output/elasticity.csv")
prod = el[el["level"] == "Product"].copy()
prod["true"] = prod["upc"].astype(int).map(TRUE)
prod["inside_ci"] = (prod["ci_low"] <= prod["true"]) & (prod["true"] <= prod["ci_high"])
prod["error"] = prod["elasticity"] - prod["true"]
print(prod[["segment", "true", "elasticity", "ci_low", "ci_high", "inside_ci"]].to_string(index=False))
print(f"\nT5: {prod['inside_ci'].sum()}/{len(prod)} true values inside the 95% CI, "
      f"mean absolute error {prod['error'].abs().mean():.3f}")
prod[["segment", "true", "elasticity", "ci_low", "ci_high", "inside_ci", "error"]].to_csv(
    Path("data/output/recovery_test_sample.csv"), index=False)
