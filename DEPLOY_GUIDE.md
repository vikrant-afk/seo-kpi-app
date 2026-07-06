# Deployment Guide — SEO KPI Extractor (self-serve, all clients)

Follow this once (~30–45 min). At the end you'll have a public link like
`https://your-app.streamlit.app` that anyone can open, pick a client, and pull the report.
No coding. Where a button label differs slightly from what's written here, the section name
in **bold** tells you what to look for.

> You'll do 8 phases: **Google Cloud → grant access → PageSpeed key → Apify → GitHub →
> Streamlit → secrets → test.** Do them in order.

---

## What you need before starting
- A Google account that can access your clients' GA4 + Search Console.
- A credit-card-free **Google Cloud** account (free tier is enough).
- An **Apify** account (for Moz DA/Spam + Ahrefs DR/Referring Domains).
- A **GitHub** account (free).
- A **Streamlit Community Cloud** account (free — you sign in with GitHub).
- The `seo_kpi_app` folder I built (all files, including the `connectors/` and `.streamlit/` subfolders).

---

## Phase 1 — Google Cloud: project, APIs, service account key

1. Go to **console.cloud.google.com** and sign in.
2. Top bar → project dropdown → **New Project** → name it `seo-kpi-tool` → **Create**, then
   select it.
3. Left menu → **APIs & Services → Library**. Search for and click **Enable** on each of these
   (five total):
   - Google Analytics Data API
   - Google Analytics Admin API
   - Google Search Console API
   - Google Sheets API
   - PageSpeed Insights API
4. Left menu → **APIs & Services → Credentials → Create credentials → Service account**.
   - Name: `kpi-bot` → **Create and continue** → skip the optional roles → **Done**.
5. Open the new service account (click its name) → **Keys** tab → **Add key → Create new key →
   JSON → Create**. A `.json` file downloads. **Keep it safe — this is the master credential.**
6. Copy the service account **email** (looks like
   `kpi-bot@seo-kpi-tool.iam.gserviceaccount.com`). You'll paste it into each client next.

---

## Phase 2 — Give the service account access to each client

This is what lets the app read each client's data. Do it for every client you want in the tool.

**Google Analytics 4** (fastest at account level, which covers all that account's properties):
1. Go to **analytics.google.com** → **Admin** (gear, bottom-left).
2. Under the **Account** column → **Account Access Management** → **+** → **Add users**.
3. Paste the service-account email → role **Viewer** → untick "Notify by email" → **Add**.
4. Repeat for each Analytics account. (If you prefer, add at the **Property** level instead —
   **Property Access Management** — but account level is fewer clicks.)

**Google Search Console** (must be done per site — GSC has no account level):
1. Go to **search.google.com/search-console** → pick a client property.
2. **Settings → Users and permissions → Add user**.
3. Paste the service-account email → permission **Full** (or Restricted) → **Add**.
4. Repeat for each client site.

> The app auto-lists whatever this service account can see, so anything you add here shows up
> in the client dropdown automatically.

---

## Phase 3 — PageSpeed API key
1. In **Cloud Console → APIs & Services → Credentials → Create credentials → API key**.
2. Copy the key. (Optional: click **Restrict key** → restrict to *PageSpeed Insights API*.)

---

## Phase 4 — Ahrefs API + DataForSEO (no Apify)
1. **Ahrefs API token** — in your Ahrefs account go to your **API / API keys** settings and
   copy your **API v3 token**. This provides **DR** and **Referring Domains**.
2. **DataForSEO login + password** — from **dataforseo.com** (your API credentials). This
   provides **Spam Score**, a **Referring Domains** fallback, and (optionally) a DA proxy.
3. **DA (Domain Authority)** — this is a Moz-only number, so:
   - Leave `DA_SOURCE = "none"` → the DA row shows `N/A · Moz` (honest blank), **or**
   - Set `DA_SOURCE = "dataforseo"` → the DA row shows DataForSEO's domain rank scaled to
     ~0–100, clearly labelled "rank proxy" (not true Moz DA).

> Every other metric works with just these two. No Apify token, no actors, no field mapping.

---

## Phase 5 — Put the app on GitHub
1. Go to **github.com** → **New repository** → name `seo-kpi-app` → set **Private** → **Create
   repository**.
2. On the repo page → **Add file → Upload files**.
3. Drag in **everything** from the `seo_kpi_app` folder. Keep the folder structure — the
   `connectors/` folder and the `.streamlit/` folder must come along. (If the drag-and-drop
   flattens folders, tell me and I'll send a ready-made zip.)
4. Scroll down → **Commit changes**.

Do **not** upload your service-account JSON or `.env` to GitHub. Secrets go in Streamlit only.

---

## Phase 6 — Deploy on Streamlit Community Cloud
1. Go to **share.streamlit.io** → **Continue with GitHub** → authorize.
2. **Create app** → **Deploy a public app from GitHub**.
3. Repository: `your-name/seo-kpi-app` · Branch: `main` · Main file path: **`app.py`**.
4. Click **Deploy**. It will start building (it may show errors until you add secrets — that's
   expected, continue to Phase 7).

---

## Phase 7 — Add your secrets (the important bit)
1. In the app, open the **⋮ menu (top-right) → Settings → Secrets** (or the **Secrets** box shown
   during deploy).
2. Paste the block below and fill in your real values. For the `[gcp_service_account]` table,
   copy the matching fields straight from your downloaded JSON key file (keep the private key
   inside the triple quotes exactly as-is, including the BEGIN/END lines).

```toml
PAGESPEED_API_KEY = "your-pagespeed-key"

AHREFS_API_TOKEN = "your-ahrefs-api-v3-token"
DATAFORSEO_LOGIN = "your-dataforseo-login"
DATAFORSEO_PASSWORD = "your-dataforseo-password"
DA_SOURCE = "none"             # none = blank DA (Moz-only) | dataforseo = rank proxy

OUTPUT_SHEET_ID = ""          # leave blank = new sheet each run; or paste a master workbook id

LLM_PROVIDER = "none"          # gemini | anthropic | none
GEMINI_API_KEY = ""
GEMINI_MODEL = "gemini-1.5-pro"
ANTHROPIC_API_KEY = ""
ANTHROPIC_MODEL = "claude-sonnet-5"

[gcp_service_account]
type = "service_account"
project_id = "seo-kpi-tool"
private_key_id = "...from json..."
private_key = """-----BEGIN PRIVATE KEY-----
...from json (keep the newlines)...
-----END PRIVATE KEY-----
"""
client_email = "kpi-bot@seo-kpi-tool.iam.gserviceaccount.com"
client_id = "...from json..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "...from json..."
```

3. **Save**. The app reboots. `GA4_PROPERTY_ID` / `GSC_PROPERTY` are **not** needed — the app
   auto-discovers clients.

> Using a master Google Sheet (OUTPUT_SHEET_ID)? Open that sheet → **Share** → add the
> service-account email as **Editor**.

---

## Phase 8 — Test, then share
1. Open your app URL. You should see a **Client** dropdown listing all your GA4/GSC clients.
2. Pick e.g. **mintand.co**, choose a date range, click **Start extraction**.
3. Confirm the KPI table fills in and the **Open Google Sheet** button works.
4. Share the URL with whoever needs to pull reports. They only ever see the form — never your keys.

---

## Troubleshooting (symptom → fix)
- **"Couldn't auto-load your client list"** → the *Analytics Admin API* isn't enabled, or the
  service account isn't added to any Analytics account. Re-check Phase 1 step 3 and Phase 2.
- **A client's GA4 rows show `ERR`** → service account isn't a **Viewer** on that property, or
  the *Analytics Data API* is off.
- **GSC rows show `ERR`** → service account not added to that Search Console property (Phase 2).
- **DR / Spam / Referring Domains show `— not configured`** → the Ahrefs token or DataForSEO
  login/password is missing. If they show `ERR`, the credential is wrong or out of quota.
- **DA always `N/A · Moz`** → expected while `DA_SOURCE = "none"`. Set it to `dataforseo` for a
  labelled rank proxy, or leave blank if you only trust real Moz DA.
- **Sheet not written** → *Sheets API* off, or (master workbook) not shared with the service
  account as Editor.
- **App is asleep** → free Streamlit apps sleep after inactivity; the first visitor taps
  "wake" and it starts in ~30s.

---

## Adding a new client later (no redeploy)
1. Add the service-account email to the new client's **GA4** (Viewer) and **Search Console** (user).
2. Wait a few minutes (the app caches the client list for ~1 hour; use **Rerun** / clear cache
   to refresh sooner).
3. The client now appears in the dropdown. Done — no code changes.

## Updating the app later
Edit files in the GitHub repo (or re-upload) → commit → Streamlit redeploys automatically.
