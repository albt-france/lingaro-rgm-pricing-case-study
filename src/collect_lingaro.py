"""Save a dated text snapshot of a few public Lingaro web pages.

Why: every fact about Lingaro in the report must point to a public page and a date.
How: download each page (robots.txt allows these paths), strip the HTML, keep the
visible text in data/raw/lingaro_site/<date>/<slug>.txt. The raw snapshot stays local
(it is Lingaro's content); only the short, sourced fact table data/public/lingaro_facts.csv
is published.

Usage:  python src/collect_lingaro.py
"""
import datetime as dt
import html
import re
import time
from pathlib import Path

import requests

BASE = "https://lingarogroup.com/"
PAGES = [
    "home",
    "about",
    "about/ai-at-lingaro",
    "services/marketing-commercial-analytics",
    "services/data-visualization",
    "case-studies",
    "case-studies/brand-guardian-creative-assets-compliance-consistency",
    "insights/cpg-case-study-ai-enhanced-price-elasticity-strategy-for-revenue-growth-management",
    "insights/understanding-price-elasticity-and-its-impact-on-consumers-and-business-strategy",
    "insights/your-promotions-show-uplift.-but-are-they-creating-demand",
    "insights/how-price-reductions-affect-retail-profitability",
    "insights/hidden-revenue-loss-in-cpg-sales-execution",
    "insights/lingaro-leads-major-contenders-in-value-delivered-in-retail-and-cpg-data-analytics-and-ai-services-peak-matrix-assessment",
    "insights/lingaro-positioned-as-a-leader-in-cpg-analytics-by-isg",
    "insights/lingaro-group-receives-eight-recognitions-from-great-place-to-work-in-2024",
    "careers",
    "careers/rgm-data-analyst",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (independent case study; low-rate research crawler)"}


def visible_text(page_html: str) -> str:
    """Very small HTML-to-text: drop scripts/styles, tags, collapse whitespace."""
    s = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", page_html)
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr)>", "\n", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in s.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def main():
    today = dt.date.today().isoformat()
    out = Path("data/raw/lingaro_site") / today
    out.mkdir(parents=True, exist_ok=True)
    for slug in PAGES:
        url = BASE + slug
        r = requests.get(url, headers=HEADERS, timeout=30)
        name = slug.replace("/", "__").replace(".", "")[:120] + ".txt"
        (out / name).write_text(f"URL: {url}\nRetrieved: {today}\nHTTP: {r.status_code}\n\n"
                                + visible_text(r.text), encoding="utf-8")
        print(r.status_code, url)
        time.sleep(2)  # be polite


if __name__ == "__main__":
    main()
