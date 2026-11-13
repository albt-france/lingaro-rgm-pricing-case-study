"""Generate the Power BI semantic model (TMDL) and the .pbip project skeleton.

One Python description of the model (tables, columns, measures, relationships) is written twice:
  1. powerbi/model.tmdl                      a 'createOrReplace' script: paste it in the TMDL view
                                             of Power BI Desktop and click Apply (method used in the
                                             previous case study);
  2. powerbi/LingaroRGM.SemanticModel/       the same model as a TMDL folder, so the .pbip opens
                                             with the model already in place.
It also writes the report shell (LingaroRGM.Report, theme). Pages: src/build_report_pages.py.

All file paths go through the DataFolder parameter (default C:\\lingaro-case-study\\data\\):
Power Query needs an absolute path; change the parameter if the repository lives elsewhere.

Usage:  python src/build_tmdl.py
"""
import json
import shutil
import uuid
from pathlib import Path

PBI = Path("powerbi")
NAME = "LingaroRGM"
DATA_FOLDER = "C:\\lingaro-case-study\\data\\"

# ----------------------------------------------------------------------------------------------
# Tables: name -> (csv path relative to DataFolder, [(column, type, format)], description)
# types: text, int, num, date, bool
# ----------------------------------------------------------------------------------------------
PCT, PCT1, USD, USD2, INT, DEC2, DEC3 = "0.0%", "0.0%", "$#,0", "$#,0.00", "#,0", "#,0.00", "0.000"

CSV_TABLES = {
    "Sales": ("clean\\sales_promo_weekly.csv", [
        ("week_end_date", "date", None), ("store_id", "int", None), ("upc", "int", None),
        ("units", "int", INT), ("spend", "num", USD2), ("price", "num", USD2), ("base_price", "num", USD2),
        ("discount_pct", "num", PCT), ("feature", "int", None), ("display", "int", None), ("tpr_only", "int", None),
        ("promo_type", "text", None), ("is_promo", "int", None), ("dq_ok", "int", None),
        ("baseline_units", "num", DEC2), ("baseline_n_weeks", "int", None), ("is_post_promo_week", "int", None)],
        "REAL RETAIL DATA - weekly sales by store and product (dunnhumby Breakfast at the Frat), with promo baseline"),
    "Product": ("clean\\products.csv", [
        ("upc", "int", None), ("product_name", "text", None), ("description", "text", None),
        ("manufacturer", "text", None), ("category", "text", None), ("sub_category", "text", None),
        ("size", "text", None), ("size_oz", "num", DEC2), ("brand_key", "text", None), ("is_private_label", "bool", None),
        ("phase_out", "int", None)],
        "Product hierarchy: category > manufacturer (brand) > product > pack size"),
    "Store": ("clean\\stores.csv", [
        ("store_id", "int", None), ("store_name", "text", None), ("city", "text", None), ("state", "text", None),
        ("segment", "text", None), ("sales_area_sqft", "num", INT)],
        "Stores; state is used as the 'market' for the cross-market template"),
    "Elasticity": ("output\\elasticity.csv", [
        ("segment_id", "int", None), ("level", "text", None), ("segment", "text", None), ("category", "text", None),
        ("manufacturer", "text", None), ("market", "text", None), ("upc", "num", None),
        ("n_obs", "int", INT), ("n_stores", "int", None), ("n_products", "int", None), ("n_weeks", "int", None),
        ("price_sd", "num", DEC3), ("base_units_52w", "num", INT), ("base_revenue_52w", "num", USD),
        ("avg_price_52w", "num", USD2), ("elasticity", "num", "0.00"), ("se", "num", DEC3),
        ("ci_low", "num", "0.00"), ("ci_high", "num", "0.00"), ("p_value", "num", "0.0000"), ("r2", "num", DEC3),
        ("feature_effect", "num", PCT), ("display_effect", "num", PCT),
        ("status", "text", None), ("status_reason", "text", None), ("plain_english", "text", None)],
        "Log-log price elasticities with 95% intervals and publication status (business rule BR-06)"),
    "Elasticity Split": ("output\\elasticity_split.csv", [
        ("category", "text", None), ("component", "text", None), ("elasticity", "num", "0.00"),
        ("ci_low", "num", "0.00"), ("ci_high", "num", "0.00"), ("p_value", "num", "0.0000"), ("n_obs", "int", INT),
        ("status", "text", None), ("note", "text", None)],
        "Regular-price vs promo-price-cut elasticity by category"),
    "Cross Elasticity": ("output\\cross_elasticity.csv", [
        ("category", "text", None), ("manufacturer", "text", None), ("n_obs", "int", INT),
        ("own_elasticity", "num", "0.00"), ("cross_elasticity", "num", "0.00"), ("ci_low", "num", "0.00"),
        ("ci_high", "num", "0.00"), ("p_value", "num", "0.0000"), ("reading", "text", None)],
        "Brand units vs rest-of-category price"),
    "Promo Effectiveness": ("output\\promo_effectiveness.csv", [
        ("brand_key", "text", None), ("category", "text", None), ("manufacturer", "text", None),
        ("promo_type", "text", None), ("promo_weeks", "int", INT), ("units", "num", INT),
        ("baseline_units", "num", INT), ("avg_discount", "num", PCT), ("incr_units", "num", INT),
        ("incr_revenue", "num", USD), ("discount_cost", "num", USD), ("net_incr_profit", "num", USD),
        ("paid_back_weeks", "int", INT), ("uplift", "num", PCT), ("roi", "num", PCT),
        ("share_weeks_paid_back", "num", PCT)],
        "Promotion results by brand and mechanic at the ASSUMED 30% margin"),
    "Promo Summary": ("output\\promo_summary.csv", [
        ("category", "text", None), ("promo_type", "text", None), ("promo_weeks", "int", INT),
        ("avg_discount", "num", PCT), ("uplift", "num", PCT), ("incr_units", "num", INT),
        ("discount_cost", "num", USD), ("net_incr_profit", "num", USD), ("roi", "num", PCT),
        ("margin_assumption", "num", "0%"), ("dip", "num", PCT), ("net_incr_profit_after_dip", "num", USD),
        ("roi_after_dip", "num", PCT)],
        "Promotion results by category and mechanic, margin sensitivity 20/30/40%"),
    "Promo Dip": ("output\\promo_dip.csv", [
        ("category", "text", None), ("post_weeks", "int", INT), ("units", "num", INT),
        ("baseline_units", "num", INT), ("dip", "num", PCT), ("dip_units", "num", INT)],
        "Post-promotion dip by category"),
    "Cannibalisation": ("output\\cannibalisation.csv", [
        ("category", "text", None), ("context", "text", None), ("weeks", "int", INT), ("units", "num", INT),
        ("baseline_units", "num", INT), ("vs_baseline", "num", PCT)],
        "Non-promoted products when another product of the category is on promotion"),
    "PPA": ("output\\ppa.csv", [
        ("category", "text", None), ("sub_category", "text", None), ("manufacturer", "text", None),
        ("upc", "int", None), ("description", "text", None), ("size", "text", None), ("size_oz", "num", DEC2),
        ("units", "num", INT), ("avg_base_price", "num", USD2), ("base_price_per_oz", "num", "$0.000"),
        ("elasticity", "num", "0.00"), ("price_index_per_oz", "num", "0"), ("inverted_vs", "text", None),
        ("inversion_premium", "num", PCT), ("opportunity", "text", None)],
        "Price-pack architecture: regular price per ounce by pack"),
    "Scenario Grid": ("output\\scenario_grid.csv", [
        ("segment_id", "int", None), ("level", "text", None), ("segment", "text", None),
        ("price_change", "num", "+0%;-0%;0%"), ("volume_pct", "num", PCT), ("volume_pct_low", "num", PCT),
        ("volume_pct_high", "num", PCT), ("revenue_pct", "num", PCT), ("revenue_pct_low", "num", PCT),
        ("revenue_pct_high", "num", PCT), ("profit_pct", "num", PCT), ("profit_pct_low", "num", PCT),
        ("profit_pct_high", "num", PCT), ("revenue_delta", "num", USD), ("profit_delta", "num", USD)],
        "Pre-computed scenarios -10%..+10% (oracle for the DAX simulator)"),
    "Pricing Stance": ("output\\pricing_stance.csv", [
        ("segment_id", "int", None), ("level", "text", None), ("segment", "text", None),
        ("elasticity", "num", "0.00"), ("ci_low", "num", "0.00"), ("ci_high", "num", "0.00"), ("stance", "text", None)],
        "Pricing stance per published segment (business rule BR-11)"),
    "Market Sim": ("output\\market_sim.csv", [
        ("brand_key", "text", None), ("category", "text", None), ("manufacturer", "text", None),
        ("quarter", "text", None), ("market_value", "num", USD), ("market_value_share", "num", PCT),
        ("retailer_revenue", "num", USD), ("retailer_value_share", "num", PCT), ("retailer_price", "num", USD2),
        ("competitor_avg_price", "num", USD2), ("price_index_vs_competitors", "num", "0.0"),
        ("numeric_distribution", "num", PCT), ("weighted_distribution", "num", PCT), ("data_label", "text", None)],
        "SIMULATED NielsenIQ/Circana-style market data (seed 42) - not real"),
    "Data Quality": ("output\\sql_05_data_quality.csv", [
        ("check_name", "text", None), ("rows_hit", "num", INT), ("note", "text", None)],
        "Data quality checks (business rule BR-07)"),
}

M_TYPES = {"text": "type text", "int": "Int64.Type", "num": "type number", "date": "type date", "bool": "type logical"}
TMDL_TYPES = {"text": "string", "int": "int64", "num": "double", "date": "dateTime", "bool": "boolean"}

# Tables built in Power Query from other queries or literals: name -> (columns, M expression)
M_TABLES = {
    "Date": ([("Week End Date", "date", "dd mmm yyyy"), ("Year", "int", "0"), ("Quarter", "text", None),
              ("Month", "text", None), ("MonthKey", "int", "0")],
             """let
    Weeks = List.Distinct(Sales[week_end_date]),
    First = List.Min(Weeks),
    Last = List.Max(Weeks),
    Dates = List.Dates(First, Number.RoundDown(Duration.Days(Last - First) / 7) + 1, #duration(7, 0, 0, 0)),
    T = Table.FromList(Dates, Splitter.SplitByNothing(), type table [Week End Date = date]),
    Y = Table.AddColumn(T, "Year", each Date.Year([Week End Date]), Int64.Type),
    Q = Table.AddColumn(Y, "Quarter", each Text.From([Year]) & "-Q" & Text.From(Date.QuarterOfYear([Week End Date])), type text),
    M = Table.AddColumn(Q, "Month", each Date.ToText([Week End Date], "MMM yyyy", "en-US"), type text),
    K = Table.AddColumn(M, "MonthKey", each [Year] * 100 + Date.Month([Week End Date]), Int64.Type)
in
    K"""),
    "Brand": ([("brand_key", "text", None), ("category", "text", None), ("manufacturer", "text", None)],
              """let
    Source = Table.SelectColumns(Product, {"brand_key", "category", "manufacturer"}),
    Distinct = Table.Distinct(Source)
in
    Distinct"""),
    "Promo Type": ([("promo_type", "text", None), ("sort_order", "int", "0")],
                   """#table(type table [promo_type = text, sort_order = Int64.Type],
    {{"No promo", 0}, {"TPR only", 1}, {"Display", 2}, {"Feature", 3}, {"Feature + Display", 4}})"""),
    "Price Change": ([("Price Change", "num", "+0%;-0%;0%")],
                     """#table(type table [Price Change = number], List.Transform({-10..10}, each {_ / 100}))"""),
    "Margin Assumption": ([("Margin", "num", "0%")],
                          """#table(type table [Margin = number], List.Transform({4..9}, each {_ * 5 / 100}))"""),
}

SORT_BY = {("Date", "Month"): "MonthKey", ("Promo Type", "promo_type"): "sort_order"}
HIDDEN = {("Date", "MonthKey"), ("Promo Type", "sort_order")}

# ----------------------------------------------------------------------------------------------
# Measures: (name, DAX, format, display folder). Kept on one line each so they are easy to read.
# ----------------------------------------------------------------------------------------------
REL = "Sales[is_promo] = 1, Sales[baseline_n_weeks] >= 4, Sales[dq_ok] = 1, Sales[baseline_units] > 0"
MEASURES = [
    # 1 Sales
    ("Revenue", "SUM ( Sales[spend] )", USD, "1 Sales"),
    ("Units", "SUM ( Sales[units] )", INT, "1 Sales"),
    ("Avg Price", "DIVIDE ( [Revenue], [Units] )", USD2, "1 Sales"),
    ("Avg Base Price", "DIVIDE ( SUMX ( Sales, Sales[base_price] * Sales[units] ), [Units] )", USD2, "1 Sales"),
    ("Avg Base Price per Oz", "DIVIDE ( SUMX ( Sales, Sales[base_price] * Sales[units] ), SUMX ( Sales, RELATED ( Product[size_oz] ) * Sales[units] ) )", "$0.000", "1 Sales"),
    ("Promo Revenue Share", "DIVIDE ( CALCULATE ( [Revenue], Sales[is_promo] = 1 ), [Revenue] )", PCT, "1 Sales"),
    ("Avg Discount Depth", "CALCULATE ( AVERAGE ( Sales[discount_pct] ), Sales[is_promo] = 1, Sales[discount_pct] > 0 )", PCT, "1 Sales"),
    ("Revenue L52W", "VAR LastWeek = CALCULATE ( MAX ( Sales[week_end_date] ), REMOVEFILTERS () ) RETURN CALCULATE ( [Revenue], 'Date'[Week End Date] > LastWeek - 364 )", USD, "1 Sales"),
    ("Revenue P52W", "VAR LastWeek = CALCULATE ( MAX ( Sales[week_end_date] ), REMOVEFILTERS () ) RETURN CALCULATE ( [Revenue], 'Date'[Week End Date] > LastWeek - 728, 'Date'[Week End Date] <= LastWeek - 364 )", USD, "1 Sales"),
    ("Revenue YoY %", "DIVIDE ( [Revenue L52W], [Revenue P52W] ) - 1", PCT, "1 Sales"),
    # 2 Promotions
    ("Promo Weeks", f"CALCULATE ( COUNTROWS ( Sales ), {REL} )", INT, "2 Promotions"),
    ("Promo Units", f"CALCULATE ( SUM ( Sales[units] ), {REL} )", INT, "2 Promotions"),
    ("Promo Baseline Units", f"CALCULATE ( SUM ( Sales[baseline_units] ), {REL} )", INT, "2 Promotions"),
    ("Incremental Units", "[Promo Units] - [Promo Baseline Units]", INT, "2 Promotions"),
    ("Promo Uplift %", "DIVIDE ( [Promo Units], [Promo Baseline Units] ) - 1", PCT, "2 Promotions"),
    ("Discount Cost", f"CALCULATE ( SUMX ( Sales, MAX ( Sales[base_price] - Sales[price], 0 ) * Sales[units] ), {REL} )", USD, "2 Promotions"),
    ("Net Incremental Profit", f"VAR m = [Margin Value] RETURN CALCULATE ( SUMX ( Sales, Sales[units] * ( Sales[price] - Sales[base_price] * ( 1 - m ) ) - Sales[baseline_units] * Sales[base_price] * m ), {REL} )", USD, "2 Promotions"),
    ("Promo ROI", "DIVIDE ( [Net Incremental Profit], [Discount Cost] )", PCT, "2 Promotions"),
    ("Post-Promo Dip %", "DIVIDE ( CALCULATE ( SUM ( Sales[units] ), Sales[is_post_promo_week] = 1, Sales[baseline_n_weeks] >= 4, Sales[baseline_units] > 0 ), CALCULATE ( SUM ( Sales[baseline_units] ), Sales[is_post_promo_week] = 1, Sales[baseline_n_weeks] >= 4, Sales[baseline_units] > 0 ) ) - 1", PCT, "2 Promotions"),
    # 3 Elasticity
    ("Published Elasticities", "CALCULATE ( COUNTROWS ( Elasticity ), Elasticity[status] = \"Published\", Elasticity[level] IN { \"Category\", \"Brand\", \"Product\" } )", INT, "3 Elasticity"),
    ("Avg Elasticity", "AVERAGE ( Elasticity[elasticity] )", "0.00", "3 Elasticity"),
    ("Segments", "COUNTROWS ( Elasticity )", INT, "3 Elasticity"),
    # 4 Simulator
    ("Price Change Value", "SELECTEDVALUE ( 'Price Change'[Price Change], 0.05 )", "+0%;-0%;0%", "4 Simulator"),
    ("Margin Value", "SELECTEDVALUE ( 'Margin Assumption'[Margin], 0.3 )", "0%", "4 Simulator"),
    ("Sim Elasticity", "IF ( HASONEVALUE ( Elasticity[segment_id] ) && SELECTEDVALUE ( Elasticity[status] ) = \"Published\", SELECTEDVALUE ( Elasticity[elasticity] ) )", "0.00", "4 Simulator"),
    ("Sim Volume %", "VAR e = [Sim Elasticity] RETURN IF ( NOT ISBLANK ( e ), POWER ( 1 + [Price Change Value], e ) - 1 )", "+0.0%;-0.0%;0.0%", "4 Simulator"),
    ("Sim Volume % Low", "VAR p = [Price Change Value] RETURN IF ( NOT ISBLANK ( [Sim Elasticity] ), MIN ( POWER ( 1 + p, SELECTEDVALUE ( Elasticity[ci_low] ) ), POWER ( 1 + p, SELECTEDVALUE ( Elasticity[ci_high] ) ) ) - 1 )", "+0.0%;-0.0%;0.0%", "4 Simulator"),
    ("Sim Volume % High", "VAR p = [Price Change Value] RETURN IF ( NOT ISBLANK ( [Sim Elasticity] ), MAX ( POWER ( 1 + p, SELECTEDVALUE ( Elasticity[ci_low] ) ), POWER ( 1 + p, SELECTEDVALUE ( Elasticity[ci_high] ) ) ) - 1 )", "+0.0%;-0.0%;0.0%", "4 Simulator"),
    ("Sim Revenue %", "VAR e = [Sim Elasticity] RETURN IF ( NOT ISBLANK ( e ), POWER ( 1 + [Price Change Value], 1 + e ) - 1 )", "+0.0%;-0.0%;0.0%", "4 Simulator"),
    ("Sim Gross Profit %", "VAR e = [Sim Elasticity] VAR p = [Price Change Value] VAR m = [Margin Value] RETURN IF ( NOT ISBLANK ( e ), POWER ( 1 + p, e ) * ( m + p ) / m - 1 )", "+0.0%;-0.0%;0.0%", "4 Simulator"),
    ("Sim Gross Profit % Low", "VAR p = [Price Change Value] VAR m = [Margin Value] RETURN IF ( NOT ISBLANK ( [Sim Elasticity] ), MIN ( POWER ( 1 + p, SELECTEDVALUE ( Elasticity[ci_low] ) ), POWER ( 1 + p, SELECTEDVALUE ( Elasticity[ci_high] ) ) ) * ( m + p ) / m - 1 )", "+0.0%;-0.0%;0.0%", "4 Simulator"),
    ("Sim Gross Profit % High", "VAR p = [Price Change Value] VAR m = [Margin Value] RETURN IF ( NOT ISBLANK ( [Sim Elasticity] ), MAX ( POWER ( 1 + p, SELECTEDVALUE ( Elasticity[ci_low] ) ), POWER ( 1 + p, SELECTEDVALUE ( Elasticity[ci_high] ) ) ) * ( m + p ) / m - 1 )", "+0.0%;-0.0%;0.0%", "4 Simulator"),
    ("Sim Revenue Change", "[Sim Revenue %] * SELECTEDVALUE ( Elasticity[base_revenue_52w] )", "+$#,0;-$#,0;$0", "4 Simulator"),
    ("Sim Gross Profit Change", "[Sim Gross Profit %] * SELECTEDVALUE ( Elasticity[base_revenue_52w] ) * [Margin Value]", "+$#,0;-$#,0;$0", "4 Simulator"),
    ("Sim Status", "IF ( ISBLANK ( [Sim Elasticity] ), \"Select ONE segment with a published elasticity (BR-06)\", \"Published elasticity \" & FORMAT ( [Sim Elasticity], \"0.00\" ) & \" (95% CI \" & FORMAT ( SELECTEDVALUE ( Elasticity[ci_low] ), \"0.00\" ) & \" to \" & FORMAT ( SELECTEDVALUE ( Elasticity[ci_high] ), \"0.00\" ) & \"), price change capped at +/-10% (BR-10)\" )", None, "4 Simulator"),
    # 5 Market (SIMULATED)
    ("Market Value Share (SIM)", "DIVIDE ( SUM ( 'Market Sim'[market_value] ), CALCULATE ( SUM ( 'Market Sim'[market_value] ), REMOVEFILTERS ( Brand[manufacturer], Brand[brand_key], 'Market Sim'[manufacturer], 'Market Sim'[brand_key] ) ) )", PCT, "5 Market (SIMULATED)"),
    ("Retailer Value Share", "DIVIDE ( SUM ( 'Market Sim'[retailer_revenue] ), CALCULATE ( SUM ( 'Market Sim'[retailer_revenue] ), REMOVEFILTERS ( Brand[manufacturer], Brand[brand_key], 'Market Sim'[manufacturer], 'Market Sim'[brand_key] ) ) )", PCT, "5 Market (SIMULATED)"),
    ("Price Index vs Competitors (SIM)", "AVERAGE ( 'Market Sim'[price_index_vs_competitors] )", "0.0", "5 Market (SIMULATED)"),
    ("Weighted Distribution (SIM)", "AVERAGE ( 'Market Sim'[weighted_distribution] )", PCT, "5 Market (SIMULATED)"),
    # 6 Data quality
    ("Rows Passing Checks %", "DIVIDE ( CALCULATE ( COUNTROWS ( Sales ), Sales[dq_ok] = 1 ), COUNTROWS ( Sales ) )", "0.00%", "6 Data quality"),
    ("Flagged Rows", "CALCULATE ( COUNTROWS ( Sales ), Sales[dq_ok] = 0 )", INT, "6 Data quality"),
]

RELATIONSHIPS = [
    ("Sales", "upc", "Product", "upc"),
    ("Sales", "store_id", "Store", "store_id"),
    ("Sales", "week_end_date", "Date", "Week End Date"),
    ("Sales", "promo_type", "Promo Type", "promo_type"),
    ("Product", "brand_key", "Brand", "brand_key"),
    ("Promo Effectiveness", "brand_key", "Brand", "brand_key"),
    ("Promo Effectiveness", "promo_type", "Promo Type", "promo_type"),
    ("Market Sim", "brand_key", "Brand", "brand_key"),
    ("Scenario Grid", "segment_id", "Elasticity", "segment_id"),
]


# ----------------------------------------------------------------------------------------------
# TMDL writers
# ----------------------------------------------------------------------------------------------
def q(name):
    """Quote a TMDL object name when needed."""
    return name if name.replace("_", "").isalnum() else "'" + name.replace("'", "''") + "'"


def indent(text, n):
    return "\n".join(("\t" * n + ln) if ln.strip() else ln for ln in text.splitlines())


def csv_m(path, cols):
    types = ", ".join(f'{{"{c}", {M_TYPES[t]}}}' for c, t, _ in cols)
    keep = ", ".join(f'"{c}"' for c, _, _ in cols)
    return f"""let
    Source = Csv.Document(File.Contents(DataFolder & "{path}"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Kept = Table.SelectColumns(Promoted, {{{keep}}}, MissingField.UseNull),
    Typed = Table.TransformColumnTypes(Kept, {{{types}}}, "en-US")
in
    Typed"""


def table_tmdl(name, cols, m_expr, description=None, measures=None, lvl=0):
    t = lvl
    out = []
    if description:
        out.append("\t" * t + f"/// {description}")
    out.append("\t" * t + f"table {q(name)}")
    if name == "Date":
        out.append("\t" * (t + 1) + "dataCategory: Time")
    out.append("")
    for mname, dax, fmt, folder in measures or []:
        out.append("\t" * (t + 1) + f"measure {q(mname)} = {dax}")
        if fmt:
            out.append("\t" * (t + 2) + f"formatString: {fmt}")
        out.append("\t" * (t + 2) + f"displayFolder: {folder}")
        out.append("")
    for c, typ, fmt in cols:
        out.append("\t" * (t + 1) + f"column {q(c)}")
        out.append("\t" * (t + 2) + f"dataType: {TMDL_TYPES[typ]}")
        if (name, c) in HIDDEN or c == "_":
            out.append("\t" * (t + 2) + "isHidden")
        if fmt:
            out.append("\t" * (t + 2) + f"formatString: {fmt}")
        out.append("\t" * (t + 2) + "summarizeBy: none")
        out.append("\t" * (t + 2) + f"sourceColumn: {c}")
        if (name, c) in SORT_BY:
            out.append("\t" * (t + 2) + f"sortByColumn: {q(SORT_BY[(name, c)])}")
        if typ == "date":
            out.append("")
            out.append("\t" * (t + 2) + "annotation UnderlyingDateTimeDataType = Date")
        out.append("")
    out.append("\t" * (t + 1) + f"partition {q(name)} = m")
    out.append("\t" * (t + 2) + "mode: import")
    out.append("\t" * (t + 2) + "source =")
    out.append(indent(m_expr, t + 3))
    out.append("")
    return "\n".join(out)


def all_tables():
    """Yield (name, cols, m_expression, description, measures) for every table, in load order."""
    for name, (path, cols, desc) in CSV_TABLES.items():
        yield name, cols, csv_m(path, cols), desc, None
    for name, (cols, m) in M_TABLES.items():
        yield name, cols, m, None, None
    yield "_Measures", [("_", "text", None)], "#table(type table [_ = text], {})", \
        "All DAX measures, grouped in display folders", MEASURES


def rel_tmdl(i, a, ac, b, bc, lvl=0):
    t = "\t" * lvl
    return (f"{t}relationship rel_{i:02d}\n{t}\tfromColumn: {q(a)}.{q(ac)}\n{t}\ttoColumn: {q(b)}.{q(bc)}\n")


EXPR = f'expression DataFolder = "{DATA_FOLDER}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'


def write_script():
    parts = ["createOrReplace", "", "\t" + EXPR, ""]
    for name, cols, m, desc, meas in all_tables():
        parts.append(table_tmdl(name, cols, m, desc, meas, lvl=1))
    for i, r in enumerate(RELATIONSHIPS, 1):
        parts.append(rel_tmdl(i, *r, lvl=1))
    (PBI / "model.tmdl").write_text("\n".join(parts), encoding="utf-8")


def write_semantic_model():
    sm = PBI / f"{NAME}.SemanticModel"
    if sm.exists():
        shutil.rmtree(sm)
    d = sm / "definition"
    (d / "tables").mkdir(parents=True)
    (sm / "definition.pbism").write_text(json.dumps({"version": "4.2", "settings": {}}, indent=2), encoding="utf-8")
    (sm / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": str(uuid.uuid5(uuid.NAMESPACE_URL, NAME + ".SemanticModel"))}},
        indent=2), encoding="utf-8")
    (d / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1600\n", encoding="utf-8")
    names = [n for n, *_ in all_tables()]
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tsourceQueryCulture: en-US", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
             "annotation __PBI_TimeIntelligenceEnabled = 0", "",
             'annotation PBI_ProTooling = ["TMDLView_Desktop","DevMode"]', "",
             "annotation PBI_QueryOrder = " + json.dumps(names + ["DataFolder"]), ""]
    model += [f"ref table {q(n)}" for n in names]
    (d / "model.tmdl").write_text("\n".join(model) + "\n", encoding="utf-8")
    (d / "expressions.tmdl").write_text(EXPR + "\n\n\tannotation PBI_ResultType = Text\n", encoding="utf-8")
    for name, cols, m, desc, meas in all_tables():
        (d / "tables" / f"{name}.tmdl").write_text(table_tmdl(name, cols, m, desc, meas), encoding="utf-8")
    (d / "relationships.tmdl").write_text("\n".join(rel_tmdl(i, *r) for i, r in enumerate(RELATIONSHIPS, 1)),
                                          encoding="utf-8")


def write_report_shell():
    rp = PBI / f"{NAME}.Report"
    (rp / "definition" / "pages").mkdir(parents=True, exist_ok=True)
    (rp / "StaticResources" / "RegisteredResources").mkdir(parents=True, exist_ok=True)
    (PBI / f"{NAME}.pbip").write_text(json.dumps({"version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
                                                  "settings": {"enableAutoRecovery": True}}, indent=2), encoding="utf-8")
    (rp / "definition.pbir").write_text(json.dumps({"version": "4.0", "datasetReference": {
        "byPath": {"path": f"../{NAME}.SemanticModel"}}}, indent=2), encoding="utf-8")
    (rp / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": str(uuid.uuid5(uuid.NAMESPACE_URL, NAME + ".Report"))}},
        indent=2), encoding="utf-8")
    (rp / "definition" / "version.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0"}, indent=2), encoding="utf-8")
    shutil.copy(PBI / "theme.json", rp / "StaticResources" / "RegisteredResources" / "LingaroRGM_Theme.json")
    ver = {"visual": "2.14.0", "report": "3.4.0", "page": "2.3.1"}
    report = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "Fluent2-CY26SU10", "reportVersionAtImport": ver, "type": "SharedResources"},
            "customTheme": {"name": "LingaroRGM_Theme.json", "reportVersionAtImport": ver, "type": "RegisteredResources"}},
        "objects": {"section": [{"properties": {"verticalAlignment": {"expr": {"Literal": {"Value": "'Top'"}}}}}]},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "Fluent2-CY26SU10", "path": "BaseThemes/Fluent2-CY26SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "LingaroRGM_Theme.json", "path": "LingaroRGM_Theme.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                     "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}}
    (rp / "definition" / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    write_script()
    write_semantic_model()
    write_report_shell()
    print(f"tables: {len(list(all_tables()))}, measures: {len(MEASURES)}, relationships: {len(RELATIONSHIPS)}")
