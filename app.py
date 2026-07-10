"""SEO KPI Extractor — Streamlit app.

Deploy once, share the URL; anyone can enter a URL + date range and pull the report.
"""
from __future__ import annotations

import base64
import pathlib
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

import settings
from daterange import (COMPARISONS, PRESETS, iso, previous_range, resolve_range)
from kpi_builder import build_rows, to_flat_dict
from connectors import ahrefs_api as c_ahrefs
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


# ----------------------------------------------------------------------------- brand assets
def _logo_b64(name: str) -> str:
    """Load a PNG from ./assets and return base64, or '' if it's not there."""
    try:
        p = pathlib.Path(__file__).parent / "assets" / name
        return base64.b64encode(p.read_bytes()).decode()
    except Exception:  # noqa: BLE001
        return ""

TF_LOGO = _logo_b64("think_forge.png")
OP_LOGO = _logo_b64("opositive.png")


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
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700;800&family=Rajdhani:wght@500;600;700&family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

        /* futuristic black canvas with red glow (AI Forge) */
        .stApp {
          background:
            radial-gradient(1100px 520px at 50% -8%, rgba(218,18,32,0.16), transparent 60%),
            radial-gradient(820px 500px at 100% 0%, rgba(218,18,32,0.06), transparent 55%),
            #07070A;
        }
        .block-container {max-width: 960px; padding-top: 3rem;}

        /* ---- header ---- */
        .topbar {display:flex; align-items:center; justify-content:space-between; margin:.4rem 0 .6rem;}
        .topbar .op {display:flex; align-items:center; gap:10px;}
        .topbar .op img {height:26px;}
        .topbar .op span {font-family:'Rajdhani',sans-serif; font-weight:600; letter-spacing:.16em;
                          text-transform:uppercase; font-size:.78rem; color:#9AA0AA;}
        .topbar .pb {font-family:'Rajdhani',sans-serif; font-weight:600; letter-spacing:.18em;
                     text-transform:uppercase; font-size:.7rem; color:#6C7079;}
        .hero {display:flex; align-items:center; gap:20px; margin:.4rem 0 .1rem;}
        .hero img {height:92px; filter: drop-shadow(0 0 22px rgba(60,150,255,.22));}
        .hero .wm {font-family:'Orbitron',sans-serif; font-weight:800; font-size:2.05rem;
                   letter-spacing:.02em; color:#F4F5F7; line-height:1.03;
                   text-shadow:0 0 26px rgba(218,18,32,.35);}
        .hero .wm .dot {color:#DA1220;}
        .hero .wm .sub {display:block; font-family:'Rajdhani',sans-serif; font-weight:600;
                        font-size:.86rem; letter-spacing:.22em; text-transform:uppercase;
                        color:#8A8F98; margin-top:.35rem; text-shadow:none;}
        .subhead {color:#8A8F98; font-family:'Rajdhani',sans-serif; letter-spacing:.02em;
                  font-size:.98rem; margin:.35rem 0 1.3rem;}

        /* ---- section rule labels (red marker bar, like the deck) ---- */
        .rulelabel {font-family:'Rajdhani',sans-serif; font-weight:700; font-size:.82rem;
                    letter-spacing:.2em; text-transform:uppercase; color:#F2413A;
                    margin:1.4rem 0 .35rem; padding-left:12px; border-left:3px solid #DA1220;}

        /* ---- inputs ---- */
        textarea, .stTextInput input {font-family:'IBM Plex Mono',monospace !important;
                    font-size:.82rem !important; background:#0E0E14 !important; color:#E7E9EC !important;
                    border:1px solid #26262E !important; border-radius:8px !important;}
        textarea:focus, .stTextInput input:focus {border-color:#DA1220 !important;
                    box-shadow:0 0 0 2px rgba(218,18,32,.25) !important;}
        label, .stSelectbox label, .stDateInput label {color:#AEB3BB !important;
                    font-family:'Rajdhani',sans-serif !important; font-weight:600 !important;
                    letter-spacing:.06em !important;}

        /* ---- buttons ---- */
        div.stButton>button {background:#DA1220; color:#fff; border:0; border-radius:9px;
                    font-family:'Rajdhani',sans-serif; font-weight:700; letter-spacing:.12em;
                    text-transform:uppercase; height:48px; width:100%;
                    box-shadow:0 0 20px rgba(218,18,32,.35);}
        div.stButton>button:hover {background:#F0152A; color:#fff;
                    box-shadow:0 0 30px rgba(218,18,32,.55);}
        .stDownloadButton>button {background:#14141B; color:#F4F5F7; border:1px solid #DA1220;
                    border-radius:9px; font-family:'Rajdhani',sans-serif; font-weight:700;
                    letter-spacing:.1em; text-transform:uppercase; box-shadow:none;}
        .stDownloadButton>button:hover {background:#1C1C25; color:#fff;}
        .stLinkButton>a {background:#DA1220 !important; color:#fff !important; border:0 !important;
                    font-family:'Rajdhani',sans-serif !important; font-weight:700 !important;
                    letter-spacing:.1em !important; text-transform:uppercase !important;
                    box-shadow:0 0 20px rgba(218,18,32,.35) !important;}

        /* ---- KPI table ---- */
        table.kpi {width:100%; border-collapse:collapse; font-size:.9rem;
                   border-left:3px solid #DA1220; background:#0D0D13;
                   box-shadow:0 0 30px rgba(0,0,0,.4);}
        table.kpi th {font-family:'Rajdhani',sans-serif; font-size:.72rem; letter-spacing:.14em;
                   font-weight:700; text-transform:uppercase; text-align:left; color:#8A8F98;
                   padding:11px 14px; border-bottom:1px solid #22222B; background:#101017;}
        table.kpi td {padding:11px 14px; border-bottom:1px solid #191921; color:#E7E9EC;}
        table.kpi td.num {font-family:'Space Grotesk',sans-serif; font-weight:600;
                   font-variant-numeric:tabular-nums; text-align:right; color:#F4F5F7;}
        table.kpi td.src {font-family:'IBM Plex Mono',monospace; font-size:.72rem; color:#71767F;}
        table.kpi tr:hover td {background:rgba(218,18,32,.05);}

        .chip {font-family:'Rajdhani',sans-serif; font-weight:700; font-size:.82rem;
               padding:2px 9px; border-radius:6px; letter-spacing:.04em;}
        .up {color:#2ED573; background:rgba(46,213,115,.12);}
        .down {color:#FF4757; background:rgba(255,71,87,.12);}
        .flat {color:#8A8F98; background:rgba(138,143,152,.12);}
        hr {border-color:#1E1E26;}
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

_tf = f'<img src="data:image/png;base64,{TF_LOGO}" alt="Think Forge">' if TF_LOGO else ''
_op = f'<img src="data:image/png;base64,{OP_LOGO}" alt="opositive.io">' if OP_LOGO else ''
st.markdown(f"""
<div class="topbar">
  <div class="op">{_op}<span>opositive.io</span></div>
  <div class="pb">Powered by Think Forge</div>
</div>
<div class="hero">
  {_tf}
  <div class="wm">SEO KPI EXTRACTOR<span class="dot">.</span>
    <span class="sub">Think Forge · Search Performance Intelligence</span>
  </div>
</div>
<div class="subhead">Enter a site and a date range, hit Start, and get the KPI report in Google Sheets.</div>
""", unsafe_allow_html=True)

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

        status.update(label="Extraction complete", state="complete")

    rows = build_rows(results["ga4"], results["gsc"], results["psi"],
                      results["ahrefs"])
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

    # warnings for failed sources
    warns = [f"{k.upper()}: {v['error']}" for k, v in results.items()
             if v.get("status") == "error"]

    # write to Google Sheet (once, here — not on every rerun)
    sheet_url = sheet_err = None
    if creds:
        sheet = c_sheets.write_sheet(creds, rows, meta, comparison_on, cfg["output_sheet_id"])
        if sheet.get("status") == "ok":
            sheet_url = sheet["url"]
        else:
            sheet_err = sheet.get("error")

    # CSV bytes (built once)
    df = pd.DataFrame([{"Metric": r["metric"], "Current": r["current"],
                        "Previous": r["previous"],
                        "Change %": r["change_pct"], "Source": r["source"]} for r in rows])
    csv_bytes = df.to_csv(index=False).encode()

    # optional AI analysis (once)
    analysis = c_llm.run_prompt(
        custom_prompt.strip(), to_flat_dict(rows), meta, cfg["llm_provider"],
        {"gemini_key": cfg["gemini_key"], "gemini_model": cfg["gemini_model"],
         "anthropic_key": cfg["anthropic_key"], "anthropic_model": cfg["anthropic_model"]})

    # stash everything so the report + RCA button survive Streamlit reruns
    st.session_state["extraction"] = {
        "rows": rows, "meta": meta, "comparison_on": comparison_on,
        "warns": warns, "sheet_url": sheet_url, "sheet_err": sheet_err,
        "csv_bytes": csv_bytes, "csv_name": f"{domain}_kpis.csv",
        "analysis": analysis,
    }
    st.session_state.pop("rca_docx", None)  # clear any RCA from a previous run

# ----------------------------------------------------------------------------- results
ex = st.session_state.get("extraction")
if ex:
    st.subheader("KPI report")
    render_table(ex["rows"], ex["comparison_on"])

    if ex["warns"]:
        st.warning("Some sources didn't return data:\n\n- " + "\n- ".join(ex["warns"]))

    if ex["sheet_url"]:
        st.link_button("Open Google Sheet", ex["sheet_url"], type="primary")
    elif ex["sheet_err"]:
        st.info(f"Sheet not written: {ex['sheet_err']}")

    st.download_button("Download CSV", ex["csv_bytes"],
                       file_name=ex["csv_name"], mime="text/csv")

    if ex["analysis"]:
        st.subheader("AI analysis")
        st.markdown(ex["analysis"])

    # ---- Week-on-Week RCA (Word) -------------------------------------------
    st.markdown("---")
    st.markdown('<div class="rulelabel">Root-cause analysis (WoW)</div>',
                unsafe_allow_html=True)
    st.caption("Builds a full Week-on-Week RCA in Word — KPI matrix from your data, "
               "analysis & recommendations written by Claude.")
    if st.button("Generate RCA report (Word)", type="primary"):
        with st.spinner("Claude is writing the WoW RCA…"):
            try:
                import rca_report
                st.session_state["rca_docx"] = rca_report.generate_rca_docx(
                    ex["rows"], ex["meta"], cfg, ex["comparison_on"])
            except Exception as e:  # noqa: BLE001
                st.error(f"RCA generation failed: {e}")

    if st.session_state.get("rca_docx"):
        st.download_button(
            "⬇  Download RCA (.docx)", st.session_state["rca_docx"],
            file_name=f"{ex['meta']['domain']}_WoW_RCA.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        st.success("RCA ready — click to download.")

    # ---- Verify via Claude Desktop (GA / GSC connectors) + run the WoW skill ----
    with st.expander("Verify in Claude Desktop (GA / GSC connectors) + run the WoW RCA skill"):
        import rca_report
        brief = rca_report.build_claude_desktop_brief(
            ex["rows"], ex["meta"], ex["comparison_on"])
        st.caption("This app can't reach your Claude Desktop connectors/skills directly. "
                   "Copy the brief below into Claude Desktop — it will pull the data using your "
                   "Google Analytics & Search Console connectors, cross-check these numbers, "
                   "then run the wow-rca-report skill.")
        st.code(brief, language="markdown")   # the code box has a built-in copy button
        st.download_button("Download brief (.md)", brief.encode(),
                           file_name=f"{ex['meta']['domain']}_RCA_brief.md",
                           mime="text/markdown")
