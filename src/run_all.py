"""Run the whole pipeline in order. Stops at the first error.

Usage:  python src/run_all.py            (real data: data/raw/retail/dunnhumby_Breakfast-at-the-Frat.zip)
        python src/run_all.py --sample   (SIMULATED sample with the same layout)
        python src/run_all.py --collect  (also refresh the public data: Lingaro facts snapshot, Eurostat)
"""
import os
import subprocess
import sys

STEPS = ["prepare", "run_sql", "elasticity", "promo", "simulator", "ppa", "simulate_market", "findings",
         "check_results", "build_tmdl", "build_measures_dictionary", "build_report_pages", "build_report", "build_dashboard",
         "build_notebooks"]

if __name__ == "__main__":
    env = dict(os.environ)
    if "--sample" in sys.argv:
        subprocess.run([sys.executable, "src/make_sample_data.py"], check=True)
        env["RETAIL_ZIP"] = "data/sample/sample_breakfast.zip"
    steps = (["collect_lingaro", "collect_eurostat"] if "--collect" in sys.argv else []) + STEPS
    for s in steps:
        print(f"\n===== {s} =====", flush=True)
        subprocess.run([sys.executable, f"src/{s}.py"], check=True, env=env)
