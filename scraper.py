import requests
from bs4 import BeautifulSoup
import json
import os
import smtplib
import time
import random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

# ──────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────
SENDER_EMAIL   = os.environ.get("GMAIL_ADDRESS")
GMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

# Optional cookies — leave secret empty/unset if you don't have them.
# Adding them improves results / avoids blocks, but everything works without them too.
LI_AT_COOKIE     = os.environ.get("LI_AT_COOKIE", "")       # LinkedIn li_at cookie
INDEED_COOKIE    = os.environ.get("INDEED_COOKIE", "")      # Indeed full cookie string
BAYT_COOKIE      = os.environ.get("BAYT_COOKIE", "")        # Bayt full cookie string
WUZZUF_COOKIE    = os.environ.get("WUZZUF_COOKIE", "")      # Wuzzuf full cookie string (rarely needed)

# ── ADD OR REMOVE RECIPIENT EMAILS HERE ────────
RECIPIENT_EMAILS = [
    "ibrahem.ramadan.ahmed@gmail.com",
    # "colleague@company.com",
]
# ───────────────────────────────────────────────

SEEN_JOBS_FILE = "seen_jobs.json"

# Keywords searched for Egypt-based jobs
KEYWORDS_EGYPT = [
    # Data Analyst variants
    "Data Analyst",
    "Business Intelligence Analyst",
    "BI Analyst",
    "Business Intelligence",
    "Power BI",
    "Power BI Developer",
    "Power BI Analyst",
    "Power BI Engineer",
    "Data Visualization",
    "Data Visualization Analyst",
    "Reporting Analyst",
    "Business Analyst",
    "Dashboard Developer",
    "Dashboard Analyst",
    "Data Insights Analyst",
    "Analytics Specialist",
    "Analytics Analyst",
    "MIS Analyst",
    "MIS Executive",
    "Data Specialist",
    "SQL Analyst",
    "Data Management",
    "Data Engineer",
    "Insights Analyst",
    "Data Reporting",
    "Data Operations",
    "Data Coordinator",
    "Excel Analyst",
    "Tableau Analyst",
    "Tableau Developer",
    "Looker Analyst",
    "Qlik Analyst",
    "ETL Analyst",
    "Analytics Engineer",
    "Decision Support Analyst",
    "Performance Analyst",
    "Reporting Engineer",
    "BI Developer",
    "BI Engineer",
    "BI Specialist",
    "BI Manager",
    "Senior Analyst",
    "Data Science Analyst",
]

REMOTE_SEARCHES = [
    # United States
    {"keyword": "Data Analyst",                   "location": "United States"},
    {"keyword": "Business Intelligence Analyst",  "location": "United States"},
    {"keyword": "BI Analyst",                     "location": "United States"},
    {"keyword": "Power BI",                       "location": "United States"},
    {"keyword": "Reporting Analyst",              "location": "United States"},
    {"keyword": "Analytics Engineer",             "location": "United States"},

    # Saudi Arabia
    {"keyword": "Data Analyst",                   "location": "Saudi Arabia"},
    {"keyword": "Business Intelligence",          "location": "Saudi Arabia"},
    {"keyword": "BI Analyst",                     "location": "Saudi Arabia"},
    {"keyword": "Power BI",                       "location": "Saudi Arabia"},
    {"keyword": "Reporting Analyst",              "location": "Saudi Arabia"},

    # United Arab Emirates
    {"keyword": "Data Analyst",                   "location": "United Arab Emirates"},
    {"keyword": "Business Intelligence",          "location": "United Arab Emirates"},
    {"keyword": "BI Analyst",                     "location": "United Arab Emirates"},
    {"keyword": "Power BI",                       "location": "United Arab Emirates"},
    {"keyword": "Reporting Analyst",              "location": "United Arab Emirates"},

    # Kuwait
    {"keyword": "Data Analyst",                   "location": "Kuwait"},
    {"keyword": "Business Intelligence",          "location": "Kuwait"},
    {"keyword": "BI Analyst",                     "location": "Kuwait"},
    {"keyword": "Power BI",                       "location": "Kuwait"},

    # Qatar
    {"keyword": "Data Analyst",                   "location": "Qatar"},
    {"keyword": "Business Intelligence",          "location": "Qatar"},
    {"keyword": "BI Analyst",                     "location": "Qatar"},
    {"keyword": "Power BI",                       "location": "Qatar"},
]

# ── TITLE FILTER — case-insensitive substring match ──
# A job passes if its title contains ANY of these strings.
# Keep these short/partial so they catch variations naturally.
TITLE_MUST_CONTAIN = [
    # BI / Business Intelligence — catches "BI Analyst", "Sr. BI", "BI Developer", etc.
    " bi ",             # space-padded to avoid false matches like "mobile"
    "bi analyst",
    "bi developer",
    "bi engineer",
    "bi specialist",
    "bi manager",
    "business intel",   # catches "business intelligence" + "business intel"
    "business analyst",

    # Data Analyst family
    "data analyst",
    "data analysis",
    "data specialist",
    "data coordinator",
    "data insights",
    "data reporting",
    "data management",
    "data operations",
    "data engineer",
    "data science",
    "data visualization",

    # Reporting / Dashboards
    "reporting analyst",
    "reporting engineer",
    "dashboard",

    # Analytics
    "analytics",        # catches "analytics analyst", "analytics engineer", "analytics specialist"
    "insights analyst",

    # Tools-based titles
    "power bi",
    "tableau",
    "looker",
    "qlik",
    "sql analyst",
    "excel analyst",
    "etl analyst",

    # MIS
    "mis analyst",
    "mis executive",

    # Other
    "decision support",
    "performance analyst",
]


def is_relevant_title(title: str) -> bool:
    """
    Case-insensitive substring match. Space-pads the title so that
    ' bi ' correctly matches titles starting or ending with 'BI'.
    """
    import re
    normalized = f" {title.lower().strip()} "
    normalized = re.sub(r"[^a-z0-9 ]", " ", normalized)
    normalized = re.sub(r" +", " ", normalized)
    return any(kw in normalized for kw in TITLE_MUST_CONTAIN)

# ───────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def cookie_dict(cookie_string):
    """Convert 'a=1; b=2' style cookie header into a dict."""
    result = {}
    if not cookie_string:
        return result
    for part in cookie_string.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            result[k] = v
    return result


# ──────────────────────────────────────────────
#  SEEN JOBS — resets daily, stores full job data
# ──────────────────────────────────────────────
def load_seen_jobs():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            data = json.load(f)
        if data.get("date") == today:
            jobs = data.get("jobs", [])
            print(f"   Same day ({today}) — keeping {len(jobs)} jobs already found today")
            return today, jobs
        else:
            print(f"   New day ({today}) — resetting (was {data.get('date')})")
            return today, []
    return today, []

def save_seen_jobs(today, jobs):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump({"date": today, "jobs": jobs}, f)


def make_job(source, title, company, location, link, posted, easy_apply=False, region="Egypt"):
    return {
        "id":          f"{source}::{link}",
        "source":      source,
        "title":       title,
        "company":     company,
        "location":    location,
        "link":        link,
        "posted":      posted,
        "easy_apply":  easy_apply,
        "region":      region,
        "found_at":    datetime.now(timezone.utc).isoformat(),
    }


# ──────────────────────────────────────────────
#  LINKEDIN
# ──────────────────────────────────────────────
def scrape_linkedin(keyword, location="Egypt"):
    jobs = []
    params = {
        "keywords": keyword,
        "location": location,
        "f_TPR":    "r86400",
        "position": 1,
        "pageNum":  0,
    }
    if location != "Egypt":
        params["f_WT"] = "2"  # remote filter

    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    cookies = {}
    if LI_AT_COOKIE:
        cookies["li_at"] = LI_AT_COOKIE

    try:
        resp = requests.get(url, headers=HEADERS, params=params, cookies=cookies, timeout=15)
        if resp.status_code != 200:
            print(f"    [LinkedIn] status {resp.status_code} — skipping")
            return []

        soup  = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all("div", class_="base-card")

        for card in cards:
            try:
                job_id_tag = card.get("data-entity-urn", "")
                job_id     = job_id_tag.split(":")[-1] if job_id_tag else None
                if not job_id:
                    continue

                title_tag    = card.find("h3", class_="base-search-card__title")
                company_tag  = card.find("h4", class_="base-search-card__subtitle")
                location_tag = card.find("span", class_="job-search-card__location")
                time_tag     = card.find("time")

                title    = title_tag.get_text(strip=True)    if title_tag    else "N/A"
                company  = company_tag.get_text(strip=True)  if company_tag  else "N/A"
                loc      = location_tag.get_text(strip=True) if location_tag else location
                posted   = time_tag.get_text(strip=True)     if time_tag     else "Recently"

                if not is_relevant_title(title):
                    continue

                link = f"https://www.linkedin.com/jobs/view/{job_id}/"

                # Easy Apply badge (only visible to logged-in scrapes, best-effort)
                easy_apply = bool(card.find(string=lambda s: s and "Easy Apply" in s))

                region = "Egypt" if location == "Egypt" else f"Remote - {location}"
                jobs.append(make_job("LinkedIn", title, company, loc, link, posted, easy_apply, region=region))

            except Exception as e:
                print(f"    [LinkedIn] card error: {e}")
                continue

    except Exception as e:
        print(f"    [LinkedIn] request error: {e}")

    return jobs


# ──────────────────────────────────────────────
#  WUZZUF
# ──────────────────────────────────────────────
def scrape_wuzzuf(keyword):
    jobs = []
    url = "https://wuzzuf.net/search/jobs/"
    params = {"q": keyword, "a": "hpb"}
    cookies = cookie_dict(WUZZUF_COOKIE)

    try:
        resp = requests.get(url, headers=HEADERS, params=params, cookies=cookies, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        links = soup.find_all("a", href=lambda x: x and "/jobs/p/" in x)

        for a_tag in links:
            try:
                title = a_tag.get_text(strip=True)
                link  = a_tag["href"]
                if not link.startswith("http"):
                    link = "https://wuzzuf.net" + link

                if not title or not is_relevant_title(title):
                    continue

                card = a_tag
                for _ in range(4):
                    if card.parent:
                        card = card.parent
                    else:
                        break

                company_tag = card.find("a", href=lambda x: x and "/c/" in x)
                company = company_tag.get_text(strip=True) if company_tag else "N/A"

                date_tag = card.find(string=lambda s: s and any(
                    w in s.lower() for w in ["ago", "today", "yesterday", "hour", "day", "minute", "week"]
                ))
                posted = date_tag.strip() if date_tag else "Recently"

                jobs.append(make_job("Wuzzuf", title, company, "Egypt", link, posted))

            except Exception:
                continue

    except Exception as e:
        print(f"    [Wuzzuf] error: {e}")

    return jobs


# ──────────────────────────────────────────────
#  BAYT
# ──────────────────────────────────────────────
def scrape_bayt(keyword):
    jobs = []
    query = keyword.replace(" ", "-").lower()
    url = f"https://www.bayt.com/en/egypt/jobs/{query}-jobs/"
    cookies = cookie_dict(BAYT_COOKIE)

    try:
        resp = requests.get(url, headers=HEADERS, cookies=cookies, timeout=15)
        if resp.status_code != 200:
            print(f"    [Bayt] status {resp.status_code} — skipping")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all("h2")

        for card in cards:
            try:
                a_tag = card.find("a")
                if not a_tag:
                    continue

                title = a_tag.get_text(strip=True)
                link  = a_tag.get("href", "")
                if not link.startswith("http"):
                    link = "https://www.bayt.com" + link

                if not title or not is_relevant_title(title):
                    continue

                jobs.append(make_job("Bayt", title, "N/A", "Egypt", link, "Recently"))

            except Exception:
                continue

    except Exception as e:
        print(f"    [Bayt] error: {e}")

    return jobs


# ──────────────────────────────────────────────
#  INDEED
# ──────────────────────────────────────────────
def scrape_indeed(keyword):
    jobs = []
    url = "https://eg.indeed.com/jobs"
    params = {"q": keyword, "l": "Egypt"}
    cookies = cookie_dict(INDEED_COOKIE)

    try:
        resp = requests.get(url, headers=HEADERS, params=params, cookies=cookies, timeout=15)
        if resp.status_code != 200:
            print(f"    [Indeed] status {resp.status_code} (often blocked without INDEED_COOKIE secret)")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all("a", class_=lambda c: c and "jcs-JobTitle" in c)

        for card in cards:
            try:
                title = card.get_text(strip=True)
                link  = "https://eg.indeed.com" + card.get("href", "")

                if not title or not is_relevant_title(title):
                    continue

                jobs.append(make_job("Indeed", title, "N/A", "Egypt", link, "Recently"))

            except Exception:
                continue

    except Exception as e:
        print(f"    [Indeed] error: {e}")

    return jobs


# ──────────────────────────────────────────────
#  BUILD EMAIL
# ──────────────────────────────────────────────
SOURCE_BADGES = {
    "LinkedIn": ("#0a66c2", "LinkedIn"),
    "Wuzzuf":   ("#ee3060", "Wuzzuf"),
    "Bayt":     ("#f6921e", "Bayt"),
    "Indeed":   ("#2557a7", "Indeed"),
}


def format_posted(job: dict, is_new: bool) -> str:
    """
    For NEW jobs     → show the original scraped 'posted' string (e.g. '5 minutes ago').
    For EARLIER jobs → compute real elapsed time from found_at so it stays accurate
                       across subsequent email runs instead of freezing at scrape time.
    """
    if is_new:
        return job.get("posted", "Recently")

    found_at_str = job.get("found_at")
    if not found_at_str:
        return job.get("posted", "Recently")

    try:
        found_at = datetime.fromisoformat(found_at_str)
        now = datetime.now(timezone.utc)
        delta = now - found_at
        total_minutes = int(delta.total_seconds() // 60)

        if total_minutes < 1:
            return "Just found"
        elif total_minutes < 60:
            return f"Found {total_minutes}m ago"
        else:
            hours = total_minutes // 60
            mins  = total_minutes % 60
            if mins == 0:
                return f"Found {hours}h ago"
            return f"Found {hours}h {mins}m ago"
    except Exception:
        return job.get("posted", "Recently")


def build_job_row(j: dict, is_new: bool = True) -> str:
    color, label = SOURCE_BADGES.get(j["source"], ("#6b7280", j["source"]))
    badge = (
        f'<span style="background:{color};color:#fff;font-size:10px;font-weight:700;'
        f'padding:2px 8px;border-radius:10px;margin-right:6px;">{label}</span>'
    )
    easy_apply_badge = ""
    if j.get("easy_apply"):
        easy_apply_badge = (
            '<span style="background:#057642;color:#fff;font-size:10px;font-weight:700;'
            'padding:2px 8px;border-radius:10px;margin-left:6px;">Easy Apply</span>'
        )

    posted_display = format_posted(j, is_new)

    return f"""
    <tr>
      <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;">
        {badge}{easy_apply_badge}<br>
        <a href="{j['link']}" style="font-weight:600;color:#0a66c2;text-decoration:none;font-size:15px;">{j['title']}</a><br>
        <span style="color:#374151;font-size:13px;">{j['company']}</span>
      </td>
      <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;color:#6b7280;font-size:13px;">{j['location']}</td>
      <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;color:#6b7280;font-size:13px;">{posted_display}</td>
      <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;">
        <a href="{j['link']}" style="background:#0a66c2;color:#fff;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:12px;font-weight:600;">Apply</a>
      </td>
    </tr>
    """


def build_table(jobs: list, is_new: bool = True) -> str:
    rows = "".join(build_job_row(j, is_new) for j in jobs)
    # Column header differs slightly to make context clear
    time_col_header = "POSTED" if is_new else "FOUND"
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
      <thead>
        <tr style="background:#f9fafb;">
          <th style="padding:10px 16px;text-align:left;font-size:12px;color:#6b7280;font-weight:600;border-bottom:2px solid #e5e7eb;">POSITION / SOURCE</th>
          <th style="padding:10px 16px;text-align:left;font-size:12px;color:#6b7280;font-weight:600;border-bottom:2px solid #e5e7eb;">LOCATION</th>
          <th style="padding:10px 16px;text-align:left;font-size:12px;color:#6b7280;font-weight:600;border-bottom:2px solid #e5e7eb;">{time_col_header}</th>
          <th style="padding:10px 16px;text-align:left;font-size:12px;color:#6b7280;font-weight:600;border-bottom:2px solid #e5e7eb;"></th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
    """


REGION_ORDER = [
    "Egypt",
    "Remote - United States",
    "Remote - Saudi Arabia",
    "Remote - United Arab Emirates",
    "Remote - Kuwait",
    "Remote - Qatar",
]

def ordered_regions(jobs: list) -> list:
    present = set(j.get("region", "Egypt") for j in jobs)
    ordered = [r for r in REGION_ORDER if r in present]
    extra   = sorted(r for r in present if r not in REGION_ORDER)
    return ordered + extra


def build_region_blocks(jobs: list, heading_color: str, is_new: bool = True) -> str:
    blocks = ""
    for region in ordered_regions(jobs):
        region_jobs = [j for j in jobs if j.get("region", "Egypt") == region]
        if not region_jobs:
            continue
        label = "🇪🇬 Egypt" if region == "Egypt" else f"🌍 {region.replace('Remote - ', '')} (Remote)"
        blocks += f"""
        <div style="padding:14px 32px 4px;">
          <h3 style="margin:0;font-size:14px;color:{heading_color};">{label} — {len(region_jobs)}</h3>
        </div>
        {build_table(region_jobs, is_new)}
        """
    return blocks


def build_email_html(new_jobs: list, earlier_jobs: list) -> str:
    now   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(new_jobs) + len(earlier_jobs)

    sections = ""
    if new_jobs:
        sections += f"""
        <div style="padding:18px 32px 4px;">
          <h2 style="margin:0;font-size:16px;color:#059669;">🆕 New since last check ({len(new_jobs)})</h2>
        </div>
        {build_region_blocks(new_jobs, "#059669", is_new=True)}
        """
    if earlier_jobs:
        sections += f"""
        <div style="padding:18px 32px 4px;">
          <h2 style="margin:0;font-size:16px;color:#6b7280;">📋 Earlier today ({len(earlier_jobs)})</h2>
        </div>
        {build_region_blocks(earlier_jobs, "#6b7280", is_new=False)}
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif;">
      <div style="max-width:760px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <div style="background:#0a66c2;padding:28px 32px;">
          <h1 style="margin:0;color:#fff;font-size:22px;">📊 Multi-Source Job Alert</h1>
          <p style="margin:6px 0 0;color:#bfdbfe;font-size:13px;">{total} jobs total today · {now}</p>
        </div>
        {sections}
        <div style="padding:20px 32px;background:#f9fafb;border-top:1px solid #e5e7eb;">
          <p style="margin:0;font-size:12px;color:#9ca3af;">
            Sources: LinkedIn · Wuzzuf · Bayt · Indeed<br>
            Egypt jobs + Remote (US / KSA / UAE / Kuwait / Qatar) · Resets daily · GitHub Actions
          </p>
        </div>
      </div>
    </body>
    </html>
    """


# ──────────────────────────────────────────────
#  SEND EMAIL
# ──────────────────────────────────────────────
def send_email(new_jobs: list, earlier_jobs: list):
    if not new_jobs:
        print("No new jobs — skipping email.")
        return

    total   = len(new_jobs) + len(earlier_jobs)
    subject = f"📊 {len(new_jobs)} New Jobs (Multi-Source) — {total} Total Today"
    html    = build_email_html(new_jobs, earlier_jobs)

    for recipient in RECIPIENT_EMAILS:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SENDER_EMAIL
        msg["To"]      = recipient
        msg.attach(MIMEText(html, "html"))
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(SENDER_EMAIL, GMAIL_PASSWORD)
                server.sendmail(SENDER_EMAIL, recipient, msg.as_string())
            print(f"✅ Email sent to {recipient} — {len(new_jobs)} new, {total} total.")
        except Exception as e:
            print(f"❌ Email failed for {recipient}: {e}")


# ──────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────
def main():
    print(f"🚀 Scraper started at {datetime.now(timezone.utc).isoformat()}")
    today, day_jobs = load_seen_jobs()
    print(f"   Already found today: {len(day_jobs)} jobs")

    seen_ids     = set(j["id"] for j in day_jobs)
    all_new_jobs = []

    # ── Egypt jobs across all sources ──
    for keyword in KEYWORDS_EGYPT:
        print(f"\n   Searching (Egypt): {keyword}")

        for name, func in [
            ("LinkedIn", lambda kw: scrape_linkedin(kw, "Egypt")),
            ("Wuzzuf",   scrape_wuzzuf),
            ("Bayt",     scrape_bayt),
            ("Indeed",   scrape_indeed),
        ]:
            try:
                results = func(keyword)
                fresh   = [j for j in results if j["id"] not in seen_ids]
                print(f"     {name}: {len(results)} found, {len(fresh)} new")
                all_new_jobs.extend(fresh)
                for j in fresh:
                    seen_ids.add(j["id"])
            except Exception as e:
                print(f"     {name} failed: {e}")
            time.sleep(random.uniform(1, 3))

    # ── Remote US / KSA / UAE / Kuwait / Qatar jobs via LinkedIn ──
    for search in REMOTE_SEARCHES:
        kw  = search["keyword"]
        loc = search["location"]
        print(f"\n   Searching (Remote/{loc}): {kw}")
        try:
            results = scrape_linkedin(kw, loc)
            fresh   = [j for j in results if j["id"] not in seen_ids]
            print(f"     LinkedIn: {len(results)} found, {len(fresh)} new")
            all_new_jobs.extend(fresh)
            for j in fresh:
                seen_ids.add(j["id"])
        except Exception as e:
            print(f"     LinkedIn (remote) failed: {e}")
        time.sleep(random.uniform(1, 3))

    print(f"\n📊 New jobs this run: {len(all_new_jobs)}")

    earlier_jobs     = sorted(day_jobs, key=lambda j: j["found_at"], reverse=True)
    updated_day_jobs = all_new_jobs + day_jobs
    save_seen_jobs(today, updated_day_jobs)
    print(f"💾 seen_jobs.json updated — {len(updated_day_jobs)} total jobs today")

    new_jobs_sorted = sorted(all_new_jobs, key=lambda j: j["found_at"], reverse=True)
    send_email(new_jobs_sorted, earlier_jobs)


if __name__ == "__main__":
    main()
