# User stories

Product: **RGM pricing product**, a prototype for a Revenue Management Europe organization.
Personas:
- **Revenue Manager (RM)**: owns the price and promotion plan of a market;
- **Category Manager (CM)**: owns the range and pack architecture;
- **Trade Marketing Manager (TM)**: owns the promotion calendar and trade spend;
- **Finance Business Partner (FBP)**: owns margin assumptions;
- **Product Owner (PO)**: rolls the product out to markets;
- **Data Engineer (DE)**: maintains the pipeline.

Priority uses MoSCoW. Acceptance criteria are in [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md), rules in [BUSINESS_RULES.md](BUSINESS_RULES.md).

| ID | Story | Priority | Rules | Report page |
|---|---|---|---|---|
| US-01 | As a **Revenue Manager**, I want to see the price elasticity of each category, brand and product with its 95% range and sample size, so that I know where a price move is low-risk and where it is not. | Must | BR-01, BR-06 | 1 |
| US-02 | As a **Revenue Manager**, I want elasticities that are unreliable or have the wrong sign to be flagged instead of shown as numbers, so that I never base a decision on noise. | Must | BR-06 | 1, 7 |
| US-03 | As a **Trade Marketing Manager**, I want the volume uplift and ROI of each promotion mechanic (TPR, feature, display) by brand, so that I can move trade spend to the mechanics that pay back. | Must | BR-02 to BR-04, BR-09 | 2 |
| US-04 | As a **Trade Marketing Manager**, I want to see the post-promotion dip and the cannibalisation of other products, so that I do not count stock-up and switching as growth. | Should | BR-05 | 2 |
| US-05 | As a **Revenue Manager**, I want to simulate a price change of up to ±10% on one brand and see the effect on volume, revenue and gross profit with a range, so that I can prepare a pricing proposal before talking to the retailer. | Must | BR-10, BR-11 | 4 |
| US-06 | As a **Finance Business Partner**, I want to change the margin assumption used in ROI and simulations, so that the results match the P&L of the market I support. | Should | BR-09 | 2, 4 |
| US-07 | As a **Category Manager**, I want to see the regular price per ounce of every pack and the packs whose ladder is inverted, so that I can fix pack-price architecture before the next price list. | Should | BR-08 | 3 |
| US-08 | As a **Revenue Manager**, I want external market share, competitor price index and distribution next to my internal sales, so that I read my price position against the market and not only inside one retailer. | Could (needs a NielsenIQ / Circana feed) | BR-13 | 5 |
| US-09 | As a **Product Owner**, I want to run the same pipeline, rules and report for a new market by changing a filter, without code changes, so that the product scales across European markets at low cost. | Must | BR-12 | 6 |
| US-10 | As a **Data Engineer**, I want every data quality check counted and visible, with flagged rows excluded from the models, so that a data issue is spotted before a business user sees a wrong number. | Must | BR-07 | 7 |

## Out of scope for this prototype
- Optimisation (recommending the profit-maximising price). The simulator evaluates scenarios that people propose.
- Competitor reaction and retailer pass-through modelling.
- Promotion calendar planning.
