# SEO KPI Extractor

A shareable web tool: enter a **website URL** + **date range** (with comparison),
paste your **NB / LLM regex** and an optional **custom prompt**, click **Start**, and
get a KPI report — shown on screen and written to **Google Sheets**.

Built so a non-technical client can just open the link and run it. All credentials
live on the server (yours), not with the client.

## Every client, automatically

The app auto-discovers **all GA4 properties and all Search Console sites** your service
account can access and shows them in a **Client dropdown** — no property IDs to type. The
GA4 property is auto-matched to the chosen Search Console site by domain (you can change it).
So the moment your service account is added to a new client's GA4 + GSC, that client appears
in the list. Any site not auto-listed can still be entered manually.

## KPIs produced

| Metric | Source |
|---|---|
| Total Users (Traffic Acquisition) | GA4 |
| Organic Sessions | GA4 |
| LLM Traffic | GA4 (session source ∩ LLM regex) |
| Overall Clicks / Impressions | Search Console |
| NB Clicks / Impressions | Search Console (query `excludingRegex`) |
| Avg CTR – NB | Search Console (NB clicks ÷ NB impressions) |
| DA (Domain Authority) | Moz-only → blank, or DataForSEO rank proxy (`DA_SOURCE`) |
| Spam Score | DataForSEO |
| DR (Domain Rating) | Ahrefs API |
| Referring Domains | Ahrefs API (DataForSEO fallback) |
| Desktop / Mobile Page Speed | PageSpeed Insights |

GA4 + GSC rows show **Current vs Previous vs Change %** when comparison is on.
The other rows are point-in-time (current only).

## What you configure once

1. **Google service account** (one JSON key) — used for GA4, Search Console and Sheets.
   - Enable **Analytics Data API**, **Search Console API**, **Google Sheets API** in Google Cloud.
   - Add the service-account email as a **Viewer** on each GA4 property and a **user** on each
     GSC property you want to report on.
   - If writing to a master workbook, give the service account **Editor** access to it.
2. **PageSpeed API key**.
3. **Ahrefs API token** (DR + Referring Domains) and **DataForSEO login/password**
   (Spam Score + Referring Domains fallback + optional DA proxy). No Apify needed.
   - `DA_SOURCE=none` leaves DA blank (Moz-only); `DA_SOURCE=dataforseo` fills it with
     DataForSEO's domain rank scaled to ~0–100, labelled as a proxy.
4. *(Optional)* an LLM key (Gemini or Anthropic) for the custom-prompt analysis.

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env          # fill in values; point GOOGLE_APPLICATION_CREDENTIALS at your JSON
streamlit run app.py
```

Open http://localhost:8501.

## Deploy so anyone can use it (Streamlit Community Cloud — free)

1. Push this folder to a **private GitHub repo**.
2. Go to https://share.streamlit.io → **New app** → pick the repo → main file `app.py`.
3. In **Settings → Secrets**, paste the contents of `.streamlit/secrets.toml.example`
   with your real values (including the `[gcp_service_account]` table — no key file needed on Cloud).
4. Deploy. You get a URL like `https://your-app.streamlit.app`.
5. Share that URL. Your client opens it, fills the form, clicks **Start**, and gets the sheet.
   (They can only pull data for properties your service account has access to.)

## Notes

- **Non-branded** uses GSC's `excludingRegex` on the `query` dimension — the exact manual method.
- **Date presets** end at *yesterday* to avoid GSC's 2–3 day data lag.
- Every connector fails independently — a missing key or a broken actor shows `ERR`/`— not
  configured` on that row only; the rest of the report still runs.
- No secrets are ever shown in the UI or sent to the LLM.

## Files

```
app.py                    Streamlit UI + orchestration
settings.py               secrets/env loader (works local + Streamlit Cloud)
daterange.py              presets + comparison windows
kpi_builder.py            assembles the KPI rows + % change
connectors/
  ga4.py                  GA4 Data API
  search_console.py       Search Console API
  pagespeed.py            PageSpeed Insights
  ahrefs_api.py           Ahrefs API v3 (DR + Referring Domains)
  dataforseo.py           DataForSEO (Spam Score, Ref Domains fallback, DA proxy)
  sheets.py               Google Sheets writer
  llm.py                  custom-prompt analysis (Gemini/Anthropic)
.streamlit/config.toml    theme
.streamlit/secrets.toml.example
.env.example
requirements.txt
```
