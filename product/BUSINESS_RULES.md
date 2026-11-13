# Business rules

Each rule has an ID, a plain-language statement, the exact definition used in code, and where it lives.
A rule changes only through a ticket that updates this file, the code and the test plan together.

| ID | Rule | Where |
|---|---|---|
| BR-01 | Product hierarchy | `src/prepare.py` |
| BR-02 | Promotion week and promotion type | `src/prepare.py` |
| BR-03 | Base price and promotion baseline | `sql/02_promo_baseline.sql` |
| BR-04 | Uplift and incremental volume | `sql/02_promo_baseline.sql`, DAX `Promo Uplift %` |
| BR-05 | Post-promotion dip | `sql/02_promo_baseline.sql`, DAX `Post-Promo Dip %` |
| BR-06 | Minimum evidence to publish an elasticity | `src/elasticity.py` |
| BR-07 | Data quality checks | `src/prepare.py`, `sql/05_data_quality.sql` |
| BR-08 | Price-pack ladder | `sql/04_price_per_unit.sql`, `src/ppa.py` |
| BR-09 | Margin assumption and promotion ROI | `src/promo.py`, DAX `Net Incremental Profit`, `Promo ROI` |
| BR-10 | Simulator limits | `src/simulator.py`, DAX `Sim *` measures |
| BR-11 | Pricing stance | `src/simulator.py`, `src/ppa.py` |
| BR-12 | Market template | `src/elasticity.py`, report page 6 |
| BR-13 | Data labelling | every report page, README |

---

### BR-01 · Product hierarchy
**Category > Brand > Product > Pack size.**
- Brand = manufacturer *within* a category. `brand_key = category + " | " + manufacturer`, so a manufacturer present in two categories counts as two brands.
- Product = one UPC. Its display name is the description plus the pack size, because one description can exist in several sizes.
- Manufacturer names truncated in the raw file are completed for display: General Mi → General Mills, Snyder S → Snyder's, Tonys → Tony's, P & G → P&G.
- Pack size is converted to ounces. Liquids (LT, ML) are converted to fluid ounces (1 fl oz = 29.5735 ml).

### BR-02 · Promotion week and promotion type
A store x product x week is a **promotion week** if any of the following is true:
- the product was in the retailer's circular (`feature = 1`);
- it had an in-store display (`display = 1`);
- it had a temporary price reduction only (`tpr_only = 1`);
- the price paid is at least **5% below the base price**.

The promotion type is assigned in this priority order: *Feature + Display* > *Feature* > *Display* > *TPR only* > *No promo*.
Discount depth = `1 - price / base_price`, floored at 0.

### BR-03 · Base price and promotion baseline
- **Base price** = the regular shelf price supplied by the retailer (`BASE_PRICE`). We use it as is; we do not re-estimate it.
- **Baseline units** for week *w* = the average units of the **clean weeks** within *w* ± 8 weeks, for the same store and product.
- A **clean week** has no promotion, is not one of the 2 weeks right after a promotion (those weeks can be depressed), and passes every quality check (BR-07).
- A baseline is **reliable** only if at least **4 clean weeks** are in the window. Promotion weeks without a reliable baseline are excluded from uplift and ROI.

### BR-04 · Uplift and incremental volume
- Uplift = `units / baseline - 1`, computed on totals (Σ units / Σ baseline - 1), not as an average of weekly ratios.
- Incremental units = `units - baseline`.

### BR-05 · Post-promotion dip
- A **post-promotion week** is the first non-promotion week after a promotion week.
- Dip = `Σ units / Σ baseline - 1` over post-promotion weeks with a reliable baseline. A negative dip means shoppers stocked up or bought earlier.

### BR-06 · Minimum evidence to publish an elasticity
An elasticity is **Published** only if all of these are true:

| Check | Threshold |
|---|---|
| Rows (store x product x week) | ≥ 1,000 |
| Distinct weeks | ≥ 52 |
| Stores (errors are clustered by store) | ≥ 5 |
| Price variation, average std of log(price) per product | ≥ 0.05 (about 5%) |
| p-value of the price coefficient | < 0.05 |
| Sign | negative |
| Width of the 95% interval | ≤ 1.5 |

Otherwise the status is:
- **Insufficient data**, if the first four checks fail;
- **Review**, if the estimate is positive, not significant or too uncertain, or if the brand or product is phasing out (BR-07).

A **positive and significant** elasticity is never shown as a number to business users. It goes to an analyst review checklist:
- price changes that coincide with features or displays the model does not capture;
- pack or mix changes under one UPC;
- data errors (price or units);
- a price increase during a demand peak (seasonality);
- too few distinct price points.

### BR-07 · Data quality checks
Rows are **flagged, not deleted**. Flagged rows (`dq_ok = 0`) stay in the sales totals but are excluded from the baseline and the models. A row is flagged when:
- the price or base price is missing or ≤ 0;
- the price is more than 5% above the base price;
- the price is more than 3 times, or less than a third of, the product's median price;
- units are ≤ 0;
- the store is not in the store lookup.

Store lookup: a store listed more than once (the raw file lists 2 stores twice, once *Mainstream* and once *Upscale*) keeps its **first** record and is flagged, so its sales are never counted twice. Duplicate week x store x product rows must be 0.

Three more checks are reported but do not flag rows:
- store x product pairs with missing weeks (possible out-of-stock or delisting);
- stores with less than 52 weeks of history;
- **phase-out products**: units of the last 13 weeks below 25% of the product's normal 13-week volume. They stay in the history and the promotion analysis, but a brand or product whose products are all phasing out gets the elasticity status *Review* (BR-06), so it is never simulated: its recent sales are not a valid base. In this data: the 3 Quaker cereals (sales collapse from Q3 2011) and the only Colgate product (no sales after March 2011).

### BR-08 · Price-pack ladder
- The ladder uses the **regular (base) price per ounce**, weighted by units, so promotions do not distort it.
- **Inverted ladder**: a bigger pack costs more per ounce than a smaller pack of the same manufacturer in the same sub-category.
- **Price index per oz** = product price per oz / sub-category average price per oz x 100.

### BR-09 · Margin assumption and promotion ROI
- Gross margin is **not in the data**. We **assume 30% of the regular price** for whoever funds the discount. The report lets users switch between 20% and 45%.
- Unit cost `c = base_price x (1 - margin)`.
- Net incremental profit = `units x (price - c) - baseline x (base_price - c)`. This is the profit with the promotion minus the profit we would have made without it.
- Discount cost = `(base_price - price) x units`.
- **Promotion ROI** = net incremental profit / discount cost. ROI > 0 means the promotion paid back.
- Display-only weeks have almost no discount, so their ROI is not shown.
- Feature and display fees paid to the retailer are not in the data, so the ROI of those mechanics is **optimistic**.

### BR-10 · Simulator limits
- Only **Published** elasticities (BR-06) can be simulated, and one segment at a time.
- Price change is limited to **±10%**. Outside the range of observed prices, a constant-elasticity model is not trusted.
- Every output comes with a range computed from the two ends of the 95% interval.
- The simulator assumes that competitors and the retailer do not react. It is a first-order estimate, not a forecast.

### BR-11 · Pricing stance
From the elasticity `e`, its 95% interval `[lo, hi]` and the margin `m`:

| Stance | Condition |
|---|---|
| Low sensitivity: price increase candidate | `lo > -1`: revenue and profit rise with price, even at the sensitive end |
| Low sensitivity (uncertain): test a price increase | `e > -1` but the interval crosses -1 |
| Moderate: price up grows profit but loses volume, test first | `-1/m ≤ e ≤ -1` |
| Highly sensitive: protect price position, targeted promotions | `hi < -1/m`: with m = 30%, more sensitive than -3.3 |

Why `-1/m`: a small price increase raises gross profit when `|e| < 1/m`, and raises revenue only when `|e| < 1`.

### BR-12 · Market template
- A market is a **filter**, here a US state. Code, SQL, rules, measures and report pages are identical for every market.
- A market's elasticity is published only if it passes BR-06 **on that market's own data**. Estimates are never borrowed from another market.
- Adding a market requires no code change. In production the market list would come from a parameter.

### BR-13 · Data labelling
- Every page carries a tag: **REAL RETAIL DATA**, **PUBLIC DATA**, **SIMULATED**, or a combination with **MODEL** or **ASSUMED MARGIN**.
- Measures built on simulated data end with **(SIM)**. Simulated tables carry `data_label = SIMULATED`.
- No number on a SIMULATED page may be quoted as a market fact.
