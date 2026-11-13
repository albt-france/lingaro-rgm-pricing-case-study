# Retail data (not included)

The dunnhumby terms of use do not allow redistribution, so the raw data is not in this repository.

1. Download *Breakfast at the Frat: A Time Series Analysis* (free form) from https://www.dunnhumby.com/source-files/
2. Put the file `dunnhumby_Breakfast-at-the-Frat.zip` here, without unzipping it.
3. Run the pipeline from the repository root (see the main README).

No download? Run everything on the SIMULATED sample instead (same layout, made-up numbers):
```bash
python src/make_sample_data.py
RETAIL_ZIP=data/sample/sample_breakfast.zip python src/prepare.py
```
