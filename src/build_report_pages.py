"""Generate the Power BI report pages (PBIR format) in powerbi/LingaroRGM.Report.

Usage:  python src/build_report_pages.py
Close Power BI Desktop first: every page is rewritten by this script.
Page titles state the conclusion; their numbers are read from data/output/findings.json.
"""
import json
import shutil
from pathlib import Path

REPORT = Path("powerbi/LingaroRGM.Report")
PAGES = REPORT / "definition" / "pages"
F = json.loads(Path("data/output/findings.json").read_text(encoding="utf-8"))
VC_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
PAGES_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"
M = "_Measures"

INK, INK2, MUTED, BLUE, GREY, RED = "#0B0B0B", "#52514E", "#898781", "#2A78D6", "#B4B2A9", "#D03B3B"
SEQ = {"250": "#86B6EF", "450": "#2A78D6", "650": "#104281"}
NEUTRAL, RED_TINT, BLUE_TINT = "#F0EFEC", "#F4C7C6", "#B7D3F6"
FOOT = "Independent case study based on public data · not affiliated with or endorsed by Lingaro"


def pct(x, d=0, sign=False):
    return f"{x * 100:+.{d}f}%" if sign else f"{x * 100:.{d}f}%"


# ---------- expression helpers (same structure as the PBIR files Power BI Desktop writes) ----------
def raw(v):
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, (int, float)):
        s = f"{v}D"
    else:
        s = "'" + str(v).replace("'", "''") + "'"
    return {"Literal": {"Value": s}}


def lit(v):
    return {"expr": raw(v)}


def color(h):
    return {"solid": {"color": lit(h)}}


def col(t, c):
    return {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}}


def meas(n):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": M}}, "Property": n}}


def agg(t, c, fn=0):
    """fn 0 = Sum, 1 = Average."""
    return {"Aggregation": {"Expression": col(t, c), "Function": fn}}


def qref(f):
    if "Column" in f:
        c = f["Column"]
        return f'{c["Expression"]["SourceRef"]["Entity"]}.{c["Property"]}'
    if "Measure" in f:
        return f'{M}.{f["Measure"]["Property"]}'
    c = f["Aggregation"]["Expression"]["Column"]
    fn = {0: "Sum", 1: "Avg"}[f["Aggregation"]["Function"]]
    return f'{fn}({c["Expression"]["SourceRef"]["Entity"]}.{c["Property"]})'


def proj(f, label=None):
    p = {"field": f, "queryRef": qref(f)}
    if "Column" in f:
        p["nativeQueryRef"] = f["Column"]["Property"]
    elif "Measure" in f:
        p["nativeQueryRef"] = f["Measure"]["Property"]
    else:
        name = f["Aggregation"]["Expression"]["Column"]["Property"]
        p["nativeQueryRef"] = name
        p["displayName"] = name
    if label:
        p["displayName"] = label
    return p


C = col


def series_color(f, h):
    return {"properties": {"fill": color(h)}, "selector": {"metadata": qref(f)}}


def ref_line(value, label, h=INK2):
    return {"properties": {"show": lit(True), "value": lit(value), "displayName": lit(label), "lineColor": color(h),
                           "style": lit("dashed"), "dataLabelShow": lit(True), "dataLabelColor": color(h)},
            "selector": {"id": "1"}}


def bg_rule(f, lo, hi, mid=None, mid_value=None):
    rule = {"min": {"color": raw(lo)}, "max": {"color": raw(hi)}, "nullColoringStrategy": {"strategy": raw("asZero")}}
    key = "linearGradient2"
    if mid:
        key = "linearGradient3"
        rule["mid"] = {"color": raw(mid)}
        if mid_value is not None:
            rule["mid"]["value"] = raw(mid_value)
    return {"properties": {"backColor": {"solid": {"color": {"expr": {"FillRule": {"Input": f, "FillRule": {key: rule}}}}}}},
            "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": qref(f)}}


def table_style(extra=(), matrix=False):
    fs = {"properties": {"fontSize": lit(11)}}
    o = {"values": [fs, *extra], "columnHeaders": [{"properties": {"fontSize": lit(11), "fontColor": color(INK2)}}]}
    if matrix:
        o["rowHeaders"] = [fs]
        o["subTotals"] = [{"properties": {"rowSubtotals": lit(False), "columnSubtotals": lit(False)}}]
    else:
        o["total"] = [{"properties": {"totals": lit(False)}}]
    return o


def cat_filter(table, column, values, negate=False, i=0):
    cond = {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": column}}],
                   "Values": [[raw(v)] for v in values]}}
    if negate:
        cond = {"Not": {"Expression": cond}}
    return {"name": f"visualFilter{i}", "type": "Categorical", "field": col(table, column),
            "filter": {"Version": 2, "From": [{"Name": "t", "Entity": table, "Type": 0}], "Where": [{"Condition": cond}]}}


class Page:
    def __init__(self, pid, name):
        self.pid, self.name, self.visuals, self.interactions, self.n = pid, name, [], [], 0

    def _add(self, vid, x, y, w, h, visual, filters=None):
        self.n += 1
        v = {"$schema": VC_SCHEMA, "name": vid,
             "position": {"x": round(x), "y": round(y), "z": self.n * 1000, "height": round(h), "width": round(w),
                          "tabOrder": self.n * 1000}, "visual": visual}
        if filters:
            v["filterConfig"] = {"filters": [cat_filter(*fl, i=i) for i, fl in enumerate(filters)]}
        self.visuals.append(v)
        return vid

    def chart(self, vid, vtype, x, y, w, h, roles, title=None, objects=None, labels=None, sort=None, filters=None):
        labels = labels or {}
        visual = {"visualType": vtype,
                  "query": {"queryState": {r: {"projections": [proj(f, labels.get(qref(f))) for f in fs]}
                                           for r, fs in roles.items() if fs}},
                  "drillFilterOtherVisuals": True}
        if sort:
            visual["query"]["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}], "isDefaultSort": False}
        if objects:
            visual["objects"] = objects
        visual["visualContainerObjects"] = {
            "subTitle": [{"properties": {"show": lit(False)}}],
            "title": [{"properties": {"show": lit(bool(title)), **({"text": lit(title)} if title else {})}}]}
        return self._add(vid, x, y, w, h, visual, filters)

    def text(self, vid, x, y, w, h, paragraphs, boxed=False):
        paras = [{"textRuns": [{"value": t, "textStyle": {"fontSize": f"{s}pt", "color": c,
                                                         **({"fontWeight": "bold"} if b else {})}}
                               for t, s, c, b in runs]} for runs in paragraphs]
        vco = {"background": [{"properties": {"show": lit(boxed)}}], "border": [{"properties": {"show": lit(boxed)}}]}
        if boxed:
            vco["padding"] = [{"properties": {"top": lit(14), "bottom": lit(14), "left": lit(18), "right": lit(18)}}]
        return self._add(vid, x, y, w, h, {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": paras}}]},
                                           "visualContainerObjects": vco})

    def header(self, title, sub, tag):
        self.text("title", 32, 18, 1480, 58, [[(title, 22, INK, True)]])
        self.text("tag", 1540, 26, 348, 40, [[(tag, 10, INK2, True)]])
        self.text("conclusion", 32, 76, 1856, 64, [[(sub, 13, INK2, False)]])

    def footer(self, source):
        self.text("footer", 32, 1040, 1856, 32, [[(source + "   ·   " + FOOT, 9, MUTED, False)]])

    def slicer(self, vid, x, y, w, h, field, title, dropdown=True, single=False, filters=None):
        o = {"header": [{"properties": {"show": lit(False)}}]}
        if dropdown:
            o["data"] = [{"properties": {"mode": lit("Dropdown")}}]
        if single:
            o["selection"] = [{"properties": {"singleSelect": lit(True), "strictSingleSelect": lit(True)}}]
        return self.chart(vid, "slicer", x, y, w, h, {"Values": [field]}, title, o, filters=filters)

    def card(self, vid, x, y, w, h, measure, title, size=26, filters=None):
        return self.chart(vid, "card", x, y, w, h, {"Values": [meas(measure)]}, title,
                          {"labels": [{"properties": {"color": color(INK), "fontSize": lit(size)}}],
                           "categoryLabels": [{"properties": {"show": lit(False)}}]}, filters=filters)

    def no_filter(self, source, target):
        self.interactions.append({"source": source, "target": target, "type": "NoFilter"})

    def write(self):
        d = PAGES / self.pid
        if d.exists():
            shutil.rmtree(d)
        (d / "visuals").mkdir(parents=True)
        page = {"$schema": PAGE_SCHEMA, "name": self.pid, "displayName": self.name, "displayOption": "FitToPage",
                "height": 1080, "width": 1920}
        if self.interactions:
            page["visualInteractions"] = self.interactions
        (d / "page.json").write_text(json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8")
        for v in self.visuals:
            (d / "visuals" / v["name"]).mkdir()
            (d / "visuals" / v["name"] / "visual.json").write_text(json.dumps(v, indent=2, ensure_ascii=False),
                                                                    encoding="utf-8")


L, R, TOP, BOT, GAP = 32, 1888, 156, 1028, 24
W = R - L


def cols(n, x0=L, x1=R):
    w = (x1 - x0 - (n - 1) * GAP) / n
    return [(x0 + i * (w + GAP), w) for i in range(n)]


def kpi_row(p, items, y=TOP, h=110, x0=L, x1=R):
    for (x, w), (m, t) in zip(cols(len(items), x0, x1), items):
        p.card("kpi_" + "".join(ch for ch in m if ch.isalnum())[:30], x, y, w, h, m, t)
    return y + h + GAP


D, E, P, S, MK = F["data"], F["elasticity"], F["promo"], F["simulator"], F["markets"]
SRC_DH = (f"Source: dunnhumby 'Breakfast at the Frat' (REAL RETAIL DATA, {D['stores']} US stores, "
          f"{D['weeks']} weeks {D['first_week'][:4]}-{D['last_week'][:4]})")
cats = {c["segment"]: c for c in E["categories"]}
most, least = cats[E["most_elastic"]], cats[E["least_elastic"]]
pt = {r["promo_type"]: r for r in P["by_type"]}
LEVELS_CB = ("Elasticity", "level", ["Category", "Brand"])
PUBLISHED = ("Elasticity", "status", ["Published"])
pages = []

# ======================= 0 Overview =======================
p = Page("a0000000000000000001", "Overview")
p.text("title", 32, 18, 1480, 58, [[("Lingaro RGM pricing product: prototype on real retail data", 22, INK, True)]])
p.text("tag", 1540, 26, 348, 40, [[("OVERVIEW", 10, INK2, True)]])
p.text("conclusion", 32, 76, 1856, 64, [[(
    "Price elasticity, promotion effectiveness and price-pack checks for an FMCG portfolio, packaged as a "
    "Power BI product with user stories and business rules. Built the way an RGM product team would hand it to a market.",
    13, INK2, False)]])
heroes = [(f"{most['elasticity']:.1f}", f"price elasticity of {most['segment']}, the most price-sensitive category "
           f"({least['segment']}: {least['elasticity']:.1f})", "REAL RETAIL DATA · ELASTICITY"),
          (pct(P["best_uplift"], sign=True), f"volume uplift of {P['best_uplift_type']} weeks vs baseline", "REAL RETAIL DATA · PROMOTIONS"),
          (f"{P['brand_mechanics_paying_back']} / {P['brand_mechanics']}", "brand x mechanic combinations that pay back "
           "at an assumed 30% margin", "REAL DATA + ASSUMED MARGIN"),
          (pct(S["profit_pct"], 1, True), f"gross profit if {S['segment'].split(' | ')[1]} ({S['segment'].split(' | ')[0]}) "
           f"prices go up 5% (volume {pct(S['volume_pct'], 1, True)})", "MODEL · SIMULATOR")]
for i, ((x, w), (num, txt, tag)) in enumerate(zip(cols(4), heroes)):
    p.text(f"hero{i+1}", x, TOP, w, 240, [[(tag, 10, INK2, True)], [(num, 40, INK, True)], [(txt, 14, INK2, False)]], boxed=True)
y2 = TOP + 240 + GAP
(x1, w1), (x2, w2) = cols(2)
BH = 410
p.text("questions", x1, y2, w1, BH, [
    [("Business questions", 20, INK, True)], [("", 10, INK, False)],
    [("1 · Elasticity   ", 15, BLUE, True), ("How price-sensitive is each category, brand and product?", 15, INK, False)],
    [("2 · Promotions   ", 15, BLUE, True), ("Which mechanics create incremental volume, and which pay back?", 15, INK, False)],
    [("3 · Price-pack   ", 15, BLUE, True), ("Is the price per ounce consistent across pack sizes?", 15, INK, False)],
    [("4 · Scenarios   ", 15, BLUE, True), ("What happens to volume, revenue and profit if price moves by x%?", 15, INK, False)],
    [("5 · Scale   ", 15, BLUE, True), ("Does the same method hold market by market?", 15, INK, False)],
    [("", 10, INK, False)],
    [("Recommendation: ", 15, INK, True), ("test price increases where elasticity is low, move trade spend from "
      "TPR-only cuts to feature + display events, fix inverted pack ladders, and roll the template out market by market.", 15, INK2, False)],
], boxed=True)
p.text("data", x2, y2, w2, BH, [
    [("Data & methods", 20, INK, True)], [("", 10, INK, False)],
    [("REAL RETAIL DATA   ", 12, INK2, True), (f"dunnhumby 'Breakfast at the Frat': {D['rows']:,} store-product-weeks, "
      f"{D['products']} products, {D['stores']} stores, {D['categories']} categories.", 15, INK, False)],
    [("PUBLIC DATA   ", 12, INK2, True), ("Lingaro website (facts, dated) and Eurostat HICP food inflation.", 15, INK, False)],
    [("SIMULATED   ", 12, INK2, True), ("NielsenIQ / Circana-style market shares and competitor prices (seed 42).", 15, INK, False)],
    [("", 10, INK, False)],
    [("SQL   ", 12, INK2, True), ("DuckDB: promo baseline with window functions, hierarchy roll-ups, PPA, data quality.", 15, INK, False)],
    [("Python   ", 12, INK2, True), ("log-log OLS (statsmodels) with store x product and month effects; CI and publish rules.", 15, INK, False)],
    [("Power BI   ", 12, INK2, True), ("star schema, 41 DAX measures, what-if simulator.", 15, INK, False)],
], boxed=True)
y3 = y2 + BH + GAP
p.text("howto", L, y3, W, BOT - y3, [
    [("How to read this report", 15, INK, True)],
    [("Titles  ", 12, INK2, True), ("state the conclusion.    ", 13, INK, False),
     ("Tags  ", 12, INK2, True), ("REAL RETAIL DATA / PUBLIC / SIMULATED mark the source.    ", 13, INK, False),
     ("Elasticity  ", 12, INK2, True), ("-1.8 = +1% price, about -1.8% units. It is a correlation on history, not an experiment.    ", 13, INK, False),
     ("Margins  ", 12, INK2, True), ("are ASSUMED (30% of regular price) and can be changed in the slicer.", 13, INK, False)],
], boxed=True)
p.footer("Sources and licences: data/SOURCES.md")
pages.append(p)

# ======================= 1 Price elasticity =======================
p = Page("a0000000000000000002", "1 · Price elasticity")
p.header(f"{most['segment']} is the most price-sensitive category ({most['elasticity']:.1f}); "
         f"{least['segment']} the least ({least['elasticity']:.1f})",
         "Elasticity = % change in units for +1% price, from a log-log regression with feature, display, store x product "
         "and month controls. Bars show the estimate, the table its 95% interval. Only rows passing business rule BR-06 are 'Published'.",
         "REAL RETAIL DATA")
y = kpi_row(p, [("Published Elasticities", "Published elasticities (category, brand, product)"),
                ("Segments", "Segments estimated (all levels)"), ("Revenue L52W", "Revenue, last 52 weeks"),
                ("Promo Revenue Share", "Revenue sold on promotion")])
(xa, wa), (xb, wb) = cols(2)
h = 330
el_m = meas("Avg Elasticity")
p.chart("elCategory", "clusteredBarChart", xa, y, wa, h, {"Category": [C("Elasticity", "segment")], "Y": [el_m]},
        "Elasticity by category (more negative = more price-sensitive; dashed = -1, revenue-neutral)",
        {"dataPoint": [{"properties": {"fill": color(BLUE)}}],
         "labels": [{"properties": {"show": lit(True), "color": color(INK)}}],
         "y1AxisReferenceLine": [ref_line(-1, "-1")]},
        labels={qref(el_m): "Elasticity"}, sort=(el_m, "Ascending"), filters=[("Elasticity", "level", ["Category"])])
p.chart("elBrand", "clusteredBarChart", xb, y, wb, h, {"Category": [C("Elasticity", "segment")], "Y": [el_m]},
        "Elasticity by brand (published only)",
        {"dataPoint": [{"properties": {"fill": color(BLUE)}}],
         "labels": [{"properties": {"show": lit(True), "color": color(INK)}}],
         "y1AxisReferenceLine": [ref_line(-1, "-1")]},
        labels={qref(el_m): "Elasticity"}, sort=(el_m, "Ascending"),
        filters=[("Elasticity", "level", ["Brand"]), PUBLISHED])
y += h + GAP
tcols = ["segment", "level", "n_obs", "elasticity", "ci_low", "ci_high", "status", "plain_english"]
lab = {"Elasticity.segment": "Segment", "Elasticity.level": "Level", "Elasticity.n_obs": "Rows",
       "Elasticity.elasticity": "Elasticity", "Elasticity.ci_low": "95% CI low", "Elasticity.ci_high": "95% CI high",
       "Elasticity.status": "Status (BR-06)", "Elasticity.plain_english": "In plain English"}
p.chart("elTable", "tableEx", L, y, W * 0.66, BOT - y, {"Values": [C("Elasticity", c) for c in tcols]},
        "Estimates with 95% interval, sample size and publication status", table_style(), labels=lab,
        filters=[LEVELS_CB])
xs = L + W * 0.66 + GAP
p.chart("elSplit", "tableEx", xs, y, R - xs, BOT - y,
        {"Values": [C("Elasticity Split", c) for c in ["category", "component", "elasticity", "ci_low", "ci_high"]]},
        "Regular price vs promo price cut (shoppers react more to short cuts)", table_style(),
        labels={"Elasticity Split.category": "Category", "Elasticity Split.component": "Price component",
                "Elasticity Split.elasticity": "Elasticity", "Elasticity Split.ci_low": "CI low", "Elasticity Split.ci_high": "CI high"})
p.footer(SRC_DH + " · Observational estimate: correlation on historical data, not causal")
pages.append(p)

# ======================= 2 Promotions =======================
tpr = pt.get("TPR only", {})
p = Page("a0000000000000000003", "2 · Promotion effectiveness")
p.header(f"{P['best_uplift_type']} lifts volume most ({pct(P['best_uplift'], sign=True)}); TPR-only cuts lift "
         f"{pct(tpr.get('uplift', 0), sign=True)} but rarely pay back",
         "Uplift = promo-week units vs a baseline of clean non-promo weeks (+/-8 weeks, BR-03). ROI = net incremental gross "
         "profit / discount cost, at an ASSUMED margin you can change below. Post-promo dip and cannibalisation shown on the right.",
         "REAL RETAIL DATA + ASSUMED MARGIN")
p.slicer("slicerMargin", L, TOP, 300, 72, C("Margin Assumption", "Margin"), "Assumed margin", single=True)
p.slicer("slicerCategory", L + 300 + GAP, TOP, 420, 72, C("Product", "category"), "Category")
y = TOP + 72 + GAP
y = kpi_row(p, [("Promo Uplift %", "Uplift vs baseline"), ("Promo ROI", "Promo ROI (assumed margin)"),
                ("Post-Promo Dip %", "Week after a promo vs baseline"), ("Avg Discount Depth", "Average discount depth")], y=y)
(xa, wa), (xb, wb) = cols(2)
h = 300
up, roi = meas("Promo Uplift %"), meas("Promo ROI")
p.chart("upliftByType", "clusteredColumnChart", xa, y, wa, h, {"Category": [C("Promo Type", "promo_type")], "Y": [up]},
        "Volume uplift by mechanic", {"dataPoint": [{"properties": {"fill": color(BLUE)}}],
                                      "labels": [{"properties": {"show": lit(True), "color": color(INK)}}]},
        labels={qref(up): "Uplift"}, filters=[("Promo Type", "promo_type", ["No promo"], True)])
p.chart("roiByType", "clusteredColumnChart", xb, y, wb, h, {"Category": [C("Promo Type", "promo_type")], "Y": [roi]},
        "ROI by mechanic (dashed = break-even; Display has almost no discount, so its ROI is not meaningful)",
        {"dataPoint": [{"properties": {"fill": color(BLUE)}}],
         "labels": [{"properties": {"show": lit(True), "color": color(INK)}}],
         "y1AxisReferenceLine": [ref_line(0, "Break-even")]},
        labels={qref(roi): "ROI"}, filters=[("Promo Type", "promo_type", ["No promo", "Display"], True)])
y += h + GAP
pe = ["category", "manufacturer", "promo_type", "promo_weeks", "avg_discount", "uplift", "roi", "share_weeks_paid_back"]
p.chart("promoTable", "tableEx", L, y, W * 0.62, BOT - y, {"Values": [C("Promo Effectiveness", c) for c in pe]},
        "Brand x mechanic at a 30% margin (red = destroys profit, blue = pays back)",
        table_style([bg_rule(C("Promo Effectiveness", "roi"), RED_TINT, BLUE_TINT, NEUTRAL, 0)]),
        labels={"Promo Effectiveness.category": "Category", "Promo Effectiveness.manufacturer": "Brand",
                "Promo Effectiveness.promo_type": "Mechanic", "Promo Effectiveness.promo_weeks": "Promo weeks",
                "Promo Effectiveness.avg_discount": "Avg discount", "Promo Effectiveness.uplift": "Uplift",
                "Promo Effectiveness.roi": "ROI", "Promo Effectiveness.share_weeks_paid_back": "Weeks paid back"})
for s in ("slicerMargin",):
    p.no_filter(s, "promoTable")
xs = L + W * 0.62 + GAP
ch = (BOT - y - GAP) / 2
p.chart("dipTable", "tableEx", xs, y, R - xs, ch, {"Values": [C("Promo Dip", c) for c in ["category", "post_weeks", "dip"]]},
        "Post-promotion dip (first week after a promo)", table_style(),
        labels={"Promo Dip.category": "Category", "Promo Dip.post_weeks": "Weeks", "Promo Dip.dip": "vs baseline"})
p.chart("canTable", "tableEx", xs, y + ch + GAP, R - xs, ch,
        {"Values": [C("Cannibalisation", c) for c in ["category", "context", "vs_baseline"]]},
        "Cannibalisation: non-promoted products vs their baseline", table_style(),
        labels={"Cannibalisation.category": "Category", "Cannibalisation.context": "Context",
                "Cannibalisation.vs_baseline": "vs baseline"})
p.footer(SRC_DH + " · Margin is an assumption (data/ASSUMPTIONS.md); feature/display fees are not in the data")
pages.append(p)

# ======================= 3 Price-pack architecture =======================
pp = F["ppa"]
p = Page("a0000000000000000004", "3 · Price-pack architecture")
n_inv, n_up = pp['inversions'], pp['price_up']
p.header(f"{n_inv} pack{' costs' if n_inv == 1 else 's cost'} more per ounce than a smaller pack of the same brand; "
         f"{n_up} product{' looks' if n_up == 1 else 's look'} under-priced for {'its' if n_up == 1 else 'their'} low sensitivity",
         "Regular (base) price per ounce by pack. A healthy ladder gives bigger packs a lower price per ounce. "
         "Price index 100 = sub-category average. Opportunity combines the ladder check with product elasticity (BR-08, BR-11).",
         "REAL RETAIL DATA")
p.slicer("slicerPpaCat", L, TOP, 420, 72, C("PPA", "category"), "Category")
y = TOP + 72 + GAP
h = 400
sx, sy = agg("PPA", "size_oz", 1), agg("PPA", "base_price_per_oz", 1)
p.chart("ladder", "scatterChart", L, y, W * 0.5, h,
        {"Category": [C("PPA", "description")], "Series": [C("PPA", "manufacturer")], "X": [sx], "Y": [sy]},
        "Pack-price ladder: pack size (oz) vs regular price per oz",
        {"markers": [{"properties": {"markerSize": lit(8)}}],
         "categoryLabels": [{"properties": {"show": lit(False)}}]},
        labels={qref(sx): "Pack size (oz)", qref(sy): "Price per oz"})
idx = agg("PPA", "price_index_per_oz", 1)
xb = L + W * 0.5 + GAP
p.chart("index", "clusteredBarChart", xb, y, R - xb, h, {"Category": [C("PPA", "description")], "Y": [idx]},
        "Price index per oz vs sub-category average (dashed = 100)",
        {"dataPoint": [{"properties": {"fill": color(BLUE)}}],
         "y1AxisReferenceLine": [ref_line(100, "Average")]}, labels={qref(idx): "Price index"}, sort=(idx, "Descending"))
y += h + GAP
pc = ["category", "manufacturer", "description", "size_oz", "base_price_per_oz", "price_index_per_oz", "elasticity",
      "inverted_vs", "inversion_premium", "opportunity"]
p.chart("ppaTable", "tableEx", L, y, W, BOT - y, {"Values": [C("PPA", c) for c in pc]},
        "Pack-level checks and opportunity", table_style(),
        labels={"PPA.category": "Category", "PPA.manufacturer": "Brand", "PPA.description": "Product",
                "PPA.size_oz": "Oz", "PPA.base_price_per_oz": "Price/oz", "PPA.price_index_per_oz": "Index",
                "PPA.elasticity": "Elasticity", "PPA.inverted_vs": "Inverted vs smaller pack",
                "PPA.inversion_premium": "Premium/oz", "PPA.opportunity": "Opportunity"})
p.footer(SRC_DH + " · Liquids converted to fluid ounces")
pages.append(p)

# ======================= 4 Scenario simulator =======================
seg_b, seg_c = S["segment"].split(" | ")[1], S["segment"].split(" | ")[0]
p = Page("a0000000000000000005", "4 · Scenario simulator")
p.header(f"+5% on {seg_b} ({seg_c}): volume {pct(S['volume_pct'], 1, True)}, revenue {pct(S['revenue_pct'], 1, True)}, "
         f"gross profit {pct(S['profit_pct'], 1, True)}",
         "Pick one segment with a published elasticity, a price change (capped at +/-10%, BR-10) and a margin assumption. "
         "Ranges come from the 95% interval of the elasticity. Volume = (1+p)^e; revenue = (1+p)^(1+e); profit = (1+p)^e x (m+p)/m.",
         "REAL DATA + MODEL")
sw = 520
p.slicer("slicerSegment", L, TOP, sw, BOT - TOP, C("Elasticity", "segment"), "Segment (published only)",
         dropdown=False, single=True, filters=[LEVELS_CB, PUBLISHED])
x0 = L + sw + GAP
(xa, wa), (xb, wb) = cols(2, x0, R)
p.slicer("slicerPrice", xa, TOP, wa, 72, C("Price Change", "Price Change"), "Price change", single=True)
p.slicer("slicerMargin", xb, TOP, wb, 72, C("Margin Assumption", "Margin"), "Assumed margin", single=True)
y = TOP + 72 + GAP
y = kpi_row(p, [("Sim Volume %", "Volume change"), ("Sim Revenue %", "Revenue change"),
                ("Sim Gross Profit %", "Gross profit change"), ("Sim Gross Profit Change", "Gross profit, $ per year")],
            y=y, x0=x0)
y = kpi_row(p, [("Sim Volume % Low", "Volume, worst case"), ("Sim Volume % High", "Volume, best case"),
                ("Sim Gross Profit % Low", "Profit, worst case"), ("Sim Gross Profit % High", "Profit, best case")],
            y=y, h=100, x0=x0)
p.card("status", x0, y, R - x0, 70, "Sim Status", "", size=12)
y += 70 + GAP
gv, gr, gp = agg("Scenario Grid", "volume_pct"), agg("Scenario Grid", "revenue_pct"), agg("Scenario Grid", "profit_pct")
p.chart("curve", "lineChart", x0, y, R - x0, BOT - y, {"Category": [C("Scenario Grid", "price_change")], "Y": [gv, gr, gp]},
        "Selected segment: volume, revenue and gross profit (30% margin) across price changes",
        {"dataPoint": [series_color(gv, GREY), series_color(gr, SEQ["250"]), series_color(gp, SEQ["650"])],
         "y1AxisReferenceLine": [ref_line(0, "0")]},
        labels={qref(gv): "Volume %", qref(gr): "Revenue %", qref(gp): "Gross profit %"})
for t in ("curve",):
    p.no_filter("slicerPrice", t)
    p.no_filter("slicerMargin", t)
p.footer(SRC_DH + " · Elasticity is observational; scenarios assume competitors and retailers do not react")
pages.append(p)

# ======================= 5 Market view (SIMULATED) =======================
msim = F["market_sim"]
p = Page("a0000000000000000006", "5 · Market view (simulated)")
p.header("How external panel data would plug in: share, competitor price and distribution",
         "NielsenIQ / Circana data is paid, so this page uses SIMULATED market data calibrated on the retailer's real sales "
         "(seed 42). It demonstrates the model and measures, not a market reading. Do not quote these numbers.",
         "SIMULATED")
p.slicer("slicerMktCat", L, TOP, 420, 72, C("Brand", "category"), "Category")
y = TOP + 72 + GAP
y = kpi_row(p, [("Market Value Share (SIM)", "Market value share (SIMULATED)"),
                ("Retailer Value Share", "Share inside this retailer (real)"),
                ("Price Index vs Competitors (SIM)", "Price index vs competitors (SIMULATED)"),
                ("Weighted Distribution (SIM)", "Weighted distribution (SIMULATED)")], y=y)
(xa, wa), (xb, wb) = cols(2)
h = BOT - y
ms, rs = meas("Market Value Share (SIM)"), meas("Retailer Value Share")
p.chart("shares", "clusteredBarChart", xa, y, wa, h, {"Category": [C("Brand", "manufacturer")], "Y": [ms, rs]},
        "Market share (SIMULATED, blue) vs share inside the retailer (real, grey)",
        {"dataPoint": [series_color(ms, BLUE), series_color(rs, GREY)]},
        labels={qref(ms): "Market share (SIM)", qref(rs): "Retailer share"})
pi = meas("Price Index vs Competitors (SIM)")
p.chart("priceIndex", "lineChart", xb, y, wb, h,
        {"Category": [C("Market Sim", "quarter")], "Y": [pi], "Series": [C("Brand", "manufacturer")]},
        "Price index vs competitors by quarter (SIMULATED, 100 = parity)",
        {"y1AxisReferenceLine": [ref_line(100, "Parity")]}, labels={qref(pi): "Price index"})
p.footer("SIMULATED data generated by src/simulate_market.py - not NielsenIQ, Circana, Lingaro or client data")
pages.append(p)

# ======================= 6 One method, many markets =======================
p = Page("a0000000000000000007", "6 · One method, many markets")
STATE = {"OH": "Ohio", "TX": "Texas", "IN": "Indiana", "KY": "Kentucky"}
_ms = MK.get("more_sensitive_everywhere")
_oth = " and ".join(STATE.get(m, m) for m in MK.get("published_markets", []) if m != _ms)
p.header(f"Same code, same rules: {STATE.get(_ms, _ms)} shoppers are more price-sensitive than {_oth} in all "
         f"{MK['n_categories']} categories" if _ms else
         f"Same code, same rules, {len(D['states'])} markets: {MK['published']} of {MK['segments']} market x category "
         "elasticities pass the publication rule",
         "Each US state stands in for a market. The pipeline, the business rules and this report are reused unchanged; "
         "only the data filter changes. What varies: the size of the elasticity. What stays: the method, the rules, the measures.",
         "REAL RETAIL DATA")
mk_f = [("Elasticity", "level", ["Market"])]
p.chart("mktMatrix", "pivotTable", L, TOP, W * 0.45, 420,
        {"Rows": [C("Elasticity", "category")], "Columns": [C("Elasticity", "market")], "Values": [el_m]},
        "Elasticity by category and market",
        table_style([bg_rule(el_m, SEQ["450"], "#FCFCFB")], matrix=True),
        labels={"Elasticity.category": "Category", "Elasticity.market": "Market", qref(el_m): "Elasticity"}, filters=mk_f)
xb = L + W * 0.45 + GAP
p.chart("mktBars", "clusteredColumnChart", xb, TOP, R - xb, 420,
        {"Category": [C("Elasticity", "category")], "Y": [el_m], "Series": [C("Elasticity", "market")]},
        "Elasticity by category, one bar per market", labels={qref(el_m): "Elasticity"}, filters=mk_f)
y = TOP + 420 + GAP
mc = ["market", "category", "n_obs", "n_stores", "elasticity", "ci_low", "ci_high", "status", "status_reason"]
p.chart("mktTable", "tableEx", L, y, W, BOT - y, {"Values": [C("Elasticity", c) for c in mc]},
        "Market x category estimates and publication status", table_style(),
        labels={"Elasticity.market": "Market", "Elasticity.category": "Category", "Elasticity.n_obs": "Rows",
                "Elasticity.n_stores": "Stores", "Elasticity.elasticity": "Elasticity", "Elasticity.ci_low": "CI low",
                "Elasticity.ci_high": "CI high", "Elasticity.status": "Status", "Elasticity.status_reason": "Reason"},
        filters=mk_f)
p.footer(SRC_DH + " · Markets = store states in the dataset")
pages.append(p)

# ======================= 7 Data quality =======================
p = Page("a0000000000000000008", "7 · Data quality")
p.header(f"{pct(D['dq_ok_share'], 1)} of rows pass every check; flagged rows are kept but excluded from models",
         "Checks run in SQL (sql/05_data_quality.sql) before any model: missing or extreme prices, price above base price, "
         "zero units, unknown stores, gaps in the weekly history, duplicate store records, products phasing out (BR-07).",
         "REAL RETAIL DATA")
y = kpi_row(p, [("Rows Passing Checks %", "Rows passing every check"), ("Flagged Rows", "Flagged rows"),
                ("Units", "Units (all rows)"), ("Revenue", "Revenue (all rows)")])
(xa, wa), (xb, wb) = cols(2)
p.chart("dqTable", "tableEx", xa, y, wa, BOT - y, {"Values": [C("Data Quality", c) for c in ["check_name", "rows_hit", "note"]]},
        "Checks and rows hit", table_style(),
        labels={"Data Quality.check_name": "Check", "Data Quality.rows_hit": "Rows", "Data Quality.note": "Handling"})
seg = meas("Segments")
p.chart("statusBars", "clusteredBarChart", xb, y, wb, BOT - y,
        {"Category": [C("Elasticity", "level")], "Y": [seg], "Series": [C("Elasticity", "status")]},
        "Elasticity segments by publication status (BR-06)", labels={qref(seg): "Segments"})
p.footer(SRC_DH)
pages.append(p)

# ---------- write ----------
PAGES.mkdir(parents=True, exist_ok=True)
keep = {pg.pid for pg in pages}
for d in PAGES.iterdir():
    if d.is_dir() and d.name not in keep:
        shutil.rmtree(d)
for pg in pages:
    pg.write()
(PAGES / "pages.json").write_text(json.dumps({"$schema": PAGES_SCHEMA, "pageOrder": [pg.pid for pg in pages],
                                              "activePageName": pages[0].pid}, indent=2), encoding="utf-8")
print("pages:", [(pg.name.encode("ascii", "replace").decode(), len(pg.visuals)) for pg in pages])
