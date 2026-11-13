# Acceptance criteria (Given / When / Then)

One block per user story ([USER_STORIES.md](USER_STORIES.md)). Each criterion is testable. The matching test is in [TEST_PLAN.md](TEST_PLAN.md).

## US-01 · Elasticity by segment
- **AC-01.1**
  - **Given** the weekly sales of a category with ≥ 1,000 clean rows over ≥ 52 weeks,
  - **When** the elasticity job runs,
  - **Then** the category gets an elasticity, a 95% interval, the number of rows, stores and weeks, and a status.
- **AC-01.2**
  - **Given** the Price elasticity page,
  - **When** I look at any estimate,
  - **Then** I see its interval and sample size next to it, never the point estimate alone.
- **AC-01.3**
  - **Given** an elasticity of -1.8,
  - **When** I read the "In plain English" column,
  - **Then** it says that +1% price means about -1.8% units, and that revenue falls when the price goes up.

## US-02 · Flag unreliable elasticities
- **AC-02.1**
  - **Given** a segment whose elasticity is positive and significant,
  - **When** results are published,
  - **Then** its status is "Review", the reason is shown, and the segment cannot be picked in the simulator.
- **AC-02.2**
  - **Given** a segment with < 52 weeks or a price that barely moved (std of log price < 0.05),
  - **When** results are published,
  - **Then** its status is "Insufficient data".
- **AC-02.3**
  - **Given** the Data quality page,
  - **When** it loads,
  - **Then** it shows how many segments are Published, Review or Insufficient data, by level.

## US-03 · Promotion uplift and ROI
- **AC-03.1**
  - **Given** a promotion week with fewer than 4 clean baseline weeks within ±8 weeks,
  - **When** uplift is computed,
  - **Then** that week is excluded.
- **AC-03.2**
  - **Given** a 30% margin, a $4.00 base price, a $3.00 promo price, 100 units sold and a baseline of 40 units,
  - **When** ROI is computed,
  - **Then**:
    - net incremental profit = 100 × (3.00 − 2.80) − 40 × (4.00 − 2.80) = **−$28**;
    - discount cost = **$100**;
    - ROI = **−28%**.
- **AC-03.3**
  - **Given** the promotion page,
  - **When** I filter one category,
  - **Then** uplift and ROI by mechanic recalculate for that category only.

## US-04 · Dip and cannibalisation
- **AC-04.1**
  - **Given** a non-promotion week that follows a promotion week,
  - **When** the dip is computed,
  - **Then** it equals Σ units / Σ baseline − 1 over those weeks.
- **AC-04.2**
  - **Given** a store-week where one product of a category is on promotion,
  - **When** cannibalisation is computed,
  - **Then** the other, non-promoted products of that category are compared with their own baselines.

## US-05 · Scenario simulator
- **AC-05.1**
  - **Given** a published elasticity e = −1.5, a +5% price change and a 30% margin,
  - **When** the simulator runs,
  - **Then**:
    - volume = 1.05^−1.5 − 1 = **−7.06%**;
    - revenue = 1.05^−0.5 − 1 = **−2.41%**;
    - gross profit = 1.05^−1.5 × 0.35 / 0.30 − 1 = **+8.43%**.
- **AC-05.2**
  - **Given** any scenario,
  - **When** results show,
  - **Then** each % comes with a low and a high value computed from the two ends of the 95% interval.
- **AC-05.3**
  - **Given** a request for +12%,
  - **When** I use the simulator,
  - **Then** it is not possible, because the price-change list stops at ±10%, and the Python function raises an error.
- **AC-05.4**
  - **Given** no segment, several segments or a non-published segment selected,
  - **When** the page renders,
  - **Then** the outputs are blank and the status says "Select ONE segment with a published elasticity".

## US-06 · Margin assumption
- **AC-06.1**
  - **Given** the margin slicer set to 40%,
  - **When** I read Promo ROI and Sim Gross Profit %,
  - **Then** both use m = 40%.
- **AC-06.2**
  - **Given** no margin selected,
  - **When** measures compute,
  - **Then** they use the default of 30%.

## US-07 · Price-pack architecture
- **AC-07.1**
  - **Given** two packs of the same manufacturer and sub-category,
  - **When** the bigger pack has a higher regular price per oz,
  - **Then** it is flagged "Fix ladder", with the smaller pack it is compared with and the premium per oz.
- **AC-07.2**
  - **Given** liquid packs in LT or ML,
  - **When** price per oz is computed,
  - **Then** sizes are first converted to fluid ounces.

## US-08 · External market view
- **AC-08.1**
  - **Given** simulated panel data,
  - **When** the page shows,
  - **Then** the page tag says SIMULATED, every simulated measure name ends with (SIM), and the subtitle says not to quote the numbers.
- **AC-08.2**
  - **Given** a category filter,
  - **When** market shares show,
  - **Then** the brands' shares add up to 100% within the category for each quarter.

## US-09 · Market roll-out
- **AC-09.1**
  - **Given** a new market's sales in the same format,
  - **When** the pipeline runs,
  - **Then** the same rules produce that market's estimates and statuses, with no code change.
- **AC-09.2**
  - **Given** a market whose own data fails BR-06,
  - **When** results are published,
  - **Then** that market's segment is not published, even if another market has a published value.

## US-10 · Data quality
- **AC-10.1**
  - **Given** a row with a price more than 3 times the product median,
  - **When** data is prepared,
  - **Then** the row is kept with `dq_ok = 0` and excluded from baselines and models.
- **AC-10.2**
  - **Given** the Data quality page,
  - **When** it loads,
  - **Then** each check shows the number of rows it hits, and the share of rows passing every check is shown.
