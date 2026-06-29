# 📰 Tech Newsletter — Complete Guide

An automated daily tech newsletter system that fetches news from RSS feeds and websites, scores it with an LLM, generates visual article cards, and emails a formatted digest to your employee list — twice a day, fully on autopilot.

---

## 📁 Project Structure

```
TECH_NEWSLETTER/
│
├── config/
│   ├── __init__.py
│   └── settings.py              ← ✏️  MASTER CONFIG — edit schedules, limits, sources here
│
├── data/
│   └── newsletter.db            ← SQLite database (employees + sent article history)
│
├── fetchers/
│   ├── __init__.py
│   ├── rss_fetcher.py           ← Parses all RSS feeds
│   ├── scraper.py               ← Scrapes web targets (Pune Mirror, STPI, etc.)
│   └── content_enricher.py     ← Fetches full article body text
│
├── filters/
│   ├── __init__.py
│   └── preflight.py             ← 3-stage pre-LLM filter (structural → dedup → quality score)
│
├── llm/
│   ├── __init__.py
│   └── scorer.py                ← Groq LLM relevance scoring + category assignment
│
├── newsletter/
│   ├── __init__.py
│   ├── builder.py               ← Assembles final HTML + plain-text email body
│   └── sender.py                ← SMTP email dispatch with embedded images
│
├── utils/
│   ├── __init__.py
│   └── database.py              ← All SQLite helpers (employees, sent articles, run log)
│
├── generated_cards/             ← Auto-generated PNG cards (cleared each run)
│   ├── <hash>.png               ← Article cards (826×241 px)
│   ├── badge_AI.png             ← Category section badges (1160×100 px)
│   ├── badge_STARTUPS.png
│   └── date_header.png          ← Date banner (1160×70 px)
│
├── logs/
│   └── pipeline.log             ← Full run log
│
├── card_generator.py            ← Generates all PNG images (cards, badges, date header)
├── manage_employees.py          ← CLI tool to manage newsletter recipients
├── pipeline.py                  ← Main orchestrator — runs the full pipeline
├── scheduler.py                 ← Runs pipeline on a schedule (8 AM + 6 PM by default)
├── setup_autostart.py           ← 🖥️  One-time script to register Windows auto-start task
├── requirements.txt
├── .env                         ← 🔑 Your API keys and SMTP credentials (never commit this)
└── image.png                    ← 🖼️  Static header banner shown at top of every email
```

---

## ⚡ Quick Start

### 1. Clone and install dependencies

```bash
git clone <your-repo-url>
cd TECH_NEWSLETTER
pip install -r requirements.txt
```

### 2. Create your `.env` file

Create a file named `.env` in the project root (same folder as `pipeline.py`):

```env
# Groq API Keys — get free keys at https://console.groq.com/keys
# Three keys are used in rotation to avoid rate limits
GROQ_API_KEY_1=gsk_xxxxxxxxxxxxxxxxxxxx
GROQ_API_KEY_2=gsk_xxxxxxxxxxxxxxxxxxxx
GROQ_API_KEY_3=gsk_xxxxxxxxxxxxxxxxxxxx

# SMTP Settings (example below uses Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your_app_password_here
SMTP_FROM_EMAIL=your@gmail.com
```

> **Gmail tip:** Use an [App Password](https://myaccount.google.com/apppasswords), not your regular Gmail password. Enable 2FA first, then generate an app-specific password.

### 3. Add at least one recipient

```bash
python manage_employees.py add --id EMP001 --name "Your Name" --email your@email.com --dept "IT"
```

### 4. Run a test (no email sent)

```bash
python pipeline.py --no-send
```

### 5. Run for real

```bash
python pipeline.py
```

### 6. Register auto-start on boot (one-time, any new PC)

```bash
python setup_autostart.py
```

> Run as Administrator for system-wide auto-start (works even when no one is logged in). After this, the scheduler starts automatically 30 seconds after every reboot — no manual action needed.

### 7. Start the scheduler manually (if not using auto-start)

```bash
python scheduler.py
```

---

## 🔧 Configuration — `config/settings.py`

This is the **one file** you edit to change how the newsletter behaves.

### ⏰ Delivery Schedule

```python
SCHEDULE_TIMES = ["08:00", "18:00"]   # 24-hour IST — change delivery times here
TIMEZONE       = "Asia/Kolkata"        # Your timezone
```

To send at 9 AM and 5 PM instead:
```python
SCHEDULE_TIMES = ["09:00", "17:00"]
```

### 📧 Email Subject

The subject is auto-generated in `newsletter/sender.py`:

```python
subject = f"Daily tech news ({date_str})"
```

To change it, open `newsletter/sender.py` and edit that line. Example:

```python
subject = f"🔔 Tech Intelligence Digest — {date_str}"
```

### 📰 Newsletter Limits

```python
MAX_ARTICLES_IN_EMAIL        = 15    # Max article cards shown per email
MAX_ARTICLES_TO_LLM          = 20    # Articles passed to Groq for scoring
NEWS_LOOKBACK_HOURS          = 24    # Only fetch news from last N hours
CONTENT_SIMILARITY_THRESHOLD = 0.72  # Duplicate detection sensitivity (0–1)
```

### 🌍 Geographic Prioritization

Geographic scope (`LOCAL / STATE / NATIONAL / GLOBAL`) is now **detected from the article content** by the LLM — not from the source name. A TechCrunch article about a Pune startup gets `LOCAL`. A Samsung press release gets `GLOBAL`. You do not need to maintain any source map.

You can tune the scoring weights in `config/settings.py`:

```python
GEO_WEIGHT = {
    "LOCAL":    1.4,   # City-level news     (highest priority)
    "STATE":    1.3,   # State-level news
    "NATIONAL": 1.2,   # India-wide news
    "GLOBAL":   1.0,   # International       (baseline)
}
```

Set all to `1.0` for zero geographic bias. This is a scoring nudge only — all geo levels still appear in the newsletter.

---

## 🖼️ Customizing the Header Image

The **static banner** shown at the very top of every email is the file:

```
image.png        ← root of the project
```

**To change it:** Simply replace `image.png` with your own image. Keep the filename exactly `image.png`. Recommended size is **1160px wide** (height is flexible). The email scales it responsively for mobile.

---

## 🃏 How Article Cards Work

Each article gets a **826×241 px PNG card** automatically generated by `card_generator.py`.

### Card layout

```
┌──────────────────────────────────────────────────────────────┐
│  [241×241 Thumbnail] │  SOURCE NAME                          │
│                      │  Article Title (bold, up to 2 lines) │
│                      │  Summary text (up to 3 lines)        │
│                      │                        [Read more →] │
└──────────────────────────────────────────────────────────────┘
```

- **Thumbnail:** Downloaded from the article's `og:image`. If unavailable, a dark-blue fallback tile with the source name is used.
- **Summary:** Written by the Groq LLM — always exactly 2 crisp, factual sentences.
- **Read more button:** Links directly to the article URL when clicked in email.

### Category Badges

Above each group of articles, a **1160×100 px category badge** is inserted — e.g., `🤖 ARTIFICIAL INTELLIGENCE`. These are auto-generated from the categories in `SECTIONS` inside `settings.py`.

### Date Header

A **1160×70 px date banner** (e.g., `25 JUN 2026`) is generated fresh each run and placed right below your static `image.png` header.

### Colors & fonts

To change card colors or fonts, edit the color constants at the top of `card_generator.py`:

```python
C_BG         = (255, 255, 255)   # Card background
C_TITLE      = (15,  23,  42)    # Title text color
C_SUMMARY    = (71,  85, 105)    # Summary text color
C_BTN_L      = (255, 81,  47)    # Button gradient left color
C_BTN_R      = (221, 36, 118)    # Button gradient right color
C_THUMB_BG   = (27,  58, 107)    # Fallback thumbnail background
```

---

## 👥 Managing Employee Recipients

All recipient management is done through the CLI — **no database browser needed**.

### See all employees

```bash
python manage_employees.py list
```

### Filter by status

```bash
python manage_employees.py list --status active
python manage_employees.py list --status inactive
```

### Add a new employee

```bash
python manage_employees.py add --id EMP001 --name "Rahul Sharma" --email rahul@company.com --dept "IT"
python manage_employees.py add --id EMP002 --name "Priya Iyer"   --email priya@company.com --dept "Operations"
```

- `--id` must be unique (e.g., EMP001, EMP002)
- `--dept` is optional
- New employees are **active** by default and will receive the next email

### Deactivate an employee (stop emails, keep record)

```bash
python manage_employees.py deactivate --id EMP001
```

### Reactivate an employee

```bash
python manage_employees.py activate --id EMP001
```

### Update someone's email address

```bash
python manage_employees.py update-email --id EMP001 --email newemail@company.com
```

### Permanently delete an employee

```bash
python manage_employees.py delete --id EMP001
```

> You will be asked to type `YES` to confirm. Prefer `deactivate` over `delete` — it keeps the record but stops emails.

### Show all active email addresses

```bash
python manage_employees.py show-emails
```

---

## 📡 Adding / Removing News Sources

### RSS Feeds

Edit the `RSS_FEEDS` list in `config/settings.py`:

```python
RSS_FEEDS = [
    {"url": "https://techcrunch.com/feed/", "source": "TechCrunch", "tier": 2},
    # Add more feeds here
]
```

- `tier: 1` = Primary sources (company blogs, major outlets)
- `tier: 2` = Secondary sources (industry publications)
- `tier: 3` = Local/niche sources

### Web Scrape Targets

Edit the `SCRAPE_TARGETS` list:

```python
SCRAPE_TARGETS = [
    {"url": "https://example.com/news", "source": "Example News", "tier": 2, "type": "generic"},
]
```

Use `"type": "stpi"` only for STPI-style government sites; use `"generic"` for everything else.

### Adding a new category label / badge

Edit the `SECTIONS` dict in `settings.py`:

```python
SECTIONS = {
    "AI":         {"emoji": "🤖", "label": "Artificial Intelligence"},
    "MYNEWCAT":   {"emoji": "⚡", "label": "My New Category"},
    # ...
}
```

The LLM will automatically assign articles to this category if it fits.

---

## 🚀 Running the Pipeline

### Full run (fetches, scores, and sends email)

```bash
python pipeline.py
```

### Dry run — check how many articles are fetched without any LLM or email

```bash
python pipeline.py --dry-run
```

### No-send — full pipeline including card generation, but skip email dispatch

```bash
python pipeline.py --no-send
```

### Debug mode — verbose logging

```bash
python pipeline.py --debug
```

### Start the scheduler (runs automatically at configured times)

```bash
python scheduler.py
```

### Run immediately and then keep scheduler running

```bash
python scheduler.py --run-now
```

---

## 🔄 Pipeline Flow (what happens when you run it)

```
1. init_db()              — Initialize/verify SQLite database
2. purge_old_articles()   — Delete sent article records older than 15 days
3. get_active_recipients()— Load active employee emails from DB
4. fetch_all_rss()        — Parse all RSS feeds (concurrent, up to 10 workers)
5. fetch_all_scraped()    — Scrape all web targets (concurrent, up to 6 workers)
6. enrich_articles()      — Fetch full article body text (concurrent, 8 workers)
7. run_preflight_pipeline()
   ├── Stage 1: Structural filter   — Reject junk URLs, thin content, already-sent
   ├── Stage 2: Semantic dedup      — TF-IDF cosine similarity, keep richest version
   └── Stage 3: Quality scoring     — Score by content length, entities, geo weight
8. score_all_articles()   — Groq LLM scores each article KEEP/REJECT + assigns category
9. clear_old_cards()      — Delete last run's PNG files
10. generate_all_cards()  — Create 826×241 PNG card for each article
11. generate_email_assets()— Create date header + category badge PNGs
12. build_email_html()    — Assemble responsive HTML email body
13. build_plain_text()    — Assemble plain-text fallback
14. send_newsletter()     — SMTP send with all images embedded as CID attachments
15. mark_articles_sent()  — Store sent URLs in DB to prevent re-sending
16. log_run()             — Write run stats to run_log table
```

---

## 🤖 LLM Scoring (Groq)

Articles are scored by `llama-3.3-70b-versatile` via Groq's API. The LLM evaluates each article on 6 criteria and returns:

- `verdict`: `KEEP` or `REJECT`
- `yes_count`: Number of criteria passed (0–6)
- `summary`: 2-sentence factual summary (used on the card)
- `category`: One of 14 categories (AI, STARTUPS, CLOUD, etc.)

Articles are sorted by `yes_count` descending, and only the top `MAX_ARTICLES_IN_EMAIL` are kept.

**Three Groq API keys** are used in rotation — if key 1 hits the rate limit, key 2 takes over automatically, then key 3.

---

## 🗄️ Database Tables

The SQLite database at `data/newsletter.db` has three tables:

| Table | Purpose |
|---|---|
| `employees` | Recipient list with status (active/inactive) |
| `sent_articles` | History of every URL ever sent (prevents duplicates) |
| `run_log` | Log of every pipeline execution with stats |

Sent article records older than **15 days** are automatically purged each run to keep the database small.

---

## 🖥️ Auto-Start on PC Boot — `setup_autostart.py`

The `setup_autostart.py` script registers the newsletter scheduler as a **Windows Task Scheduler task** so it starts automatically every time the PC boots — no manual intervention needed on any new machine.

### Install (run once per PC)

Right-click your terminal → **Run as Administrator**, then:

```bash
python setup_autostart.py
```

That's it. The script auto-detects your Python path and project folder — nothing is hardcoded, so it works on any machine.

### What it sets up

- Triggers **30 seconds after every system boot** (delay lets the network come up first)
- **Restarts automatically** up to 3 times if the scheduler crashes
- Runs with highest available privileges
- Works even when no user is logged in (when run as Administrator)

### Check if the task is registered

```bash
python setup_autostart.py --status
```

### Remove the task

```bash
python setup_autostart.py --remove
```

### Without Administrator rights

The task still installs but only runs when **your user account** is logged in. For a headless server or shared PC, always run as Administrator.

### Verify in Windows Task Scheduler

Open **Task Scheduler** → look for `TechNewsletterScheduler` in the task list. You can manually trigger, disable, or inspect it from there if needed.

---

| Problem | Fix |
|---|---|
| No email received | Check SMTP credentials in `.env`. Run `python pipeline.py --debug` and check logs. |
| `No active recipients` | Add employees with `manage_employees.py add` |
| All articles rejected by LLM | Your Groq keys may be rate-limited or invalid. Check `logs/pipeline.log`. |
| Cards not generating | Ensure `Pillow` is installed: `pip install Pillow` |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| Font looks wrong | The card generator auto-detects system fonts. Install Liberation Sans on Linux or ensure Arial/Calibri is present on Windows. |
| Gmail auth fails | Use an [App Password](https://myaccount.google.com/apppasswords), not your Gmail password |
| Auto-start task not running | Re-run `python setup_autostart.py` as Administrator. Check Task Scheduler for `TechNewsletterScheduler`. |
| Task registered but emails not sent | Check `logs/pipeline.log` — the scheduler may be starting but hitting an API or SMTP error. |

---

## 📋 Requirements Summary

- Python 3.11+
- Internet access (for fetching feeds and Groq API)
- A Groq account (free tier works — get keys at [console.groq.com](https://console.groq.com/keys))
- A Gmail account (or any SMTP provider) for sending

---

## 📄 License

Internal use. All rights reserved.