"""
=============================================================================
  TECH NEWSLETTER - MASTER SETTINGS
  ✏️  Edit this file to change schedules, recipients, limits, and sources.
=============================================================================
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# 🕐  SCHEDULE  (24-hour format, IST)
# ─────────────────────────────────────────────────────────────────────────────
SCHEDULE_TIMES = ["08:00",]   # ← Change newsletter delivery times here
TIMEZONE       = "Asia/Kolkata"        # ← Your local timezone

EMAIL_SENDER_NAME = "Tech News "


# ─────────────────────────────────────────────────────────────────────────────
# 🔑  API KEYS  (set in .env file — never hardcode here)
# ─────────────────────────────────────────────────────────────────────────────
GROQ_API_KEY_1 = os.getenv("GROQ_API_KEY_1", "")
GROQ_API_KEY_2 = os.getenv("GROQ_API_KEY_2", "")
GROQ_API_KEY_3 = os.getenv("GROQ_API_KEY_3", "")

SMTP_HOST       = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER       = os.getenv("SMTP_USER", "")
SMTP_PASSWORD   = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")

# ─────────────────────────────────────────────────────────────────────────────
# 📰  NEWSLETTER LIMITS
# ─────────────────────────────────────────────────────────────────────────────
MAX_ARTICLES_IN_EMAIL        = 7    # ← Max cards shown in the newsletter
MAX_ARTICLES_TO_LLM          = 35    # ← Articles sent to Groq for scoring
NEWS_LOOKBACK_HOURS          = 24    # ← Only fetch news from the last N hours
CONTENT_SIMILARITY_THRESHOLD = 0.72  # ← 0-1: higher = stricter duplicate detection

# ─────────────────────────────────────────────────────────────────────────────
# 🤖  LLM SETTINGS
# ─────────────────────────────────────────────────────────────────────────────
GROQ_MODEL  = "llama-3.3-70b-versatile"
LLM_TIMEOUT = 30   # seconds per request

# ─────────────────────────────────────────────────────────────────────────────
# 🌍  GEOGRAPHIC SCOPE WEIGHTS
# ─────────────────────────────────────────────────────────────────────────────
GEO_WEIGHT = {
    "LOCAL":    1.4,
    "STATE":    1.3,
    "NATIONAL": 1.2,
    "GLOBAL":   1.0,
}

# ─────────────────────────────────────────────────────────────────────────────
# 💾  DATABASE
# ─────────────────────────────────────────────────────────────────────────────
DB_PATH = "data/newsletter.db"

# ─────────────────────────────────────────────────────────────────────────────
# 📡  RSS FEEDS
# ─────────────────────────────────────────────────────────────────────────────
RSS_FEEDS = [
    # --- AI Labs ---
    {"url": "https://openai.com/news/rss.xml",                                 "source": "OpenAI",               "tier": 1},

    # --- Big Tech ---
    {"url": "https://www.apple.com/newsroom/rss-feed.rss",                     "source": "Apple",                "tier": 1},
    {"url": "https://blog.google/rss/",                                        "source": "Google Blog",          "tier": 1},
    {"url": "https://blogs.nvidia.com/feed/",                                  "source": "NVIDIA",               "tier": 1},
    {"url": "https://newsroom.intel.com/feed/",                                "source": "Intel",                "tier": 1},
    {"url": "https://news.samsung.com/global/feed",                            "source": "Samsung",              "tier": 1},

    # --- Cloud ---
    {"url": "https://aws.amazon.com/blogs/aws/feed/",                          "source": "AWS Blog",             "tier": 1},
    {"url": "https://cloud.google.com/blog/rss",                               "source": "GCP Blog",             "tier": 1},
    {"url": "https://www.redhat.com/en/rss/blog",                              "source": "Red Hat",              "tier": 2},

    # --- Data Centers ---
    {"url": "https://www.datacenterdynamics.com/rss/",                         "source": "DC Dynamics",          "tier": 2},
    {"url": "https://www.datacenterknowledge.com/rss.xml",                     "source": "DC Knowledge",         "tier": 2},

    # --- Cybersecurity ---
    {"url": "https://thehackernews.com/feeds/posts/default",                   "source": "Hacker News",          "tier": 2},
    {"url": "https://www.bleepingcomputer.com/feed/",                          "source": "BleepingComputer",     "tier": 2},
    {"url": "https://www.securityweek.com/feed/",                              "source": "SecurityWeek",         "tier": 2},
    {"url": "https://www.darkreading.com/rss.xml",                             "source": "Dark Reading",         "tier": 2},
    {"url": "https://www.helpnetsecurity.com/feed/",                           "source": "HelpNetSecurity",      "tier": 2},

    # --- Tech News ---
    {"url": "https://techcrunch.com/category/artificial-intelligence/feed/",   "source": "TechCrunch AI",        "tier": 2},
    {"url": "https://techcrunch.com/category/robotics/feed/",                  "source": "TechCrunch Robotics",  "tier": 2},
    {"url": "https://techcrunch.com/category/startups/feed/",                  "source": "TechCrunch Startups",  "tier": 2},
    {"url": "https://techcrunch.com/tag/microsoft/feed/",                      "source": "TechCrunch Microsoft", "tier": 2},
    {"url": "https://techcrunch.com/tag/meta/feed/",                           "source": "TechCrunch Meta",      "tier": 2},
    {"url": "https://techcrunch.com/tag/asia/feed/",                           "source": "TechCrunch Asia",      "tier": 2},

    # --- Indian Tech ---
    {"url": "https://economictimes.indiatimes.com/tech/rssfeeds/13357270.cms", "source": "ET Tech",              "tier": 2},
    {"url": "https://manufacturing.economictimes.indiatimes.com/rss",          "source": "ET Manufacturing",     "tier": 2},
    {"url": "https://www.thehindu.com/sci-tech/technology/feeder/default.rss", "source": "The Hindu Tech",       "tier": 2},
    {"url": "https://indianexpress.com/section/cities/pune/feed/",             "source": "Indian Express Pune",  "tier": 3},
]

# ─────────────────────────────────────────────────────────────────────────────
# 🌐  WEB SCRAPE TARGETS
# ─────────────────────────────────────────────────────────────────────────────
SCRAPE_TARGETS = [
    # --- STPI (Software Technology Parks of India) ---
    {"url": "https://stpi.in/en/main-news",                        "source": "STPI",             "tier": 2, "type": "stpi"},

    # --- Pune Tech News (technology section only) ---
    {"url": "https://punemirror.com/technology/",                  "source": "Pune Mirror Tech", "tier": 3, "type": "generic"},
    {"url": "https://www.punekarnews.in/category/business/",       "source": "Punekar News",     "tier": 3, "type": "generic"},

    # --- Manufacturing & Industry 4.0 ---
    {"url": "https://www.industryweek.com/technology-and-iiot",    "source": "IndustryWeek",     "tier": 2, "type": "generic"},
    {"url": "https://www.automation.com",                          "source": "Automation.com",   "tier": 2, "type": "generic"},
]

# ─────────────────────────────────────────────────────────────────────────────
# 🏷️  NEWSLETTER SECTIONS
# ─────────────────────────────────────────────────────────────────────────────
SECTIONS = {
    "AI":             {"label": "Artificial Intelligence"},
    "MANUFACTURING":  {"label": "Industry 4.0 & Smart Manufacturing"},
    "IIOT":           {"label": "Industrial IoT"},
    "CLOUD":          {"label": "Cloud & Enterprise Infrastructure"},
    "CYBERSECURITY":  {"label": "Cybersecurity"},
    "DATACENTERS":    {"label": "Data Centers & Compute"},
    "SEMICONDUCTOR":  {"label": "Semiconductor & Hardware"},
    "STARTUPS":       {"label": "Startups, Funding & M&A"},
    "BIGTECH":        {"label": "Big Tech & Enterprise"},
    "DIGITAL":        {"label": "Digital Transformation"},
    "CONNECTIVITY":   {"label": "Connectivity & Networking"},
    "SUSTAINABILITY": {"label": "Sustainability & Green Tech"},
    "SUPPLYCHAIN":    {"label": "Supply Chain & Logistics"},
    "EMERGING":       {"label": "Emerging Technologies"},
}