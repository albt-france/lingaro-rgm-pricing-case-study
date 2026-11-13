# Assumptions

Everything in this case study that is **assumed or simulated** rather than observed.

## A. Assumptions used on real data
| ID | Assumption | Value | Why | Where it is used | Sensitivity shown |
|---|---|---|---|---|---|
| A1 | Gross margin at regular price, for whoever funds the discount | **30%** | Margins are not in the data. 30% is a round, mid-range figure for packaged food, used for illustration only. | Promotion ROI, simulator profit | 20 / 30 / 40% in `promo_summary.csv`; slicer from 20% to 45% in Power BI |
| A2 | Baseline window | ±8 weeks, ≥ 4 clean weeks | Long enough to average out noise, short enough to follow seasonality | Baseline, uplift, ROI | - |
| A3 | Weeks excluded after a promotion | 2 | Those weeks can be depressed by stock-up | Baseline | - |
| A4 | Promotion price-cut threshold | 5% below base price | Smaller gaps are rounding or price noise | Promotion flag | - |
| A5 | Feature and display fees | **not included** | Not in the data | ROI of feature and display is optimistic | stated in the report (p.5) and on Power BI page 2 |
| A6 | Constant elasticity within ±10% | log-log model | Standard first-order approach; not trusted further from observed prices | Simulator | 95% range on every output |
| A7 | No competitor or retailer reaction | - | Out of scope | Simulator | stated in the report (p.7) and on Power BI page 4 |
| A8 | Market = US state of the store | - | The dataset has no countries; states play the role of markets to demonstrate the template | Report p.9, Power BI page 6 | - |

## B. SIMULATED external market data (`src/simulate_market.py`, seed 42)
The data imitates what a NielsenIQ / Circana feed would bring. **It is not real.**

| ID | Parameter | Value | Meaning |
|---|---|---|---|
| S1 | Retailer share of the regional market | 8% | Total market value = retailer category sales / 0.08 |
| S2 | Brand distortion (log-normal, sd) | 0.25 | How differently a brand sells outside this retailer |
| S3 | Competitor price offset by brand (normal, sd) | 6% | Gap between competitor and retailer prices |
| S4 | Quarterly price noise (normal, sd) | 2% | Movement of competitor prices from quarter to quarter |
| S5 | Numeric distribution | real share of the retailer's stores selling the brand x U(0.85, 1.00) | Anchored on real listings |
| S6 | Weighted distribution | numeric distribution + U(0, 0.08), capped at 100% | Leaders sit in the bigger stores |

Calibration: the brand split starts from the brand's **real** revenue share inside the retailer, quarter by quarter. Private label is treated like any other brand, although in reality it is sold only by this retailer.

## C. SIMULATED test sample (`src/make_sample_data.py`, seed 42)
- Same layout as the dunnhumby workbook: 10 products, 12 stores, 156 weeks.
- Known elasticities from -0.6 to -1.9.
- Random features (8%), displays (8%) and TPRs (12%), with 10-35% discounts.
- Used for two things:
  1. running the pipeline without the licensed data;
  2. checking that the model recovers known elasticities (TEST_PLAN T5).
