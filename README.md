# Multi-Source Job Scraper

Scrapes BI/Data jobs from **LinkedIn, Wuzzuf, Bayt, and Indeed** for Egypt,
plus **remote** roles in the US and Saudi Arabia (via LinkedIn).
Sends one email per run with a "🆕 New" section and "📋 Earlier today" section.

---

## Setup (same as before)

1. Create a new private GitHub repo
2. Upload: `scraper.py`, `seen_jobs.json`, `.github/workflows/scrape.yml`
3. Enable Actions (Actions tab → enable)
4. Settings → Actions → General → **Read and write permissions** → Save
5. Add secrets (Settings → Secrets → Actions):

| Secret | Required? | Notes |
|---|---|---|
| `GMAIL_ADDRESS` | ✅ Required | Your Gmail |
| `GMAIL_APP_PASSWORD` | ✅ Required | Gmail App Password |
| `LI_AT_COOKIE` | Optional | LinkedIn `li_at` cookie — improves results |
| `INDEED_COOKIE` | Optional | Indeed is heavily protected; without this it likely returns 0 results |
| `BAYT_COOKIE` | Optional | Improves Bayt reliability |
| `WUZZUF_COOKIE` | Optional | Rarely needed, Wuzzuf works without it |

If you don't have a cookie for Indeed/Bayt/Wuzzuf, just **leave the secret unset or empty** — the scraper skips it gracefully and uses the other sources.

---

## How to get each cookie (optional)

**Indeed:**
1. Log into indeed.com (or eg.indeed.com) in Chrome
2. F12 → Network tab → reload page → click any request to indeed.com
3. Copy the entire `Cookie:` request header value
4. Paste as `INDEED_COOKIE` secret

**Bayt / Wuzzuf:** same process — F12 → Network → Cookie header → paste as secret.

---

## What's in each email

- Color badge per source (LinkedIn / Wuzzuf / Bayt / Indeed)
- "Easy Apply" tag when LinkedIn shows it
- Posted date/time
- Direct Apply link
- New jobs section (green) + Earlier today section (gray)

---

## Remote jobs (US / KSA)

Searched via LinkedIn's remote filter for: Data Analyst, Business Intelligence
Analyst/Intelligence, Power BI — both US and Saudi Arabia. Edit `REMOTE_SEARCHES`
in `scraper.py` to add/remove searches.

---

## Trigger schedule

Same as your other repos — use cron-job.org with `repository_dispatch`
(`{"event_type": "run-scraper"}`) since GitHub's native cron is less precise.

---

## Notes on source reliability

- **LinkedIn** — works reliably without cookie, better with `li_at`
- **Wuzzuf** — works well without any cookie
- **Bayt** — HTML structure changes sometimes; may need selector tweaks over time
- **Indeed** — blocks anonymous requests (403). Needs `INDEED_COOKIE` to return results consistently
