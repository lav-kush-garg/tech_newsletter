"""
Pre-LLM Filter Pipeline
========================
Three stages before any LLM call:

Stage 1 — Structural filter
    Rejects junk by URL path, title signals, thin content, already-sent URLs.
    Tuned for an IT/tech professional audience.

Stage 2 — Semantic deduplication (TF-IDF cosine similarity on full body text)
    Same story from multiple sources → keep the one with richest content.

Stage 3 — Content quality scoring + geographic weight
    Geographic weight gives a mild boost to local news but does NOT override
    quality — a low-quality local article still scores below a high-quality
    global one.
"""

import re
import logging
from datetime import datetime, timezone
from math import log
from urllib.parse import urlparse

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config.settings import (
    MAX_ARTICLES_TO_LLM,
    CONTENT_SIMILARITY_THRESHOLD,
    GEO_WEIGHT,
)
from utils.database import is_already_sent

logger = logging.getLogger(__name__)

# ─── Regex patterns ───────────────────────────────────────────────────────────

_JUNK_URL_PATTERNS = re.compile(
    r'/(tag|author|category|about|contact|advertise|careers|events?|webinar|'
    r'award|podcast|video|gallery|subscribe|newsletter|search|sitemap)/',
    re.I
)

# Junk title signals — finance/deal/HR noise + non-IT consumer topics
_JUNK_TITLE_SIGNALS = re.compile(
    r'\b(sponsored|advertisement|advertorial|press release|op-ed|opinion:|'
    r'editorial:|interview:|q&a:|podcast:|webinar:|award[s]?:|hiring|'
    r'layoffs?|stock price|share price|market cap|quarterly earnings?|'
    r'annual report|analyst prediction[s]?|rumou?r[s]?|reportedly|may launch|'
    r'could announce|lifestyle|celebrity|ipo|valuation|merger|acquisition|'
    r'acqui-hire|fundrais|series [abcde]|seed round|venture capital|'
    r'appoints?|names? (new|its)|joins? as (ceo|cto|coo|cfo|vp|head)|'
    r'promoted to|executive team|board of directors|revenue grew|'
    r'profit rose|net income|quarterly result|jewellery|jewelry|luxury brand|'
    r'fashion|automobile launch|car launch|new model|test drive|'
    r'plastic[s]? manufactur|hot runner|mould|injection mold)\b',
    re.I
)

# Hard block: listicle directory articles — "32 Companies in Pune to Know",
# "11 Cloud Companies in Pune", "23 IT Companies in Pune to Know"
_LISTICLE_TITLE_PATTERN = re.compile(
    r'^\d+\s+(companies|startups|firms|tools|apps|platforms|ways|tips|things|'
    r'reasons|examples|best|top|must.know).{0,60}(to know|in \w+|you should)',
    re.I
)

_NUMBERS_RE    = re.compile(
    r'\b\d+[\.,]?\d*\s*(%|bn|mn|million|billion|crore|lakh|GB|TB|GHz|nm|ms|fps|kwh|mw|gw)?\b'
)
_PROPERNOUN_RE = re.compile(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)+\b')

# IT-relevance signals — used only for scoring boost, not hard gating
_IT_TOPIC_SIGNALS = re.compile(
    r'\b(ai|ml|machine.learning|deep.learning|llm|generative|cloud|kubernetes|'
    r'docker|devops|devsecops|api|microservice|cybersecurity|ransomware|'
    r'vulnerability|zero.day|patch|cve|breach|malware|phishing|encryption|'
    r'firewall|siem|soc|iot|iiot|plc|scada|edge.computing|5g|semiconductor|'
    r'chip|gpu|cpu|fpga|data.center|automation|robotics|digital.twin|'
    r'erp|sap|azure|aws|gcp|terraform|ansible|python|open.?source|'
    r'platform.engineering|observability|industry.4|smart.factory|'
    r'smart.manufacturing|supply.chain.tech|software|developer|coding|'
    r'infrastructure|network.security|endpoint|xdr|soar)\b',
    re.I
)


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 1 — Structural filter
# ═══════════════════════════════════════════════════════════════════════════════

def _structural_filter(articles: list[dict]) -> list[dict]:
    kept     = []
    rejected = 0

    for art in articles:
        title   = art.get("title", "")
        url     = art.get("url", "")
        content = (art.get("content", "") or "") + " " + (art.get("summary", "") or "")

        if is_already_sent(url):
            rejected += 1
            continue

        if not title or len(title) < 15:
            rejected += 1
            continue

        if _JUNK_URL_PATTERNS.search(url):
            rejected += 1
            continue

        # Hard block: listicle directory articles
        if _LISTICLE_TITLE_PATTERN.search(title.strip()):
            logger.debug(f"[Filter] Listicle blocked: {title[:60]}")
            rejected += 1
            continue

        if _JUNK_TITLE_SIGNALS.search(title):
            rejected += 1
            continue

        if len(content.strip()) < 150:
            rejected += 1
            continue

        kept.append(art)

    logger.info(f"[Filter/Stage1] Kept {len(kept)} / rejected {rejected} articles")
    return kept


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 2 — Semantic deduplication
# ═══════════════════════════════════════════════════════════════════════════════

def _build_text_repr(art: dict) -> str:
    title      = art.get("title", "") or ""
    content    = art.get("content", "") or ""
    summary    = art.get("summary", "") or ""
    body       = (content or summary)[:1500]
    clean_body = re.sub(r'(click here|read more|subscribe|share this|advertisement|copyright)', '', body, flags=re.I)
    return f"{title} {title} {title} {title} {clean_body}"


def _content_richness(art: dict) -> float:
    content  = (art.get("content", "") or art.get("summary", "")).strip()
    clen     = len(content)
    numbers  = len(_NUMBERS_RE.findall(content))
    capwords = len(_PROPERNOUN_RE.findall(content))
    words    = max(1, len(content.split()))

    length_score = min(1.0, log(max(1, clen)) / log(3000))
    entity_score = min(1.0, (numbers * 2 + capwords) / max(1, words * 0.15))
    return length_score + entity_score


def _semantic_dedup(articles: list[dict]) -> list[dict]:
    if len(articles) <= 1:
        return articles

    texts = [_build_text_repr(a) for a in articles]

    try:
        vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 3),
            sublinear_tf=True,
            stop_words="english",
        )
        tfidf_matrix = vectorizer.fit_transform(texts)
        sim_matrix   = cosine_similarity(tfidf_matrix)
    except Exception as e:
        logger.error(f"[Dedup] TF-IDF failed: {e} — skipping dedup")
        return articles

    n    = len(articles)
    keep = [True] * n

    for i in range(n):
        if not keep[i]:
            continue
        for j in range(i + 1, n):
            if not keep[j]:
                continue
            effective_threshold = CONTENT_SIMILARITY_THRESHOLD - 0.05
            if sim_matrix[i, j] >= effective_threshold:
                if _content_richness(articles[j]) > _content_richness(articles[i]):
                    keep[i] = False
                    break
                else:
                    keep[j] = False

    deduped       = [articles[i] for i in range(n) if keep[i]]
    dupes_removed = n - len(deduped)
    logger.info(f"[Filter/Dedup] Removed {dupes_removed} duplicates → {len(deduped)} unique")
    return deduped


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 3 — Content quality scoring
# ═══════════════════════════════════════════════════════════════════════════════

def _geo_weight(art: dict) -> float:
    """
    Mild geographic tiebreaker — local news gets a small nudge, not a
    free pass. Quality content always ranks higher regardless of location.
    """
    if art.get("geo_scope"):
        geo_lvl = art["geo_scope"]
    else:
        text = " ".join([
            art.get("title", ""),
            art.get("content", "")[:800],
            art.get("summary", ""),
        ]).lower()

        local_signals = [
            "pune", "pcmc", "pimpri", "chinchwad", "hinjewadi", "wakad",
            "baner", "kothrud", "hadapsar", "viman nagar", "kharadi",
            "magarpatta", "balewadi", "mumbai", "delhi", "bengaluru",
            "bangalore", "hyderabad", "chennai", "kolkata", "ahmedabad",
        ]
        state_signals = [
            "maharashtra", "karnataka", "tamil nadu", "telangana",
            "gujarat", "rajasthan", "kerala", "andhra pradesh",
            "uttar pradesh", "west bengal", "madhya pradesh",
        ]
        national_signals = [
            "india", "indian", "indians", "rupee", "rbi", "sebi",
            "ministry of", "government of india", "startup india",
            "make in india", "digital india", "niti aayog", "isro",
            "tata", "infosys", "wipro", "hcl", "reliance", "adani",
        ]

        if any(s in text for s in local_signals):
            geo_lvl = "LOCAL"
        elif any(s in text for s in state_signals):
            geo_lvl = "STATE"
        elif any(s in text for s in national_signals):
            geo_lvl = "NATIONAL"
        else:
            geo_lvl = "GLOBAL"

    # Conservative weights — geo is a tiebreaker, not a trump card
    weights = {"LOCAL": 1.2, "STATE": 1.1, "NATIONAL": 1.05, "GLOBAL": 1.0}
    return weights.get(geo_lvl, 1.0)


def _it_relevance_score(art: dict) -> float:
    """Boost articles containing genuine IT terminology."""
    text = (
        art.get("title", "") + " " +
        (art.get("content", "") or art.get("summary", ""))[:600]
    )
    matches = len(_IT_TOPIC_SIGNALS.findall(text))
    return min(0.4, matches * 0.1)


def _composite_score(art: dict) -> float:
    content = (art.get("content", "") or art.get("summary", "")).strip()
    url     = art.get("url", "")

    clen         = len(content)
    length_score = min(1.0, log(max(1, clen)) / log(2000))

    numbers      = len(_NUMBERS_RE.findall(content))
    cap_words    = len(_PROPERNOUN_RE.findall(content))
    word_count   = max(1, len(content.split()))
    entity_score = min(1.0, (numbers * 2 + cap_words) / max(1, word_count * 0.15))

    sentences = re.split(r'[.!?]+', content)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    if len(sentences) >= 4:
        lengths       = [len(s.split()) for s in sentences]
        avg           = sum(lengths) / len(lengths)
        variance      = sum((l - avg) ** 2 for l in lengths) / len(lengths)
        variety_score = min(1.0, variance / 80.0)
    else:
        variety_score = 0.05

    path_parts = [p for p in urlparse(url).path.split('/') if p]
    url_score  = min(1.0, len(path_parts) / 4.0)

    image_bonus = 0.2 if art.get("image_url") else 0.0
    it_boost    = _it_relevance_score(art)
    geo         = _geo_weight(art)

    base_score = (
        length_score  * 1.5 +
        entity_score  * 1.5 +
        variety_score * 1.0 +
        url_score     * 0.5 +
        image_bonus   +
        it_boost
    )

    return base_score * geo


# ═══════════════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════════════

def run_preflight_pipeline(articles: list[dict]) -> list[dict]:
    logger.info(f"[Pipeline] Starting pre-LLM pipeline with {len(articles)} articles")

    articles = _structural_filter(articles)
    articles = _semantic_dedup(articles)

    articles.sort(key=_composite_score, reverse=True)

    target_count = MAX_ARTICLES_TO_LLM if len(articles) >= MAX_ARTICLES_TO_LLM else len(articles)
    shortlist = articles[:target_count]

    logger.info(f"[Pipeline] Shortlist: {len(shortlist)} articles → sending to LLM")

    geo_counts = {}
    for a in shortlist:
        lvl = a.get("geo_scope") or "GLOBAL"
        geo_counts[lvl] = geo_counts.get(lvl, 0) + 1
    logger.info(f"[Pipeline] Geo distribution: {geo_counts}")

    return shortlist