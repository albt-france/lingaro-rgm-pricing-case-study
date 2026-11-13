# Test and validation plan

How we know a number is right before a Revenue Manager sees it.
- Automated checks run with `python src/check_results.py`. They print PASS/FAIL, write `data/output/checks.csv` and stop the release if anything fails.
- Manual checks in Power BI are listed at the end of this file.

## Levels
| Level | Question | How |
|---|---|---|
| T1 · Rule unit tests | Does each formula give the hand-computed answer? | Worked examples from the acceptance criteria |
| T2 · Data reconciliation | Do rows and totals survive every step? | Totals compared between CSV, SQL and Python |
| T3 · Model and output checks | Do the outputs respect the business rules? | Assertions on every output table |
| T4 · Report checks | Does Power BI show the same numbers as Python? | DAX measure vs Python value, by hand, at release |
| T5 · Method validation | Does the model find the truth when we know it? | Recovery test on simulated data |

## T1 · Rule unit tests (automated)
| ID | Test | Expected | Criterion |
|---|---|---|---|
| T1.1 | ROI worked example: base $4.00, promo $3.00, 100 units, baseline 40, margin 30% | ROI = -28% | AC-03.2 |
| T1.2 | Simulator worked example: e = -1.5, +5%, margin 30% | volume -7.06%, revenue -2.41%, profit +8.43% | AC-05.1 |
| T1.3 | Simulator with +12% | error | AC-05.3, BR-10 |
| T1.4 | Pack size parsing | 1 LT = 33.81 fl oz, 12.25 OZ = 12.25 oz | AC-07.2 |
| T1.5 | Pricing stance classes | low / moderate / high examples land in the right class | BR-11 |
| T1.6 | Profit threshold | +1% price raises profit at e = -3.0, lowers it at e = -3.6 (m = 30%) | BR-11 |

## T2 · Data reconciliation (automated)
| ID | Test |
|---|---|
| T2.1 | Same row count before and after the SQL baseline step |
| T2.2 | Same revenue total in the clean CSV and the SQL output |
| T2.3 | Categories add up to the grand total in the hierarchy roll-up |
| T2.4 | Data quality: "rows passing every check" equals the number of `dq_ok` rows |
| T2.5 | No row with price ≤ 0 or units ≤ 0 is marked OK |
| T2.6 | Baseline is unbiased: on non-promo weeks, Σ units / Σ baseline is within ±5% |

## T3 · Model and output checks (automated)
| ID | Test | Rule |
|---|---|---|
| T3.1 | Every published elasticity is negative | BR-06 |
| T3.2 | Every published 95% interval is ≤ 1.5 wide | BR-06 |
| T3.3 | Every published segment has ≥ 1,000 rows and ≥ 52 weeks | BR-06 |
| T3.4 | Each point estimate sits inside its interval | - |
| T3.5 | Promotion brand table adds up to the category table | BR-09 |
| T3.6 | Promo uplift computed with the DAX logic on Sales rows equals the Python table | BR-04 |
| T3.7 | A 0% price change gives 0% everywhere | BR-10 |
| T3.8 | Low ≤ central ≤ high for every scenario | BR-10 |
| T3.9 | The simulator only contains published segments | BR-06, BR-10 |
| T3.10 | SIMULATED shares add up to 100% per category and quarter | AC-08.2 |
| T3.11 | Every simulated row is labelled SIMULATED | BR-13 |
| T3.12 | Units-weighted price index per oz = 100 in each sub-category | BR-08 |
| T4.1 | `findings.json` is complete (every number in titles comes from it) | - |

## T4 · Power BI vs Python (manual, at each release)
Open the report, refresh, then check:

| Measure (DAX) | Filter | Must equal | Source |
|---|---|---|---|
| `Revenue L52W` | none | `revenue_l52w` | `data/output/findings.json` |
| `Promo Uplift %` | promo type = TPR only | TPR row: Σ units / Σ baseline_units - 1 | `data/output/promo_effectiveness.csv` |
| `Promo ROI` | margin 30%, one category | that category's row at 30% | `data/output/promo_summary.csv` |
| `Sim Volume %`, `Sim Revenue %`, `Sim Gross Profit %` | one segment, +5%, margin 30% | `volume_pct`, `revenue_pct`, `profit_pct` at `price_change = 0.05` | `data/output/scenario_grid.csv` |
| `Market Value Share (SIM)` | one category, one quarter | `market_value_share` | `data/output/market_sim.csv` |
| `Rows Passing Checks %` | none | `dq_ok_share` | `data/output/findings.json` |

Also check, on the simulator page, that selecting two segments, or a segment whose status is not Published, blanks every output (AC-05.4).

## T5 · Method validation on simulated data
`src/make_sample_data.py` builds a SIMULATED dataset with known elasticities. Running the pipeline on it and then `src/check_recovery.py` gives:
- **9 of the 10** true product elasticities fall inside the estimated 95% interval;
- the mean absolute error is **0.06**.

With a 95% interval, about 1 miss in 20 is expected. Result file: [docs/validation/recovery_test_sample.csv](../docs/validation/recovery_test_sample.csv).
This shows that the regression and the controls work as intended. It does **not** prove that the real-data estimates are causal: see the limits in the README.

## What would be added in production
- Data-contract tests on each new market feed: schema, week continuity, price ranges.
- Alerts on the share of Published segments falling below the previous run.
- Back-testing: compare simulated volume with actual volume after a real price change.
- User acceptance testing with Revenue Managers, using the acceptance criteria as the script.
