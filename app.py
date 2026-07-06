"""SEO KPI Extractor — Streamlit app.

Deploy once, share the URL; anyone can enter a URL + date range and pull the report.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

import settings
from daterange import (COMPARISONS, PRESETS, iso, previous_range, resolve_range)
from kpi_builder import build_rows, to_flat_dict
from connectors import ahrefs_api as c_ahrefs
from connectors import dataforseo as c_dfs
from connectors import discovery
from connectors import ga4 as c_ga4
from connectors import llm as c_llm
from connectors import pagespeed as c_psi
from connectors import search_console as c_gsc
from connectors import sheets as c_sheets

DEFAULT_NB = (
    r"(?i)mint & co|mint & co.|mint uae|mintand|mint co|mint n co|mint&co|mint mena|"
    r"mint and co|mint agency|m int|mint and.co|brand mint|dubai|mint dubai|mint market|"
    r"mint and|mint real estate|mint fzco|min t|co mint|mint branding|mint development|"
    r"mint.co|mint property|mint performance marketing clients|"
    r"mint performance marketing contact number|mint performance marketing"
)
DEFAULT_LLM = (
    r"^.*(chatgpt\.com|perplexity(\.ai)?|gemini(\.google\.com)?|ai\s?mode|"
    r"copilot\.microsoft\.com|edgeservices\.bing\.com|deepseek|chat\.deepseek\.com|"
    r"you\.com|poe\.com|blackbox\.ai|agentgpt|wrtn\.ai|chat\.qwenlm\.ai|askaichat|"
    r"textcortex|huggingface\.co|doubao\.com|claude\.ai).*"
)

GA_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
ALL_SCOPES = GA_SCOPES + GSC_SCOPES + SHEETS_SCOPES


# ----------------------------------------------------------------------------- helpers
def domain_of(url: str) -> str:
    netloc = urlparse(url if "//" in url else f"https://{url}").netloc or url
    return netloc.replace("www.", "").strip("/")


def valid_regex(pattern: str) -> str | None:
    try:
        re.compile(pattern)
        return None
    except re.error as e:
        return str(e)


def _skip(reason: str) -> dict:
    return {"status": "not_configured", "error": reason}


def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
        .block-container {max-width: 940px; padding-top: 2.2rem;}
        .wordmark {font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:1.9rem;
                   letter-spacing:-0.02em; color:#141A16; margin-bottom:.15rem;}
        .wordmark .dot {color:#0E6E4E;}
        .subhead {color:#5B615B; font-size:.92rem; margin-bottom:1.4rem;}
        .rulelabel {font-family:'IBM Plex Mono',monospace; font-size:.72rem; letter-spacing:.14em;
                    text-transform:uppercase; color:#0E6E4E; margin:1.3rem 0 .3rem;}
        textarea {font-family:'IBM Plex Mono',monospace !important; font-size:.82rem !important;}
        div.stButton>button {background:#0E6E4E; color:#fff; border:0; border-radius:8px;
                    font-weight:600; height:46px; width:100%;}
        div.stButton>button:hover {background:#0B5A40; color:#fff;}
        /* KPI readout */
        table.kpi {width:100%; border-collapse:collapse; font-size:.9rem;
                   border-left:3px solid #0E6E4E; background:#fff;}
        table.kpi th {font-family:'IBM Plex Mono',monospace; font-size:.68rem; letter-spacing:.1em;
                   text-transform:uppercase; text-align:left; color:#5B615B;
                   padding:10px 14px; border-bottom:1px solid #E2E6E1;}
        table.kpi td {padding:11px 14px; border-bottom:1px solid #EEF1EE; color:#141A16;}
        table.kpi td.num {font-family:'Space Grotesk',sans-serif; font-weight:600;
                   font-variant-numeric:tabular-nums; text-align:right;}
        table.kpi td.src {font-family:'IBM Plex Mono',monospace; font-size:.72rem; color:#7A807A;}
        .chip {font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:.82rem;
                   padding:2px 8px; border-radius:20px;}
        .up {color:#0E6E4E; background:#E7F2EC;}
        .down {color:#B4341C; background:#F7E7E3;}
        .flat {color:#6B7280; background:#EEF1EE;}
        </style>
        """, unsafe_allow_html=True,
    )


def chip(change):
    if change is None:
        return '<span class="chip flat">—</span>'
    if change == float("inf"):
        return '<span class="chip up">NEW</span>'
    cls = "up" if change > 0 else ("down" if change < 0 else "flat")
    arrow = "▲" if change > 0 else ("▼" if change < 0 else "•")
    return f'<span class="chip {cls}">{arrow} {abs(change)}%</span>'


def render_table(rows, comparison_on):
    head = "<tr><th>Metric</th><th>Current</th>"
    if comparison_on:
        head += "<th>Previous</th><th>Change</th>"
    head += "<th>Source</th></tr>"
    body = ""
    for r in rows:
        body += "<tr>"
        body += f"<td>{r['metric']}</td>"
        body += f"<td class='num'>{r['current']}</td>"
        if comparison_on:
            body += f"<td class='num'>{r['previous']}</td>"
            body += f"<td class='num'>{chip(r['change_pct'])}</td>"
        body += f"<td class='src'>{r['source']}</td>"
        body += "</tr>"
    st.markdown(f"<table class='kpi'>{head}{body}</table>", unsafe_allow_html=True)


# ----------------------------------------------------------------------------- app
st.set_page_config(page_title="SEO KPI Extractor", page_icon="📈", layout="centered")
inject_css()
cfg = settings.defaults()

st.markdown('<div class="wordmark">SEO KPI Extractor<span class="dot">.</span></div>',
            unsafe_allow_html=True)
st.markdown('<div class="subhead">Enter a site and a date range, click Start, get the '
            'KPI report in Google Sheets.</div>', unsafe_allow_html=True)

# --- Inputs (no st.form, so the custom date pickers can appear dynamically) ---
@st.cache_data(ttl=3600, show_spinner="Loading your clients…")
def _discover():
    creds = settings.google_credentials(GA_SCOPES + GSC_SCOPES)
    return discovery.list_gsc_sites(creds), discovery.list_ga4_properties(creds)

url = gsc_property = ga4_property = ""
manual_mode = False
try:
    sites, ga4_props = _discover()
except Exception as e:  # noqa: BLE001
    sites, ga4_props = [], []
    manual_mode = True
    st.info(f"Couldn't auto-load your client list ({e}). Enter details manually below.")

if sites:
    site_choice = st.selectbox("Client", sites,
                               format_func=lambda s: discovery.site_domain(s))
    gsc_property = site_choice
    url = site_choice if "//" in site_choice else f"https://{discovery.site_domain(site_choice)}/"
    if ga4_props:
        guess = discovery.best_ga4_for(site_choice, ga4_props)
        ids = [p["id"] for p in ga4_props]
        idx = ids.index(guess) if guess in ids else 0
        ga4_choice = st.selectbox("GA4 property (auto-matched — change if needed)",
                                  ga4_props, index=idx,
                                  format_func=lambda p: f"{p['name']} · {p['id']}")
        ga4_property = ga4_choice["id"]
    st.caption(f"Will pull: {url}  ·  GSC `{gsc_property}`  ·  GA4 `{ga4_property or '—'}`")
else:
    manual_mode = True

if manual_mode:
    url = st.text_input("Website URL", value=url, placeholder="https://example.com/")
    mc1, mc2 = st.columns(2)
    gsc_property = mc1.text_input("GSC property", value=gsc_property,
                                  placeholder="https://example.com/ or sc-domain:example.com")
    ga4_property = mc2.text_input("GA4 property id", value=ga4_property,
                                  placeholder="e.g. 484638180")

c1, c2 = st.columns(2)
preset = c1.selectbox("Date range", list(PRESETS.keys()),
                      format_func=lambda k: PRESETS[k])
comparison = c2.selectbox("Comparison", list(COMPARISONS.keys()),
                          format_func=lambda k: COMPARISONS[k])

custom_start = custom_end = None
if preset == "custom":
    d1, d2 = st.columns(2)
    custom_start = d1.date_input("Start", value=date.today() - timedelta(days=30))
    custom_end = d2.date_input("End", value=date.today() - timedelta(days=1))

# resolve + preview the range
range_err = None
try:
    cur_start, cur_end = resolve_range(preset, custom_start, custom_end)
    prev = previous_range(cur_start, cur_end, comparison)
    preview = f"{iso(cur_start)} → {iso(cur_end)}"
    if prev:
        preview += f"  vs  {iso(prev[0])} → {iso(prev[1])}"
    st.caption(f"Reporting window: {preview}")
except ValueError as e:
    range_err = str(e)
    st.warning(range_err)

st.markdown('<div class="rulelabel">Non-branded regex (excluded from GSC)</div>',
            unsafe_allow_html=True)
nb_regex = st.text_area("nb", value=DEFAULT_NB, height=90, label_visibility="collapsed")

st.markdown('<div class="rulelabel">LLM regex (GA4 session source)</div>',
            unsafe_allow_html=True)
llm_regex = st.text_area("llm", value=DEFAULT_LLM, height=90, label_visibility="collapsed")

st.markdown('<div class="rulelabel">Custom prompt (optional)</div>', unsafe_allow_html=True)
custom_prompt = st.text_area(
    "prompt", height=80, label_visibility="collapsed",
    placeholder="Optional: extra instructions or an analysis request over the KPIs.")

start = st.button("Start extraction", type="primary", disabled=bool(range_err))

# ----------------------------------------------------------------------------- run
if start:
    # validate
    if not url.strip():
        st.error("Enter a website URL first.")
        st.stop()
    for label, pattern in [("NB regex", nb_regex), ("LLM regex", llm_regex)]:
        err = valid_regex(pattern)
        if err:
            st.error(f"{label} is invalid: {err}")
            st.stop()

    domain = domain_of(url)
    gsc_site = (gsc_property.strip() or url.strip())
    ga4_id = ga4_property.strip()
    cur = (iso(cur_start), iso(cur_end))
    prev_iso = (iso(prev[0]), iso(prev[1])) if prev else None
    comparison_on = prev is not None

    # google creds (shared) — degrade gracefully if absent
    creds = None
    try:
        creds = settings.google_credentials(ALL_SCOPES)
    except Exception as e:  # noqa: BLE001
        st.warning(f"Google credentials not configured — GA4/GSC/Sheets will be skipped. ({e})")

    results = {}
    with st.status("Extracting KPIs…", expanded=True) as status:
        st.write("Search Console…")
        results["gsc"] = (c_gsc.get_search_console(creds, gsc_site, cur, prev_iso, nb_regex)
                          if creds and gsc_site else _skip("Google creds / GSC property"))

        st.write("Google Analytics 4…")
        results["ga4"] = (c_ga4.get_ga4(creds, ga4_id, cur, prev_iso, llm_regex)
                          if creds and ga4_id else _skip("GA4 property / creds"))

        st.write("PageSpeed Insights…")
        results["psi"] = c_psi.get_pagespeed(url.strip(), cfg["psi_key"])

        st.write("Ahrefs API…")
        results["ahrefs"] = c_ahrefs.get_ahrefs(cfg["ahrefs_token"], domain, cur[1])

        st.write("DataForSEO…")
        results["dfs"] = c_dfs.get_dataforseo(cfg["dfs_login"], cfg["dfs_password"],
                                              domain, cfg["da_source"])

        status.update(label="Extraction complete", state="complete")

    rows = build_rows(results["ga4"], results["gsc"], results["psi"],
                      results["ahrefs"], results["dfs"])
    # Prompt-driven extra metrics (safe catalog; appended as "from prompt" rows)
    if custom_prompt.strip():
        try:
            from connectors import extra_metrics
            rows += extra_metrics.fetch_from_prompt(custom_prompt, creds, ga4_id, gsc_site, cur)
        except Exception as _e:
            st.info(f"Prompt extras skipped: {_e}")
    meta = {"url": url.strip(), "domain": domain, "range": " vs ".join(filter(None, [
        f"{cur[0]}…{cur[1]}", f"{prev_iso[0]}…{prev_iso[1]}" if prev_iso else ""])),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")}

    st.subheader("KPI report")
    render_table(rows, comparison_on)

    # warnings for failed sources
    warns = [f"{k.upper()}: {v['error']}" for k, v in results.items()
             if v.get("status") == "error"]
    if warns:
        st.warning("Some sources didn't return data:\n\n- " + "\n- ".join(warns))

    # write to Google Sheet
    if creds:
        sheet = c_sheets.write_sheet(creds, rows, meta, comparison_on, cfg["output_sheet_id"])
        if sheet.get("status") == "ok":
            st.link_button("Open Google Sheet", sheet["url"], type="primary")
        else:
            st.info(f"Sheet not written: {sheet.get('error')}")

    # CSV download
    df = pd.DataFrame([{"Metric": r["metric"], "Current": r["current"],
                        "Previous": r["previous"],
                        "Change %": r["change_pct"], "Source": r["source"]} for r in rows])
    st.download_button("Download CSV", df.to_csv(index=False).encode(),
                       file_name=f"{domain}_kpis.csv", mime="text/csv")

    # optional AI analysis
    analysis = c_llm.run_prompt(
        custom_prompt.strip(), to_flat_dict(rows), meta, cfg["llm_provider"],
        {"gemini_key": cfg["gemini_key"], "gemini_model": cfg["gemini_model"],
         "anthropic_key": cfg["anthropic_key"], "anthropic_model": cfg["anthropic_model"]})
    if analysis:
        st.subheader("AI analysis")
        st.markdown(analysis)
