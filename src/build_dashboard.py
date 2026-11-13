"""Build docs/dashboard.html: an interactive, single-file version of the main results for GitHub Pages.

    python src/build_dashboard.py

The data comes from data/output (aggregated results only, never row-level dunnhumby data) and is
embedded as JSON, so the page needs no server. Charts use Chart.js from a CDN.
The simulator recomputes the same formulas as src/simulator.py and the DAX 'Sim *' measures.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "output"
DOCS = ROOT / "docs"
REPO = "https://github.com/albt-france/lingaro-rgm-pricing-case-study"


def r(x, d=4):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), d)


def short(seg):
    return seg.replace("Oral Hygiene Products", "Oral hygiene").replace("Cold Cereal", "Cereal")


def build_data():
    el = pd.read_csv(OUT / "elasticity.csv")
    elast = [dict(id=int(x.segment_id), level=x.level, segment=short(x.segment), category=x.category,
                  e=r(x.elasticity, 3), lo=r(x.ci_low, 3), hi=r(x.ci_high, 3), n=int(x.n_obs), stores=int(x.n_stores),
                  status=x.status, why=x.status_reason if isinstance(x.status_reason, str) else "",
                  rev=r(x.base_revenue_52w, 0))
             for x in el.itertuples() if x.level in ("Category", "Brand", "Product", "Market")]
    eff = pd.read_csv(OUT / "promo_effectiveness.csv")
    summ = pd.read_csv(OUT / "promo_summary.csv")
    by_type = {}
    for m, g in summ.groupby("margin_assumption"):
        t = g.groupby("promo_type")[["units", "baseline_units", "net_incr_profit", "discount_cost"]].sum()
        by_type[f"{m:.1f}"] = {k: dict(uplift=r(v.units / v.baseline_units - 1), roi=r(v.net_incr_profit / v.discount_cost))
                               for k, v in t.iterrows()}
    promo = [dict(category=x.category, brand=x.manufacturer, type=x.promo_type, weeks=int(x.promo_weeks),
                  disc=r(x.avg_discount), uplift=r(x.uplift), roi=r(x.roi), payback=r(x.share_weeks_paid_back))
             for x in eff.itertuples()]
    ppa = pd.read_csv(OUT / "ppa.csv")
    ppa_rows = [dict(category=x.category, brand=x.manufacturer, product=x.description, oz=r(x.size_oz, 2),
                     ppo=r(x.base_price_per_oz), idx=r(x.price_index_per_oz, 1), e=r(x.elasticity, 2),
                     inv=x.inverted_vs if isinstance(x.inverted_vs, str) else "", opp=x.opportunity) for x in ppa.itertuples()]
    dq = pd.read_csv(OUT / "sql_05_data_quality.csv")
    f = json.loads((OUT / "findings.json").read_text(encoding="utf-8").replace("NaN", "null"))
    return dict(elasticity=elast, by_type=by_type, promo=promo, ppa=ppa_rows,
                dq=[dict(check=x.check_name, rows=int(x.rows_hit), note=x.note if isinstance(x.note, str) else "")
                    for x in dq.itertuples()],
                data=f["data"], dip=f["promo"]["dip_avg"], cann=f["promo"].get("cannibalisation_avg", 0),
                pay=[f["promo"]["brand_mechanics_paying_back"], f["promo"]["brand_mechanics"]], repo=REPO)


HTML = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>RGM Pricing Dashboard</title>
<meta name="description" content="Interactive RGM pricing dashboard: price elasticity, promotion ROI, price-pack architecture and a what-if price simulator, on real retail data.">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root { --bg:#F4F4F2; --card:#FCFCFB; --ink:#0B0B0B; --ink2:#52514E; --muted:#898781; --grid:#E1E0D9;
        --blue:#2A78D6; --blued:#184F94; --bluel:#8DB9EE; --orange:#EB6834; --red:#D03B3B; --bluetint:#CDE2FB; --grey:#B4B2AD; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#161615; --card:#1F1F1E; --ink:#F1F0EC; --ink2:#C2C0B9; --muted:#8F8D86; --grid:#34332F;
  --blue:#5598E7; --blued:#8DB9EE; --bluel:#2D5E9C; --orange:#F08458; --red:#E5605F; --bluetint:#1D3554; --grey:#6E6C66; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font-family:'Segoe UI', system-ui, -apple-system, sans-serif; font-size:14px; }
.wrap { max-width:1280px; margin:0 auto; padding:24px 16px 40px; }
header { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; }
h1 { font-size:26px; margin:0 0 4px; line-height:1.2; }
h2 { font-size:18px; margin:30px 0 4px; }
.sub { color:var(--ink2); margin:0 0 6px; max-width:920px; line-height:1.45; }
.tag { font-size:11px; font-weight:700; letter-spacing:.06em; color:var(--ink2); white-space:nowrap; padding-top:8px; }
.links a { color:var(--blue); text-decoration:none; margin-right:14px; font-size:13px; }
.controls { display:flex; gap:14px; align-items:center; flex-wrap:wrap; margin:12px 0; }
select, input[type=range] { font:inherit; }
select { padding:7px 10px; border-radius:8px; border:1px solid var(--grid); background:var(--card); color:var(--ink); min-width:240px; max-width:100%; }
input[type=range] { width:200px; accent-color:var(--blue); }
.card { background:var(--card); border:1px solid var(--grid); border-radius:8px; padding:14px 16px; min-width:0; }
.card h3 { font-size:11px; letter-spacing:.05em; text-transform:uppercase; color:var(--ink2); margin:0 0 8px; }
.kpis { display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; }
.kpi .v { font-size:30px; font-weight:700; line-height:1.1; font-variant-numeric:tabular-nums; }
.kpi .l { color:var(--ink2); font-size:12.5px; margin-top:4px; line-height:1.35; }
.grid2 { display:grid; grid-template-columns:3fr 2fr; gap:12px; margin-top:12px; }
.grid2b { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:12px; }
.chartbox { position:relative; height:340px; } .chartbox.tall { height:520px; } .chartbox.sm { height:260px; }
table { border-collapse:collapse; width:100%; font-size:13px; }
th { text-align:left; color:var(--ink2); font-weight:600; border-bottom:1px solid var(--ink2); padding:5px 6px; white-space:nowrap; }
td { padding:5px 6px; border-bottom:1px solid var(--grid); vertical-align:middle; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
.tablewrap { overflow-x:auto; max-height:420px; overflow-y:auto; }
.pos { color:var(--blue); } .neg { color:var(--red); }
.note { color:var(--ink2); font-size:12.5px; line-height:1.45; margin:8px 0 0; }
.status { font-size:13px; color:var(--ink2); margin-top:6px; }
footer { color:var(--muted); font-size:11.5px; margin-top:28px; line-height:1.5; }
a { color:var(--blue); }
@media (max-width: 900px) { .kpis { grid-template-columns:1fr 1fr; } .grid2, .grid2b { grid-template-columns:1fr; } h1 { font-size:21px; } }
</style></head>
<body><div class="wrap">
<header><div><h1>RGM pricing: elasticity, promotions, price-pack and a what-if simulator</h1>
<p class="sub">Prototype of a Revenue Growth Management pricing product on real retail data (dunnhumby <i>Breakfast at the Frat</i>,
weekly store x product sales, 77 US stores, 2009-2012). Only aggregated results are embedded in this page.</p>
<div class="links"><a href="__REPO__">Repository</a><a href="__REPO__/blob/main/docs/Lingaro_RGM_CaseStudy.pdf">Report (PDF)</a><a href="__REPO__/tree/main/powerbi">Power BI project</a><a href="__REPO__/tree/main/product">Product docs</a></div></div>
<div class="tag">REAL RETAIL DATA</div></header>

<div class="kpis" style="margin-top:16px">
  <div class="card kpi"><h3>Published elasticities</h3><div class="v" id="k1"></div><div class="l">category, brand and product estimates passing the publication rule (BR-06)</div></div>
  <div class="card kpi"><h3>Most / least price-sensitive</h3><div class="v" id="k2"></div><div class="l" id="k2l"></div></div>
  <div class="card kpi"><h3>Brand x mechanic paying back</h3><div class="v" id="k3"></div><div class="l">promotions with positive net incremental profit, at an ASSUMED 30% margin</div></div>
  <div class="card kpi"><h3>Rows passing quality checks</h3><div class="v" id="k4"></div><div class="l" id="k4l"></div></div>
</div>

<h2>Scenario simulator</h2>
<p class="sub">Pick one segment with a published elasticity, a price change (capped at ±10%) and an ASSUMED gross margin. Ranges come from the 95% interval of the elasticity. Same formulas as the Python simulator and the Power BI DAX measures.</p>
<div class="controls">
  <label><b>Segment</b> <select id="seg"></select></label>
  <label><b>Price change</b> <input type="range" id="p" min="-10" max="10" step="1" value="5"> <span id="pv"></span></label>
  <label><b>Margin</b> <input type="range" id="m" min="20" max="45" step="5" value="30"> <span id="mv"></span></label>
</div>
<div class="kpis">
  <div class="card kpi"><h3>Volume</h3><div class="v" id="s1"></div><div class="l" id="s1l"></div></div>
  <div class="card kpi"><h3>Revenue</h3><div class="v" id="s2"></div><div class="l" id="s2l"></div></div>
  <div class="card kpi"><h3>Gross profit</h3><div class="v" id="s3"></div><div class="l" id="s3l"></div></div>
  <div class="card kpi"><h3>Per year, on last-52-week revenue</h3><div class="v" id="s4"></div><div class="l" id="s4l"></div></div>
</div>
<div class="grid2">
  <div class="card"><h3>Effect of a price change from -10% to +10%</h3><div class="chartbox"><canvas id="c_sim" aria-label="Simulator curves"></canvas></div>
    <p class="status" id="sstatus"></p></div>
  <div class="card"><h3>How it works</h3><p class="note" style="margin-top:0">Volume = (1+p)<sup>e</sup>; revenue = (1+p)<sup>1+e</sup>; gross profit = (1+p)<sup>e</sup> x (m+p)/m.
    Revenue rises with price only if |e| &lt; 1. Gross profit rises with a small increase while |e| &lt; 1/m (3.3 at a 30% margin).</p>
    <p class="note">The model assumes a constant elasticity near observed prices, no competitor or retailer reaction, and an assumed margin: a first-order estimate for a pricing proposal, not a forecast.</p>
    <p class="note">The elasticity is observational (a correlation on historical prices), from a log-log regression with feature, display, store x product and month effects and a trend; errors clustered by store.</p></div>
</div>

<h2>Price elasticity</h2>
<p class="sub">% change in units for +1% price, with its 95% interval. Grey = not published (phased out, too few stores, or uncertain). Dashed line = -1: to its left, a price increase loses revenue.</p>
<div class="controls"><label><b>Level</b> <select id="lvl"><option>Brand</option><option>Category</option><option>Market</option><option>Product</option></select></label></div>
<div class="grid2">
  <div class="card"><h3 id="c_el_t">Elasticity by brand</h3><div class="chartbox tall"><canvas id="c_el" aria-label="Elasticity chart"></canvas></div></div>
  <div class="card"><h3>Values</h3><div class="tablewrap" style="max-height:520px"><table><thead><tr><th>Segment</th><th class="num">Elasticity</th><th class="num">95% CI</th><th>Status</th></tr></thead><tbody id="t_el"></tbody></table></div></div>
</div>

<h2>Promotion effectiveness</h2>
<p class="sub">Uplift = promo-week units vs a baseline of clean non-promo weeks within ±8 weeks. ROI = (profit with the promotion - profit without it) / discount cost, at an ASSUMED margin. Feature and display fees are not in the data, so their ROI is optimistic.</p>
<div class="controls"><label><b>Margin assumption</b> <select id="pm"><option value="0.2">20%</option><option value="0.3" selected>30%</option><option value="0.4">40%</option></select></label>
  <label><b>Category</b> <select id="pc"></select></label></div>
<div class="grid2b">
  <div class="card"><h3>Volume uplift vs baseline, by mechanic (all categories)</h3><div class="chartbox sm"><canvas id="c_up"></canvas></div></div>
  <div class="card"><h3>ROI by mechanic (all categories)</h3><div class="chartbox sm"><canvas id="c_roi"></canvas></div>
    <p class="note" id="dipnote"></p></div>
</div>
<div class="card" style="margin-top:12px"><h3>By brand and mechanic (ROI at 30% margin)</h3><div class="tablewrap"><table><thead><tr><th>Category</th><th>Brand</th><th>Mechanic</th><th class="num">Promo weeks</th><th class="num">Avg discount</th><th class="num">Uplift</th><th class="num">ROI</th></tr></thead><tbody id="t_pr"></tbody></table></div></div>

<h2>Price-pack architecture</h2>
<p class="sub">Regular (base) price per ounce by pack size. A healthy ladder gives bigger packs a lower price per ounce. Red = a bigger pack costs more per ounce than a smaller pack of the same brand.</p>
<div class="controls"><label><b>Category</b> <select id="pp"></select></label></div>
<div class="grid2">
  <div class="card"><h3>Regular price per ounce vs pack size</h3><div class="chartbox"><canvas id="c_ppa"></canvas></div></div>
  <div class="card"><h3>Flags and opportunities</h3><div class="tablewrap"><table><thead><tr><th>Product</th><th class="num">Index</th><th class="num">Elasticity</th><th>Opportunity</th></tr></thead><tbody id="t_ppa"></tbody></table></div></div>
</div>

<h2>Data quality</h2>
<div class="card"><div class="tablewrap"><table><thead><tr><th>Check</th><th class="num">Rows</th><th>Handling</th></tr></thead><tbody id="t_dq"></tbody></table></div>
<p class="note">Rows are flagged, not deleted. The raw store file lists 2 stores twice (de-duplicated); Quaker and Colgate products leave the shelf in 2011 (kept in history, not simulated).</p></div>

<footer>Sources: dunnhumby <i>Breakfast at the Frat</i> (Source Files terms; raw data not redistributed, aggregated results only). Margins are assumptions.
Built with SQL (DuckDB), Python (statsmodels) and Chart.js; the same model ships as a Power BI project in the repository.<br>
Independent case study based on public data · not affiliated with or endorsed by Lingaro</footer>
</div>
<script>
const D = __DATA__;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const C = { ink: css('--ink'), ink2: css('--ink2'), grid: css('--grid'), blue: css('--blue'), blued: css('--blued'), bluel: css('--bluel'), grey: css('--grey'), red: css('--red'), orange: css('--orange') };
Chart.defaults.color = C.ink2; Chart.defaults.borderColor = C.grid; Chart.defaults.font.family = "'Segoe UI', system-ui, sans-serif";
const pct = (v, d = 1, s = true) => v == null ? '–' : (s && v > 0 ? '+' : '') + (v * 100).toFixed(d) + '%';
const usd = v => (v >= 0 ? '+' : '-') + '$' + Math.abs(Math.round(v)).toLocaleString('en-US');
const $ = id => document.getElementById(id);
const charts = {};
function draw(id, cfg) { if (charts[id]) charts[id].destroy(); charts[id] = new Chart($(id), cfg); }

// KPIs
const pub = D.elasticity.filter(x => x.status === 'Published' && ['Category', 'Brand', 'Product'].includes(x.level));
const allSeg = D.elasticity.filter(x => ['Category', 'Brand', 'Product'].includes(x.level));
$('k1').textContent = pub.length + ' / ' + allSeg.length;
const cats = D.elasticity.filter(x => x.level === 'Category').sort((a, b) => a.e - b.e);
$('k2').textContent = cats[0].e.toFixed(1) + ' / ' + cats[cats.length - 1].e.toFixed(1);
$('k2l').textContent = cats[0].segment + ' / ' + cats[cats.length - 1].segment + ' (category elasticity)';
$('k3').textContent = D.pay[0] + ' / ' + D.pay[1];
$('k4').textContent = (D.data.dq_ok_share * 100).toFixed(1) + '%';
$('k4l').textContent = D.data.rows.toLocaleString('en-US') + ' weekly store x product rows, ' + D.data.products + ' products, ' + D.data.stores + ' stores';

// Simulator
const simSeg = pub.slice().sort((a, b) => ({Category: 0, Brand: 1, Product: 2}[a.level] - {Category: 0, Brand: 1, Product: 2}[b.level]) || a.segment.localeCompare(b.segment));
$('seg').innerHTML = simSeg.map(x => `<option value="${x.id}">${x.level}: ${x.segment}</option>`).join('');
const def = simSeg.filter(x => x.level === 'Brand').sort((a, b) => b.rev - a.rev)[0];
$('seg').value = def.id;
function sim(e, p, m) { return [Math.pow(1 + p, e) - 1, Math.pow(1 + p, 1 + e) - 1, Math.pow(1 + p, e) * (m + p) / m - 1]; }
function runSim() {
  const s = D.elasticity.find(x => x.id == $('seg').value), p = $('p').value / 100, m = $('m').value / 100;
  $('pv').textContent = (p > 0 ? '+' : '') + Math.round(p * 100) + '%'; $('mv').textContent = Math.round(m * 100) + '%';
  const c = sim(s.e, p, m), a = sim(s.lo, p, m), b = sim(s.hi, p, m);
  [['s1', 0], ['s2', 1], ['s3', 2]].forEach(([id, i]) => {
    $(id).textContent = pct(c[i]); $(id).className = 'v ' + (c[i] >= 0 ? 'pos' : 'neg');
    $(id + 'l').textContent = 'range ' + pct(Math.min(a[i], b[i])) + ' to ' + pct(Math.max(a[i], b[i]));
  });
  $('s4').textContent = usd(c[2] * s.rev * m); $('s4l').textContent = 'gross profit; revenue ' + usd(c[1] * s.rev) + ' (base $' + s.rev.toLocaleString('en-US') + ')';
  $('sstatus').textContent = `Published elasticity ${s.e.toFixed(2)} (95% CI ${s.lo.toFixed(2)} to ${s.hi.toFixed(2)}), ${s.n.toLocaleString('en-US')} rows, ${s.stores} stores.`;
  const xs = [...Array(21).keys()].map(i => i - 10);
  const ser = (k, col, lab) => [
    { label: lab, data: xs.map(x => sim(s.e, x / 100, m)[k] * 100), borderColor: col, backgroundColor: col, borderWidth: 2, pointRadius: 0, tension: .2 },
    { label: lab + ' range', data: xs.map(x => Math.max(sim(s.lo, x / 100, m)[k], sim(s.hi, x / 100, m)[k]) * 100), borderWidth: 0, pointRadius: 0, fill: '+1', backgroundColor: col + '33' },
    { label: '_', data: xs.map(x => Math.min(sim(s.lo, x / 100, m)[k], sim(s.hi, x / 100, m)[k]) * 100), borderWidth: 0, pointRadius: 0 }];
  draw('c_sim', { type: 'line', data: { labels: xs.map(x => (x > 0 ? '+' : '') + x + '%'),
      datasets: [...ser(0, C.grey, 'Volume'), ...ser(1, C.bluel, 'Revenue'), ...ser(2, C.blued, 'Gross profit')] },
    options: { maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      plugins: { legend: { labels: { filter: i => !i.text.includes('range') && i.text !== '_' } },
                 tooltip: { filter: i => !i.dataset.label.includes('range') && i.dataset.label !== '_', callbacks: { label: i => i.dataset.label + ': ' + (i.raw > 0 ? '+' : '') + i.raw.toFixed(1) + '%' } } },
      scales: { y: { title: { display: true, text: 'Change vs last 52 weeks, %' } }, x: { title: { display: true, text: 'Price change' }, grid: { display: false } } } } });
}
['seg', 'p', 'm'].forEach(id => $(id).addEventListener('input', runSim)); runSim();

// Elasticity
function runEl() {
  const lvl = $('lvl').value;
  const rows = D.elasticity.filter(x => x.level === lvl).sort((a, b) => (a.e ?? 9) - (b.e ?? 9));
  $('c_el_t').textContent = 'Elasticity by ' + lvl.toLowerCase();
  const fit = rows.filter(x => x.e != null);
  draw('c_el', { type: 'bar', data: { labels: fit.map(x => x.segment), datasets: [
      { label: '95% interval', data: fit.map(x => [x.lo, x.hi]), backgroundColor: fit.map(x => x.status === 'Published' ? C.blue + '55' : C.grey + '77'), borderRadius: 4, barPercentage: .5 },
      { type: 'scatter', label: 'Elasticity', data: fit.map((x, i) => ({ x: x.e, y: x.segment })), backgroundColor: fit.map(x => x.status === 'Published' ? C.blue : C.grey), pointRadius: 5 }] },
    options: { indexAxis: 'y', maintainAspectRatio: false, plugins: { legend: { display: false },
        tooltip: { callbacks: { label: i => { const x = fit[i.dataIndex]; return `${x.e.toFixed(2)} (95% CI ${x.lo.toFixed(2)} to ${x.hi.toFixed(2)}) · ${x.status}`; } } } },
      scales: { x: { title: { display: true, text: 'Price elasticity (dashed = -1)' }, suggestedMax: 0 }, y: { grid: { display: false }, ticks: { autoSkip: false, font: { size: lvl === 'Product' ? 9 : 11 } } } } },
    plugins: [{ id: 'ref', afterDraw(ch) { const x = ch.scales.x.getPixelForValue(-1), a = ch.chartArea, g = ch.ctx;
      g.save(); g.setLineDash([4, 4]); g.strokeStyle = C.ink2; g.beginPath(); g.moveTo(x, a.top); g.lineTo(x, a.bottom); g.stroke(); g.restore(); } }] });
  $('t_el').innerHTML = rows.map(x => `<tr><td>${x.segment}</td><td class="num">${x.e == null ? '–' : x.e.toFixed(2)}</td><td class="num">${x.e == null ? '–' : x.lo.toFixed(2) + ' to ' + x.hi.toFixed(2)}</td><td>${x.status}${x.why ? '<br><span class="note">' + x.why + '</span>' : ''}</td></tr>`).join('');
}
$('lvl').addEventListener('change', runEl); runEl();

// Promotions
const order = ['TPR only', 'Display', 'Feature', 'Feature + Display'];
const pcats = [...new Set(D.promo.map(x => x.category))].sort();
$('pc').innerHTML = '<option value="">All categories</option>' + pcats.map(c => `<option>${c}</option>`).join('');
function runPromo() {
  const t = D.by_type[$('pm').value], m = $('pm').value;
  draw('c_up', { type: 'bar', data: { labels: order, datasets: [{ label: 'Uplift', data: order.map(k => t[k].uplift * 100), backgroundColor: C.blue, borderRadius: 4, barPercentage: .55 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: i => '+' + i.raw.toFixed(0) + '% vs baseline' } } },
      scales: { y: { title: { display: true, text: 'Uplift, %' } }, x: { grid: { display: false } } } } });
  draw('c_roi', { type: 'bar', data: { labels: order, datasets: [{ label: 'ROI', data: order.map(k => t[k].roi * 100), backgroundColor: order.map(k => t[k].roi >= 0 ? C.blue : C.red), borderRadius: 4, barPercentage: .55 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: i => (i.raw > 0 ? '+' : '') + i.raw.toFixed(0) + '% at ' + Math.round(m * 100) + '% margin' } } },
      scales: { y: { title: { display: true, text: 'ROI on discount cost, %' } }, x: { grid: { display: false } } } } });
  $('dipnote').textContent = `Week after a promotion: ${pct(D.dip, 0)} vs baseline (no stock-up dip). Other products of the category during a promotion: ${pct(D.cann, 1)} (no measurable cannibalisation).`;
  const c = $('pc').value;
  $('t_pr').innerHTML = D.promo.filter(x => !c || x.category === c).sort((a, b) => b.roi - a.roi).map(x =>
    `<tr><td>${x.category}</td><td>${x.brand}</td><td>${x.type}</td><td class="num">${x.weeks.toLocaleString('en-US')}</td><td class="num">${pct(x.disc, 0, false)}</td><td class="num">${pct(x.uplift, 0)}</td><td class="num ${x.roi >= 0 ? 'pos' : 'neg'}">${pct(x.roi, 0)}</td></tr>`).join('');
}
['pm', 'pc'].forEach(id => $(id).addEventListener('change', runPromo)); runPromo();

// PPA
const ppcats = [...new Set(D.ppa.map(x => x.category))].sort();
$('pp').innerHTML = ppcats.map(c => `<option>${c}</option>`).join('');
function runPpa() {
  const rows = D.ppa.filter(x => x.category === $('pp').value);
  const pt = x => ({ x: x.oz, y: x.ppo, label: x.product });
  draw('c_ppa', { type: 'scatter', data: { datasets: [
      { label: 'Consistent ladder', data: rows.filter(x => !x.inv).map(pt), backgroundColor: C.blue, pointRadius: 6 },
      { label: 'Inverted ladder', data: rows.filter(x => x.inv).map(pt), backgroundColor: C.red, pointRadius: 8, pointStyle: 'rectRot' }] },
    options: { maintainAspectRatio: false, plugins: { tooltip: { callbacks: { label: i => i.raw.label + ': $' + i.raw.y.toFixed(3) + '/oz' } } },
      scales: { x: { title: { display: true, text: 'Pack size (oz; liquids in fl oz)' } }, y: { title: { display: true, text: 'Regular price per oz, $' } } } } });
  $('t_ppa').innerHTML = rows.slice().sort((a, b) => (a.opp === 'No action') - (b.opp === 'No action') || b.idx - a.idx).map(x =>
    `<tr><td>${x.product}</td><td class="num">${x.idx.toFixed(0)}</td><td class="num">${x.e == null ? '–' : x.e.toFixed(2)}</td><td>${x.opp}${x.inv ? ' (vs ' + x.inv + ')' : ''}</td></tr>`).join('');
}
$('pp').addEventListener('change', runPpa); runPpa();

$('t_dq').innerHTML = D.dq.map(x => `<tr><td>${x.check}</td><td class="num">${x.rows.toLocaleString('en-US')}</td><td>${x.note}</td></tr>`).join('');
</script></body></html>
"""


def main():
    data = build_data()
    html = HTML.replace("__DATA__", json.dumps(data, separators=(",", ":"))).replace("__REPO__", REPO)
    (DOCS / "dashboard.html").write_text(html, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    print("dashboard ->", DOCS / "dashboard.html", f"{len(html) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
