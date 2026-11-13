"""Build the PDF report: HTML pages + matplotlib charts -> PDF with headless Edge (or Chrome).

Every number comes from data/output/findings.json or from the output tables; nothing is typed by hand.
Output: docs/Lingaro_RGM_CaseStudy.pdf, docs/report.html, docs/img/*.png
Power BI screenshots, if present in docs/img/pbi_*.png, are added to the simulator page and an appendix.

Usage:  python src/build_report.py
"""
import html
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from pypdf import PdfReader, PdfWriter  # noqa: E402

OUT, PUB, DOCS = Path("data/output"), Path("data/public"), Path("docs")
IMG = DOCS / "img"
F = json.loads((OUT / "findings.json").read_text(encoding="utf-8"))
D, E, P, S, MK = F["data"], F["elasticity"], F["promo"], F["simulator"], F["markets"]

# palette (validated reference palette, light mode): blue = data, grey = comparison, red = alert
INK, INK2, MUTED, GRID = "#0B0B0B", "#52514E", "#898781", "#E1E0D9"
BLUE, BLUE_L, BLUE_D, GREY, RED = "#2A78D6", "#86B6EF", "#104281", "#B4B2A9", "#D03B3B"
CAT = ["#2A78D6", "#EB6834", "#1BAF7A", "#EDA100", "#E87BA4", "#008300"]   # fixed order, never cycled
FOOT = "Independent case study based on public data · not affiliated with or endorsed by Lingaro"
AI_NOTE = ("AI-assisted workflow: I used Claude, mainly to write scripts faster. I drove the project: I defined the "
           "questions, chose and validated the data sources, made the analytical decisions and checked every result.")

plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 10, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "legend.frameon": False, "figure.dpi": 100, "savefig.dpi": 200})


def pct(x, d=0, sign=False):
    return f"{x * 100:+.{d}f}%" if sign else f"{x * 100:.{d}f}%"


def esc(s):
    return html.escape(str(s))


def save(fig, name):
    IMG.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMG / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return f"img/{name}"


def short(seg):
    return seg.replace("Oral Hygiene Products", "Oral hygiene").replace("Cold Cereal", "Cereal")


# ------------------------------------------------------------------ charts
def chart_hicp():
    h = pd.read_csv(PUB / "hicp_annual.csv")
    eu = h[h["geo"] == "EU27_2020"]
    food = eu[eu["coicop"] == "CP011"].set_index("year")["rate_pct"]
    allit = eu[eu["coicop"] == "CP00"].set_index("year")["rate_pct"]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    x = np.arange(len(food))
    ax.bar(x - 0.2, allit.values, 0.38, color=GREY, label="All items")
    ax.bar(x + 0.2, food.values, 0.38, color=BLUE, label="Food")
    for i, v in enumerate(food.values):
        ax.text(i + 0.2, v + 0.3, f"{v:.1f}", ha="center", fontsize=8, color=INK)
    ax.set_xticks(x, food.index)
    ax.set_ylabel("Annual average rate, %")
    ax.legend(loc="upper left")
    ax.grid(axis="x", visible=False)
    a = save(fig, "hicp_eu.png")

    cum = h[(h["coicop"] == "CP011") & h["year"].isin([2020, 2025])].pivot(index="geo", columns="year", values="index_2015")
    cum = ((cum[2025] / cum[2020] - 1) * 100).sort_values()
    names = {"EU27_2020": "EU27", "DE": "Germany", "FR": "France", "IT": "Italy", "ES": "Spain", "PL": "Poland", "NL": "Netherlands"}
    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    colors = [BLUE if g == "EU27_2020" else GREY for g in cum.index]
    ax.barh([names[g] for g in cum.index], cum.values, color=colors, height=0.6)
    for i, v in enumerate(cum.values):
        ax.text(v + 0.5, i, f"+{v:.0f}%", va="center", fontsize=8, color=INK)
    ax.set_xlabel("Food price index, 2025 vs 2020")
    ax.grid(axis="y", visible=False)
    b = save(fig, "hicp_countries.png")
    return a, b


def chart_elasticity():
    el = pd.read_csv(OUT / "elasticity.csv")
    out = []
    for level, name, fs in [("Category", "el_category.png", (6.4, 3.2)), ("Brand", "el_brand.png", (7.6, 4.6))]:
        d = el[(el["level"] == level) & el["elasticity"].notna()].sort_values("elasticity", ascending=False)
        if level == "Brand":
            d = d[d["status"].isin(["Published", "Review"])]
        fig, ax = plt.subplots(figsize=fs)
        y = np.arange(len(d))
        col = [BLUE if s == "Published" else GREY for s in d["status"]]
        ax.errorbar(d["elasticity"], y, xerr=[d["elasticity"] - d["ci_low"], d["ci_high"] - d["elasticity"]],
                    fmt="none", ecolor=MUTED, elinewidth=1.2, capsize=3)
        ax.scatter(d["elasticity"], y, color=col, s=40, zorder=3)
        ax.axvline(-1, color=INK2, ls="--", lw=1)
        ax.axvline(0, color=GRID, lw=1)
        ax.set_yticks(y, [short(s) for s in d["segment"]], fontsize=8.5)
        for yi, (e, hi) in enumerate(zip(d["elasticity"], d["ci_high"])):
            ax.text(hi + 0.06, yi, f"{e:.2f}", va="center", fontsize=8, color=INK)
        ax.set_xlabel("Price elasticity with 95% interval (dashed = -1)")
        ax.grid(axis="y", visible=False)
        out.append(save(fig, name))
    return out


def chart_promo():
    summ = pd.read_csv(OUT / "promo_summary.csv")
    eff = pd.read_csv(OUT / "promo_effectiveness.csv")
    order = ["TPR only", "Display", "Feature", "Feature + Display"]
    g = eff.groupby("promo_type")[["units", "baseline_units"]].sum()
    up = (g["units"] / g["baseline_units"] - 1).reindex(order).dropna()
    fig, ax = plt.subplots(figsize=(5.4, 6.6))
    ax.bar(up.index, up.values * 100, color=BLUE, width=0.55)
    for i, v in enumerate(up.values):
        ax.text(i, v * 100 + 2, f"+{v * 100:.0f}%", ha="center", fontsize=9, color=INK)
    ax.set_ylabel("Volume uplift vs baseline, %")
    ax.grid(axis="x", visible=False)
    a = save(fig, "promo_uplift.png")

    t = summ.groupby(["margin_assumption", "promo_type"]).apply(
        lambda x: x["net_incr_profit"].sum() / x["discount_cost"].sum(), include_groups=False).unstack(0)
    t = t.reindex(order).dropna(how="all")
    fig, ax = plt.subplots(figsize=(5.8, 6.6))
    x = np.arange(len(t))
    shades = {0.2: BLUE_L, 0.3: BLUE, 0.4: BLUE_D}
    for i, m in enumerate(t.columns):
        ax.bar(x + (i - 1) * 0.26, t[m].values * 100, 0.24, color=shades.get(round(m, 1), BLUE), label=f"{m:.0%} margin")
    ax.axhline(0, color=INK2, ls="--", lw=1)
    ax.set_xticks(x, t.index)
    ax.set_ylabel("ROI = net incremental profit / discount cost, %")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(axis="x", visible=False)
    b = save(fig, "promo_roi.png")
    return a, b


def chart_ppa():
    ppa = pd.read_csv(OUT / "ppa.csv")
    cats = sorted(ppa["category"].unique())
    fig, axes = plt.subplots(1, len(cats), figsize=(15, 3.4), sharey=False)
    axes = np.atleast_1d(axes)
    for ax, c in zip(axes, cats):
        d = ppa[ppa["category"] == c]
        inv = d["inverted_vs"].fillna("") != ""
        ax.scatter(d.loc[~inv, "size_oz"], d.loc[~inv, "base_price_per_oz"], color=BLUE, s=28, label="Consistent")
        ax.scatter(d.loc[inv, "size_oz"], d.loc[inv, "base_price_per_oz"], color=RED, s=40, marker="D", label="Inverted ladder")
        ax.set_title(short(c), fontsize=10, color=INK, loc="left")
        ax.set_xlabel("Pack size (oz)")
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:.2f}"))
    axes[0].set_ylabel("Regular price per oz")
    axes[-1].legend(loc="upper right", fontsize=8)
    return save(fig, "ppa_ladder.png")


def chart_simulator():
    grid = pd.read_csv(OUT / "scenario_grid.csv")
    el = pd.read_csv(OUT / "elasticity.csv")
    sid = el.loc[el["segment"] == S["segment"], "segment_id"].iloc[0]
    g = grid[grid["segment_id"] == sid].sort_values("price_change")
    fig, ax = plt.subplots(figsize=(6.6, 3.8))
    x = g["price_change"] * 100
    for k, c, lab in [("volume", GREY, "Volume"), ("revenue", BLUE_L, "Revenue"), ("profit", BLUE_D, "Gross profit (30% margin)")]:
        ax.fill_between(x, g[f"{k}_pct_low"] * 100, g[f"{k}_pct_high"] * 100, color=c, alpha=0.25, lw=0)
        ax.plot(x, g[f"{k}_pct"] * 100, color=c, lw=2, label=lab)
    ax.axhline(0, color=INK2, lw=1, ls="--")
    ax.axvline(5, color=MUTED, lw=0.8, ls=":")
    ax.set_xlabel("Price change, %  (capped at ±10%, BR-10)")
    ax.set_ylabel("Change vs last 52 weeks, %")
    ax.legend(loc="upper left", fontsize=8)
    return save(fig, "sim_curves.png")


def chart_market():
    ms = pd.read_csv(OUT / "market_sim.csv")
    q = ms[ms["quarter"] == ms["quarter"].max()].sort_values(["category", "market_value_share"])
    lab = [short(f"{c} | {m}") for c, m in zip(q["category"], q["manufacturer"])]
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    y = np.arange(len(q))
    ax.barh(y + 0.2, q["market_value_share"] * 100, 0.38, color=BLUE, label="Market share (SIMULATED)")
    ax.barh(y - 0.2, q["retailer_value_share"] * 100, 0.38, color=GREY, label="Share inside the retailer (real)")
    ax.set_yticks(y, lab, fontsize=8)
    ax.set_xlabel(f"Value share within category, %  ({F['market_sim']['quarter']})")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(axis="y", visible=False)
    a = save(fig, "market_share.png")
    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    q2 = q.sort_values("price_index_vs_competitors")
    col = [RED if v > 105 else BLUE if v < 95 else GREY for v in q2["price_index_vs_competitors"]]
    ax.barh([short(f"{c} | {m}") for c, m in zip(q2["category"], q2["manufacturer"])],
            q2["price_index_vs_competitors"] - 100, color=col, height=0.6)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_xlabel("Price index vs competitors - 100 (SIMULATED)")
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(axis="y", visible=False)
    b = save(fig, "market_price_index.png")
    return a, b


def chart_markets():
    el = pd.read_csv(OUT / "elasticity.csv")
    mk = el[(el["level"] == "Market") & el["elasticity"].notna()]
    pooled = el[el["level"] == "Category"].set_index("segment")
    cats = sorted(mk["category"].unique())
    markets = sorted(mk["market"].unique())
    fig, ax = plt.subplots(figsize=(11, 3.6))
    width = 0.8 / max(len(markets), 1)
    for j, m in enumerate(markets):
        d = mk[mk["market"] == m].set_index("category").reindex(cats)
        x = np.arange(len(cats)) - 0.4 + width * (j + 0.5)
        ok = d["status"] == "Published"
        ax.errorbar(x, d["elasticity"], yerr=[d["elasticity"] - d["ci_low"], d["ci_high"] - d["elasticity"]],
                    fmt="none", ecolor=CAT[j % len(CAT)], elinewidth=1, capsize=2, alpha=0.7)
        ax.scatter(x[ok.values], d["elasticity"][ok], color=CAT[j % len(CAT)], s=36, zorder=3, label=m)
        ax.scatter(x[~ok.values], d["elasticity"][~ok], facecolor="white", edgecolor=CAT[j % len(CAT)], s=36, zorder=3)
    for i, c in enumerate(cats):
        if c in pooled.index:
            ax.hlines(pooled.loc[c, "elasticity"], i - 0.42, i + 0.42, color=INK2, ls="--", lw=1)
    ax.set_xticks(np.arange(len(cats)), [short(c) for c in cats])
    ax.set_ylabel("Elasticity, 95% interval")
    ax.legend(title="Market (state)  ·  hollow = not published  ·  dashed = all markets", fontsize=8,
              title_fontsize=8, ncol=len(markets), loc="lower center", bbox_to_anchor=(0.5, -0.32))
    ax.grid(axis="x", visible=False)
    return save(fig, "markets.png")


# ------------------------------------------------------------------ html helpers
def page(n, title, sub, tag, body, source):
    tag_html = f'<div class="tag">{esc(tag)}</div>' if tag else ""
    return f"""<section class="page"><header><div><h1>{esc(title)}</h1><p class="sub">{esc(sub)}</p></div>{tag_html}</header>
<main>{body}</main><footer><span>{esc(source)}</span><span>{esc(FOOT)} · {n}</span></footer></section>"""


def card(inner, cls=""):
    return f'<div class="card {cls}">{inner}</div>'


def img(src, cap=None):
    c = f"<h3>{esc(cap)}</h3>" if cap else ""
    return f'{c}<img src="{src}">'


def table(df, fmt=None):
    fmt = fmt or {}
    head = "".join(f"<th>{esc(c)}</th>" for c in df.columns)
    rows = "".join("<tr>" + "".join(f"<td>{esc(fmt.get(c, lambda v: v)(v))}</td>" for c, v in r.items()) + "</tr>"
                   for _, r in df.iterrows())
    return f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"


CSS = """
@page { size: 1600px 900px; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: 'Segoe UI', Arial, sans-serif; color: #0B0B0B; background: #F4F4F2; }
.page { width: 1600px; height: 900px; padding: 34px 44px 20px; background: #F4F4F2; display: flex; flex-direction: column;
        page-break-after: always; overflow: hidden; }
header { display: flex; justify-content: space-between; align-items: flex-start; gap: 30px; }
h1 { font-size: 29px; margin: 0 0 6px; font-weight: 700; line-height: 1.15; }
.sub { font-size: 15px; color: #52514E; margin: 0; max-width: 1290px; line-height: 1.4; }
.tag { font-size: 12px; font-weight: 700; color: #52514E; letter-spacing: .06em; white-space: nowrap; padding-top: 8px; }
main { flex: 1; display: grid; gap: 18px; margin-top: 20px; min-height: 0; }
footer { display: flex; justify-content: space-between; font-size: 11px; color: #898781; margin-top: 12px; gap: 20px; }
.card { background: #FCFCFB; border: 1px solid #E1E0D9; border-radius: 8px; padding: 16px 20px; min-height: 0; overflow: hidden; }
.card h3 { font-size: 14px; margin: 0 0 8px; font-weight: 600; }
.card img { width: 100%; max-height: 100%; object-fit: contain; }
.card p, .card li { font-size: 14px; line-height: 1.45; color: #0B0B0B; margin: 0 0 6px; }
.card ul { margin: 0; padding-left: 18px; }
.k { font-size: 11px; font-weight: 700; color: #52514E; letter-spacing: .05em; text-transform: uppercase; }
.big { font-size: 40px; font-weight: 700; margin: 6px 0 4px; }
.muted { color: #52514E; }
.blue { color: #2A78D6; font-weight: 700; }
table { border-collapse: collapse; width: 100%; font-size: 12.5px; }
th { text-align: left; color: #52514E; font-weight: 600; border-bottom: 1px solid #0B0B0B; padding: 4px 6px; }
td { padding: 4px 6px; border-bottom: 1px solid #EEEDE8; vertical-align: top; }
.g2 { grid-template-columns: 1fr 1fr; } .g3 { grid-template-columns: 1fr 1fr 1fr; } .g4 { grid-template-columns: repeat(4, 1fr); }
.g64 { grid-template-columns: 1.5fr 1fr; } .g46 { grid-template-columns: 1fr 1.5fr; }
.rows { grid-template-rows: auto 1fr; }
.note { background: #FCFCFB; border-left: 3px solid #2A78D6; }
"""


def build():
    hicp_a, hicp_b = chart_hicp()
    el_cat, el_brand = chart_elasticity()
    pr_up, pr_roi = chart_promo()
    ppa_png = chart_ppa()
    sim_png = chart_simulator()
    mk_a, mk_b = chart_market()
    mkts_png = chart_markets()
    facts = pd.read_csv(PUB / "lingaro_facts.csv").set_index("fact_id")
    cats = E["categories"]
    most, least = cats[0], cats[-1]
    pt = {r["promo_type"]: r for r in P["by_type"]}
    tpr = pt.get("TPR only", {})
    fd = pt.get("Feature + Display", {})
    pp = F["ppa"]
    eu = F["eurostat"]
    pages = []
    brand_seg = S["segment"].split(" | ")
    pub_n = E["published"].get("Published", 0)
    STATE = {"OH": "Ohio", "TX": "Texas", "IN": "Indiana", "KY": "Kentucky"}
    def brand_words(seg):   # "Bag Snacks | Shultz" -> "Shultz bag snacks"
        cat, man = seg.split(" | ")
        return f"{'private-label' if man == 'Private Label' else man} {short(cat).lower()}"
    low_brands = [brand_words(b) for b in S.get("low_sensitivity_brands", [])]
    low_txt = ", ".join(low_brands) if low_brands else "the least sensitive brands"
    inv = (pp.get("worst_inversion") or [None])[0]
    po_brands = D.get("phase_out_brands", [])
    po_txt = " and ".join(po_brands)
    unpub = [STATE.get(m, m) for m in MK.get("unpublished_markets", [])]

    # ---- 0 Overview
    heroes = [
        (f"{most['elasticity']:.1f}", f"price elasticity of {most['segment']}: the most price-sensitive category "
         f"({least['segment']} {least['elasticity']:.1f})", "Real retail data · p.4"),
        (pct(fd.get('uplift', P['best_uplift']), sign=True), "volume uplift when feature and display run together, "
         f"vs {pct(tpr.get('uplift', 0), sign=True)} for a price cut alone", "Real retail data · p.5"),
        (f"{P['brand_mechanics_paying_back']}/{P['brand_mechanics']}", "brand x mechanic combinations that pay back at an "
         "assumed 30% margin", "Real data + assumed margin · p.5"),
        (pct(S["profit_pct"], 1, True), f"gross profit for +5% on {brand_seg[1]} {short(brand_seg[0]).lower()} "
         f"(volume {pct(S['volume_pct'], 1, True)}, range {pct(S['volume_pct_low'], 1, True)} to {pct(S['volume_pct_high'], 1, True)})",
         "Model · p.7")]
    hero_html = "".join(card(f'<div class="k">{esc(t)}</div><div class="big">{esc(n)}</div><p class="muted">{esc(x)}</p>')
                        for n, x, t in heroes)
    body = f"""<div style="display:grid;grid-template-rows:auto 1fr;gap:18px;min-height:0">
<div class="g4" style="display:grid;gap:18px">{hero_html}</div>
<div class="g3" style="display:grid;gap:18px;min-height:0">
{card('''<div style="display:flex;flex-direction:column;height:100%"><h3>Five questions an RGM product answers</h3><ul>
<li><b>Elasticity</b> - how price-sensitive is each category, brand and product? (p.4)</li>
<li><b>Promotions</b> - which mechanics create incremental volume, and which pay back? (p.5)</li>
<li><b>Price-pack</b> - is the price per ounce consistent across pack sizes? (p.6)</li>
<li><b>Scenarios</b> - what does +x% do to volume, revenue and profit? (p.7)</li>
<li><b>Scale</b> - does the same method hold market by market? (p.9)</li></ul>''' + f'<h3 style="margin-top:14px">Price elasticity by category (95% interval)</h3><div style="flex:1;min-height:0"><img src="{el_cat}" style="height:100%;width:100%;object-fit:contain"></div></div>')}
{card(f'''<h3>Recommendations</h3><ul>
<li>Test small price increases first on the least price-sensitive brands ({esc(low_txt)}); hold price on {esc(most['segment'].lower())}, where an increase loses revenue.</li>
<li>Move trade spend from TPR-only cuts (ROI {pct(tpr.get('roi', 0), 0, True)} at 30% margin) toward feature + display events, and negotiate their fees.</li>
{f"<li>Fix the pack ladder before the next price list: {esc(inv['description'])} costs {inv['inversion_premium']:.0%} more per ounce than {esc(inv['inverted_vs'])}.</li>" if inv and pp['inversions'] else ""}
<li>Roll out market by market with the same rules; {esc(' and '.join(unpub)) if unpub else 'small markets'} {'need' if len(unpub) != 1 else 'needs'} more stores before {'their' if len(unpub) != 1 else 'its'} own elasticities can be published.</li></ul>''')}
{card(f'''<h3>Data & methods</h3>
<p><span class="k">Real retail data</span> dunnhumby <i>Breakfast at the Frat</i>: {D['rows']:,} store x product x weeks, {D['products']} products, {D['stores']} US stores, {D['weeks']} weeks ({D['first_week'][:4]}-{D['last_week'][:4]}).</p>
<p><span class="k">Public data</span> Lingaro website (dated facts), Eurostat HICP.</p>
<p><span class="k">Simulated</span> NielsenIQ / Circana-style market data, clearly labelled.</p>
<p><span class="k">Data quality</span> {D['dq_ok_share']:.1%} of rows pass every check; {D.get('duplicate_stores', 0)} stores listed twice in the store file were de-duplicated; {esc(po_txt) if po_txt else 'no brand'} {'leave' if len(po_brands) != 1 else 'leaves'} the shelf in 2011 (kept in history, not simulated).</p>
<p><span class="k">Stack</span> SQL (DuckDB) · Python (statsmodels) · Power BI (TMDL + PBIR, {41} measures).</p>
<p><span class="k">How to read</span> Titles state the conclusion; the tag top right gives the data source; dashed lines are thresholds; ranges are 95% intervals.</p>''')}
</div></div>"""
    pages.append(page(1, "Lingaro: a Revenue Growth Management pricing product, prototyped on real retail data",
                      "Price elasticity, promotion effectiveness and price-pack opportunities for an FMCG portfolio, packaged as "
                      "a Power BI product with user stories and business rules: what I would deliver in Lingaro's RGM product team.",
                      "", body, "Sources and licences: data/SOURCES.md · Assumptions: data/ASSUMPTIONS.md"))

    # ---- 1 Lingaro in public data
    body = f"""<div class="g3" style="display:grid;gap:18px;min-height:0">
{card(f'''<h3>Who Lingaro is</h3><ul>
<li>{esc(facts.loc['F01','fact'])}.</li>
<li>On the market since {facts.loc['F03','value']}, {facts.loc['F02','value']} people, {facts.loc['F04','value']} global sites: {esc(facts.loc['F05','value'])}.</li>
<li>Domains: Marketing & Commercial Analytics, Supply Chain, Sustainability & Compliance, AI & GenAI, Data Consulting.</li>
<li>Named a Leader by ISG for retail & CPG analytics (2025); highest "value delivered" among Major Contenders in Everest Group's 2024 retail & CPG PEAK Matrix.</li>
<li>Says it has partnered with {facts.loc['F18','value']} of Fortune 200 CPG companies (company statement).</li></ul>''')}
{card(f'''<h3>Revenue Growth Management, in Lingaro's words</h3><ul>
<li>RGM is listed as a Marketing & Commercial Analytics capability.</li>
<li>Scope named on its site: price management, promo management, assortment, trade spend & profitability, <b>price elasticity analytics</b>, <b>what-if scenarios</b>, <b>promo effectiveness</b>, profit optimisation.</li>
<li>On promotions: uplift can mix true incremental demand with stock-up, pull-forward, cannibalisation and seasonality; trade spend can be {esc(facts.loc['F14','value'])} of gross sales.</li>
<li>Public case study: a price elasticity tool for a global beverage company - elasticity estimates, recommended strategies and what-if simulation on volume, sales value and gross profit, now the go-to source in {facts.loc['F11','value']} markets.</li></ul>''')}
{card(f'''<h3>What this prototype mirrors</h3>
<table><thead><tr><th>In Lingaro's case study / posting</th><th>Here</th></tr></thead><tbody>
<tr><td>Elasticity estimates per product</td><td>p.4, log-log with 95% intervals</td></tr>
<tr><td>Separate real demand from stock-up and cannibalisation</td><td>p.5, baseline, dip, cannibalisation</td></tr>
<tr><td>What-if on volume, sales value, gross profit</td><td>p.7, simulator with ranges</td></tr>
<tr><td>Data limitations explained to users</td><td>BR-06 publication rule</td></tr>
<tr><td>Scaled to other markets</td><td>p.9, one template, many markets</td></tr>
<tr><td>User stories, acceptance criteria, business rules</td><td>p.10, <code>product/</code></td></tr>
<tr><td>NielsenIQ / Circana data</td><td>p.8, simulated feed, labelled</td></tr></tbody></table>''')}
</div>"""
    pages.append(page(2, "Lingaro builds data & AI products for consumer goods; RGM pricing is one of them",
                      "Lingaro's public RGM case study describes exactly the product the RGM Data Analyst role supports: elasticity "
                      "estimates and a what-if simulator, built once and scaled market by market.",
                      "PUBLIC DATA", body,
                      "Source: lingarogroup.com (home, about, Marketing & Commercial Analytics, RGM case study, insights, careers), "
                      "retrieved 2026-11-12 · data/public/lingaro_facts.csv"))

    # ---- 2 Why pricing matters now
    body = f"""<div class="g64" style="display:grid;gap:18px;min-height:0">{card(img(hicp_a, 'EU27 HICP, annual average rate of change'))}
<div style="display:grid;grid-template-rows:1fr auto;gap:18px;min-height:0">{card(img(hicp_b, 'Cumulative food price increase, 2020 to 2025'))}
{card(f'''<h3>What it changes for revenue management</h3><ul>
<li>After two years of double-digit food inflation, shoppers compare prices more; elasticity is no longer a constant to assume, it is a number to measure, per market.</li>
<li>Retailers push back on list-price increases: each increase needs a volume, revenue and margin case.</li>
<li>Promotions absorb more trade spend: knowing which ones pay back protects margin.</li></ul>''', 'note')}</div></div>"""
    pages.append(page(3, f"EU food prices rose {pct(eu['food_cum_2020_2025'])} in five years: every price move now needs evidence",
                      f"Food inflation in the EU peaked at {eu['food_2022']:.1f}% in 2022 and {eu['food_2023']:.1f}% in 2023, well above "
                      f"all items, before easing to {eu['food_2025']:.1f}% in 2025. Food prices outpaced the overall index "
                      f"({pct(eu['food_cum_2020_2025'])} vs {pct(eu['all_cum_2020_2025'])} since 2020).",
                      "PUBLIC DATA", body, "Source: Eurostat HICP prc_hicp_aind (CC BY 4.0), retrieved 2026-11-12"))

    # ---- 3 Elasticity
    split = pd.DataFrame(E["split"])
    split = split.dropna(subset=["elasticity"]) if "elasticity" in split else split.iloc[0:0]
    split_html = (table(split[["category", "component", "elasticity", "ci_low", "ci_high"]].rename(
        columns={"category": "Category", "component": "Price component", "elasticity": "Elasticity",
                 "ci_low": "CI low", "ci_high": "CI high"}), {c: (lambda v: f"{v:.2f}") for c in ["Elasticity", "CI low", "CI high"]})
        if len(split) else "<p>Regular prices barely moved inside products: not estimable (BR-06).</p>")
    body = f"""<div class="g46" style="display:grid;gap:18px;min-height:0">
<div style="display:grid;grid-template-rows:auto 1fr;gap:18px;min-height:0">{card(img(el_cat, 'By category (blue = published, BR-06)'))}
{card(f'''<h3>Reading "{most['elasticity']:.1f}" in plain English</h3>
<p>If {esc(most['segment'])} prices go up 1%, units fall about {abs(most['elasticity']):.1f}%, all else equal. Because the fall is larger than 1%, revenue falls too. {esc(least['segment'])} ({least['elasticity']:.1f}) is far less sensitive.</p>
<p class="muted">Model: log(units) on log(price), with feature, display, store x product and month effects and a trend; errors clustered by store. It is a <b>correlation on historical data</b>, not an experiment: prices were set by the retailer, sometimes alongside actions the data does not show.</p>''', 'note')}</div>
<div style="display:grid;grid-template-rows:1fr auto;gap:18px;min-height:0">{card(img(el_brand, 'By brand (manufacturer within category); grey = review'))}
{card('<h3>Regular price vs promotion price cut</h3>' + split_html)}</div></div>"""
    pages.append(page(4, f"{most['segment']} is the most price-sensitive category ({most['elasticity']:.1f}); "
                         f"{least['segment']} the least ({least['elasticity']:.1f})",
                      f"{pub_n} of {E['n_segments']} category, brand and product elasticities pass the publication rule "
                      "(≥ 1,000 rows, ≥ 52 weeks, ≥ 5 stores, enough price variation, significant, negative, interval ≤ 1.5 wide)"
                      + (f"; the other {E['n_segments'] - pub_n} are {po_txt}, which leave the shelf in 2011. " if po_txt else ". ") +
                      f"{E['cross_substitutes']} of {E['cross_tested']} brands show a significant substitution effect with the rest of their category.",
                      "REAL RETAIL DATA", body,
                      "Source: dunnhumby 'Breakfast at the Frat' (licence: dunnhumby Source Files terms; raw data not redistributed) · src/elasticity.py"))

    # ---- 4 Promotions
    dip = pd.DataFrame(P["dip"])
    can = pd.DataFrame(P["cannibalisation"])
    can_w = can[can["context"].str.startswith("Another")][["category", "vs_baseline"]]
    small = dip.merge(can_w, on="category", how="left").rename(columns={"category": "Category", "dip": "Week after promo",
                                                                       "vs_baseline": "Other products during promo"})
    sens = P["sensitivity"]
    body = f"""<div class="g3" style="display:grid;gap:18px;min-height:0">{card(img(pr_up, 'Volume uplift vs baseline, by mechanic'))}
{card(img(pr_roi, 'Promotion ROI by mechanic and margin assumption (dashed = break-even)'))}
<div style="display:grid;grid-template-rows:auto 1fr;gap:18px;min-height:0">
{card('<h3>Dip and cannibalisation (units vs baseline)</h3>' + table(small, {"Week after promo": lambda v: pct(v, 1, True), "Other products during promo": lambda v: pct(v, 1, True) if pd.notna(v) else "-"}))}
{card(f'''<h3>So what</h3><ul>
<li>A price cut alone lifts volume {pct(tpr.get('uplift', 0), sign=True)} but gives away more margin than it creates: ROI {pct(tpr.get('roi', 0), 0, True)} at 30% margin.</li>
<li>Overall, promotions return {pct(sens.get('0.3', 0), 0, True)} on discount cost at 30% margin ({pct(sens.get('0.2', 0), 0, True)} at 20%, {pct(sens.get('0.4', 0), 0, True)} at 40%).</li>
<li>{"No stock-up dip is visible: the week after a promotion sells " + pct(P['dip_avg'], 0, True) + " vs baseline" if P['dip_avg'] > -0.01 else "The week after a promotion sells " + pct(P['dip_avg'], 0, True) + " vs baseline (stock-up)"}; other products of the category stay at {pct(P.get('cannibalisation_avg', 0), 1, True)}, so cannibalisation is negligible.</li>
<li>Feature and display fees are not in the data, so their ROI is optimistic.</li></ul>''', 'note')}</div></div>"""
    pages.append(page(5, f"Feature + display lifts volume {pct(fd.get('uplift', 0), sign=True)}; most price cuts do not pay back",
                      "Uplift = promo-week units vs a baseline of clean non-promo weeks within ±8 weeks (BR-03). ROI = (profit with the "
                      "promotion - profit without it) / discount cost, at an ASSUMED gross margin (BR-09).",
                      "REAL RETAIL DATA · ASSUMED MARGIN", body,
                      "Source: dunnhumby 'Breakfast at the Frat' · sql/02_promo_baseline.sql, src/promo.py · margin assumption: data/ASSUMPTIONS.md"))

    # ---- 5 PPA
    ppa = pd.read_csv(OUT / "ppa.csv")
    flags = ppa[ppa["opportunity"] != "No action"][["category", "manufacturer", "description", "base_price_per_oz",
                                                     "price_index_per_oz", "elasticity", "opportunity"]].head(9)
    flags = flags.rename(columns={"category": "Category", "manufacturer": "Brand", "description": "Product",
                                  "base_price_per_oz": "Price/oz", "price_index_per_oz": "Index", "elasticity": "Elasticity",
                                  "opportunity": "Opportunity"})
    body = f"""<div style="display:grid;grid-template-rows:1fr 1fr;gap:18px;min-height:0">{card(img(ppa_png, 'Regular price per ounce by pack size (red diamond = bigger pack costs more per oz than a smaller one of the same brand)'))}
{card('<h3>Flags and opportunities (BR-08, BR-11)</h3>' + table(flags, {"Price/oz": lambda v: f"${v:.3f}", "Index": lambda v: f"{v:.0f}", "Elasticity": lambda v: f"{v:.2f}" if pd.notna(v) else "-"}))}</div>"""
    n_inv, n_up = pp['inversions'], pp['price_up']
    pages.append(page(6, f"{n_inv} pack{' breaks' if n_inv == 1 else 's break'} the price ladder; {n_up} product{' looks' if n_up == 1 else 's look'} under-priced for {'its' if n_up == 1 else 'their'} low price sensitivity",
                      "A healthy ladder gives bigger packs a lower price per ounce. Prices are regular (base) prices so promotions do not "
                      "distort the ladder; index 100 = sub-category average; liquids are converted to fluid ounces.",
                      "REAL RETAIL DATA", body, "Source: dunnhumby 'Breakfast at the Frat' · sql/04_price_per_unit.sql, src/ppa.py"))

    # ---- 6 Simulator
    grid = pd.read_csv(OUT / "scenario_grid.csv")
    five = grid[(grid["price_change"].round(2) == 0.05) & (grid["level"] == "Brand")].copy()
    five = five.sort_values("profit_pct", ascending=False)
    tbl = pd.DataFrame({"Brand": [short(s) for s in five["segment"]],
                        "Volume": [f"{pct(v, 1, True)} ({pct(lo, 1, True)} to {pct(hi, 1, True)})" for v, lo, hi in
                                   zip(five["volume_pct"], five["volume_pct_low"], five["volume_pct_high"])],
                        "Revenue": [pct(v, 1, True) for v in five["revenue_pct"]],
                        "Gross profit": [pct(v, 1, True) for v in five["profit_pct"]]})
    pbi = sorted(IMG.glob("pbi_*simulator*.png"))
    right = card(img(f"img/{pbi[0].name}", "The same simulator in Power BI (what-if parameters)")) if pbi else \
        card('<h3>+5% on every published brand (30% margin, range from the 95% interval)</h3>' + table(tbl))
    body = f"""<div class="g2" style="display:grid;gap:18px;min-height:0">
<div style="display:grid;grid-template-rows:1fr auto;gap:18px;min-height:0">{card(img(sim_png, f'{short(S["segment"])}: effect of a price change (bands = 95% interval)'))}
{card(f'''<h3>How it works (BR-10, BR-11)</h3><p>Volume = (1+p)<sup>e</sup>; revenue = (1+p)<sup>1+e</sup>; gross profit = (1+p)<sup>e</sup> x (m+p)/m. Revenue rises with price only if |e| &lt; 1; gross profit rises with a small increase while |e| &lt; 1/m (3.3 at 30% margin). Only published elasticities, ±10% max, no competitor reaction: a first-order estimate for a proposal, not a forecast.</p>''', 'note')}</div>
{right}</div>"""
    pages.append(page(7, f"+5% on {brand_seg[1]} ({short(brand_seg[0]).lower()}): volume {pct(S['volume_pct'], 1, True)}, "
                         f"revenue {pct(S['revenue_pct'], 1, True)}, gross profit {pct(S['profit_pct'], 1, True)}",
                      f"The largest published brand, elasticity {S['elasticity']:.2f} (95% CI {S['ci'][0]:.2f} to {S['ci'][1]:.2f}). "
                      f"On last-52-week revenue of ${S['base_revenue']:,.0f}, that is {'+' if S['revenue_delta'] >= 0 else '-'}${abs(S['revenue_delta']):,.0f} revenue and "
                      f"{'+' if S['profit_delta'] >= 0 else '-'}${abs(S['profit_delta']):,.0f} gross profit per year at a 30% margin.",
                      "REAL DATA + MODEL", body, "Source: dunnhumby 'Breakfast at the Frat' · src/simulator.py; DAX 'Sim *' measures in Power BI"))

    # ---- 7 Market view SIMULATED
    body = f"""<div class="g2" style="display:grid;gap:18px;min-height:0">{card(img(mk_a, 'Market share (SIMULATED) vs share inside the retailer (real)'))}
<div style="display:grid;grid-template-rows:1fr auto;gap:18px;min-height:0">{card(img(mk_b, 'Price index vs competitors (SIMULATED; red > 105, blue < 95)'))}
{card('''<h3>Why simulate, and what changes with real panel data</h3><p>NielsenIQ / Circana data is paid. The simulated feed has the same shape (brand x quarter: value, share, competitor price, numeric and weighted distribution), so the model, measures and pages are ready for a real feed. With real data, this page would answer: are we losing share where our price index is highest?</p>''', 'note')}</div></div>"""
    pages.append(page(8, "Market view: how an external panel feed plugs into the product",
                      "SIMULATED data (seed 42), calibrated on the retailer's real brand shares. It shows the data model and the measures, "
                      "not a market reading: do not quote these numbers.",
                      "SIMULATED", body, "SIMULATED by src/simulate_market.py - not NielsenIQ, Circana, dunnhumby, Lingaro or client data · assumptions S1-S6 in data/ASSUMPTIONS.md"))

    # ---- 8 Markets
    spread = MK["spread"]
    body = f"""<div style="display:grid;grid-template-rows:1fr auto;gap:18px;min-height:0">{card(img(mkts_png, 'Category elasticity by market (state), with 95% intervals'))}
<div class="g2" style="display:grid;gap:18px">{card(f'''<h3>Standard in every market</h3><ul>
<li>Same SQL, Python and DAX; same business rules BR-01 to BR-13; same report pages.</li>
<li>A market is a filter: no code change to add one (BR-12).</li>
<li>Each market is published only on its own evidence: {MK['published']} of {MK['segments']} market x category estimates pass.</li></ul>''')}
{card(f'''<h3>What varies</h3><ul>
<li>The size of the elasticity: largest gap between markets per category {", ".join(f"{short(k)} {v:.2f}" for k, v in spread.items())}.</li>
<li>Sample size: small markets give wider intervals, so fewer publishable segments.</li>
<li>In Europe: currency, VAT, retailer mix and promotion rules differ, and enter as market parameters.</li></ul>''')}</div></div>"""
    ms_ = MK.get("more_sensitive_everywhere")
    others = [STATE.get(m, m) for m in MK.get("published_markets", []) if m != ms_]
    title9 = (f"Same method in every market: {STATE.get(ms_, ms_)} shoppers are more price-sensitive than {' and '.join(others)} "
              f"in all {MK['n_categories']} categories" if ms_ else
              f"One method, {len(D['states'])} markets: the template travels, the elasticities differ")
    pages.append(page(9, title9,
                      "Each US state in the data plays the role of a market. The pipeline, the business rules and the report are reused "
                      "unchanged; only the market filter changes. This is how an RGM product scales across European markets."
                      + (f" {' and '.join(unpub)} {'have' if len(unpub) != 1 else 'has'} fewer than 5 stores: not published (BR-06)." if unpub else ""),
                      "REAL RETAIL DATA", body, "Source: dunnhumby 'Breakfast at the Frat' · src/elasticity.py (level = Market)"))

    # ---- 9 Product
    body = """<div class="g4" style="display:grid;gap:18px;min-height:0">
""" + card('''<h3>User stories (10)</h3><ul>
<li><b>US-01</b> As a Revenue Manager, I want each elasticity with its 95% range and sample size, so that I know where a price move is low-risk.</li>
<li><b>US-03</b> As a Trade Marketing Manager, I want uplift and ROI per mechanic and brand, so that I move spend to what pays back.</li>
<li><b>US-05</b> As a Revenue Manager, I want to simulate up to ±10% with a range, so that I can prepare a pricing proposal.</li>
<li><b>US-09</b> As a Product Owner, I want to add a market by changing a filter, so that the product scales at low cost.</li></ul>''') + card('''<h3>Acceptance criteria (Given / When / Then)</h3>
<p><b>AC-05.1</b> Given a published elasticity -1.5, +5% and a 30% margin, when the simulator runs, then volume = -7.06%, revenue = -2.41%, gross profit = +8.43%.</p>
<p><b>AC-05.4</b> Given two segments or a non-published one selected, when the page renders, then outputs are blank and the status explains why.</p>
<p><b>AC-03.2</b> Given base $4.00, promo $3.00, 100 units, baseline 40, margin 30%, then ROI = -28%.</p>''') + card('''<h3>Business rules (13)</h3><ul>
<li><b>BR-03</b> Baseline = average of clean non-promo weeks within ±8 weeks; ≥ 4 weeks or no baseline.</li>
<li><b>BR-06</b> Publish an elasticity only with ≥ 1,000 rows, ≥ 52 weeks, ≥ 5 stores, price variation ≥ 5%, p &lt; 0.05, negative sign, interval ≤ 1.5. Positive sign = analyst review.</li>
<li><b>BR-10</b> Simulator: published segments only, ±10% max, ranges always shown.</li>
<li><b>BR-13</b> Every page tagged REAL / PUBLIC / SIMULATED.</li></ul>''') + card(f'''<h3>Test plan</h3><ul>
<li>25 automated checks (<code>src/check_results.py</code>): rule unit tests, reconciliations, output assertions.</li>
<li>DAX vs Python: each key measure compared with the Python value at release.</li>
<li>Method test on simulated data: 9 of 10 known elasticities inside the 95% interval.</li>
<li>{len(__import__('build_tmdl').MEASURES)} measures documented in <code>MEASURES_DICTIONARY.md</code>.</li></ul>''') + "</div>"
    pages.append(page(10, "From analysis to product: stories, rules and tests a development team can build on",
                      "The analysis is packaged as product documentation: user stories with priorities, testable acceptance criteria, "
                      "numbered business rules and a test plan. Full documents in product/.",
                      "", body, "product/USER_STORIES.md · ACCEPTANCE_CRITERIA.md · BUSINESS_RULES.md · MEASURES_DICTIONARY.md · TEST_PLAN.md"))

    # ---- 10 Methods & limits
    body = f"""<div class="g3" style="display:grid;gap:18px;min-height:0">{card(f'''<h3>Sources and licences</h3><ul>
<li><b>dunnhumby</b> <i>Breakfast at the Frat</i>, Source Files terms of use: raw data not redistributed; scripts and aggregates only.</li>
<li><b>Eurostat</b> HICP, CC BY 4.0.</li>
<li><b>Lingaro</b> public website, facts quoted with URL and date (2026-11-12).</li>
<li><b>Simulated</b> market data and test sample, seed 42, labelled everywhere.</li></ul>
<h3 style="margin-top:12px">Reproduce</h3><p><code>python src/run_all.py</code> (real data) or <code>python src/run_all.py --sample</code> (simulated sample, no download). Power BI: open <code>powerbi/LingaroRGM.pbip</code>, refresh.</p>''')}
{card('''<h3>Limits</h3><ul>
<li><b>Elasticity is observational</b>: a correlation on historical prices set by the retailer, not a controlled test. Controls reduce, but do not remove, confounding (unobserved competitor moves, local events).</li>
<li><b>Old US data</b> (2009-2012, one retailer): it demonstrates the method, not today's European elasticities.</li>
<li><b>Margin is assumed</b> (30%); feature and display fees are unknown, so their ROI is optimistic.</li>
<li><b>Market data is simulated</b>; no market conclusion is drawn from it.</li>
<li>The simulator ignores competitor and retailer reactions and is capped at ±10%.</li></ul>''')}
{card(f'''<h3>Methods</h3><ul>
<li>SQL (DuckDB): baseline with window functions, hierarchy ROLLUP, price per oz, quality checks.</li>
<li>Python: statsmodels OLS, log-log, store x product and month effects, trend, store-clustered errors.</li>
<li>Data quality: rows flagged, not deleted (BR-07); duplicate store records and phasing-out products found and handled.</li>
<li>Specification check: with separate store and product effects, bag snacks came out at -0.65, because Texas stores carry only 9 of the 15 snack products. One effect per store x product pair fixes this (-1.23, consistent with Ohio and Texas on their own).</li>
<li>Validation: 25 automated checks pass; on simulated data with known elasticities, 9 of 10 true values fall inside the 95% interval.</li>
<li>Power BI: star schema, {len(__import__('build_tmdl').MEASURES)} DAX measures, what-if parameters, TMDL + PBIR generated by script.</li></ul>
<h3 style="margin-top:12px">AI note</h3><p>{esc(AI_NOTE)}</p>''')}</div>"""
    pages.append(page(11, "Methods, limits and how to reproduce",
                      "What the numbers can and cannot say, where every input comes from, and how to rerun everything from a clean clone.",
                      "", body, "Full details: README.md, data/SOURCES.md, data/ASSUMPTIONS.md"))

    # ---- appendix: Power BI screenshots if present
    for i, shot in enumerate(sorted(IMG.glob("pbi_*.png"))):
        pages.append(page(12 + i, "Appendix - Power BI report: " + shot.stem.replace("pbi_", "").replace("_", " ").lstrip("0123456789 "),
                          "Screenshot of the Power BI report built from the same data (powerbi/LingaroRGM.pbip).", "POWER BI",
                          f'<div class="card" style="display:flex;align-items:center;justify-content:center">'
                          f'<img src="img/{shot.name}" style="max-height:640px;width:auto;max-width:100%"></div>',
                          "powerbi/LingaroRGM.pbip"))

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title></title><style>{CSS}</style></head>
<body>{''.join(pages)}</body></html>"""
    (DOCS / "report.html").write_text(doc, encoding="utf-8")
    return len(pages)


def to_pdf():
    browsers = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Google\Chrome\Application\chrome.exe", shutil.which("msedge") or "",
                shutil.which("chromium") or "", shutil.which("google-chrome") or ""]
    exe = next(b for b in browsers if b and Path(b).exists())
    tmp = DOCS / "_tmp.pdf"
    profile = Path(tempfile.mkdtemp(prefix="pdfprofile_"))   # separate profile: works even if the browser is open
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={profile}",
                    f"--print-to-pdf={tmp.resolve()}", (DOCS / "report.html").resolve().as_uri()], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(120):   # the browser may hand the job to a child process: wait for the file
        if tmp.exists() and tmp.stat().st_size > 0:
            break
        time.sleep(0.5)
    time.sleep(1)
    # rewrite with EMPTY metadata (no author, no creator, no title)
    w = PdfWriter(clone_from=PdfReader(tmp))
    w._info = None
    w.add_metadata({"/Title": "", "/Author": "", "/Creator": "", "/Producer": ""})
    final = DOCS / "Lingaro_RGM_CaseStudy.pdf"
    with open(final, "wb") as fh:
        w.write(fh)
    tmp.unlink()
    shutil.rmtree(profile, ignore_errors=True)
    return final


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    n = build()
    pdf = to_pdf()
    print(f"{n} pages -> {pdf}", PdfReader(pdf).metadata)
