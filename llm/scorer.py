"""
LLM Relevance Scorer
=====================
Scores articles for an IT/tech professional audience using Groq LLM.
"""

import json
import logging
import time
import re
from groq import Groq

from config.settings import (
    GROQ_API_KEY_1,
    GROQ_API_KEY_2,
    GROQ_API_KEY_3,
    GROQ_MODEL,
    LLM_TIMEOUT,
    MAX_ARTICLES_IN_EMAIL,
)

logger = logging.getLogger(__name__)

_groq_clients: list[Groq | None] = [None, None, None]

def _get_groq_client(index: int) -> Groq | None:
    global _groq_clients
    keys = [GROQ_API_KEY_1, GROQ_API_KEY_2, GROQ_API_KEY_3]
    if index >= len(keys):
        return None
    if _groq_clients[index] is None and keys[index]:
        try:
            _groq_clients[index] = Groq(api_key=keys[index])
        except Exception as e:
            logger.warning(f"[Groq] Could not init client #{index + 1}: {e}")
            return None
    return _groq_clients[index]


# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a tech news filter for a daily newsletter read by IT professionals: software developers, cloud engineers, cybersecurity analysts, DevOps, AI/ML engineers, digitalization leads, and operations tech staff.

KEEP articles about:
- AI/ML tools, frameworks, deployments, research breakthroughs
- Cloud platforms, DevOps, infrastructure, Kubernetes, containers
- Cybersecurity: threats, vulnerabilities, patches, zero-days, breaches
- Software development: languages, frameworks, open-source, APIs
- IoT, IIoT, smart manufacturing, Industry 4.0, automation
- Data centers, semiconductors, hardware for computing
- Digital transformation in enterprises or government
- Startups in Pune or India building tech products in the above sectors
- Connectivity: 5G, networking, edge computing

REJECT articles about:
- Funding rounds, acquisitions, IPOs, valuations, mergers (pure financial/deal news)
- Stock prices, market cap, quarterly earnings, analyst predictions
- Executive appointments, leadership changes, HR news
- Consumer lifestyle, entertainment, social media trends
- Generic opinion pieces, top-10 lists, event announcements
- Anything not relevant to hands-on IT practitioners

Output ONLY this JSON, no extra text:
{
  "verdict": "KEEP" or "REJECT",
  "summary": "<2 sentences, factual, present tense, zero hype>",
  "category": "<one of: AI, MANUFACTURING, IIOT, CLOUD, CYBERSECURITY, DATACENTERS, SEMICONDUCTOR, STARTUPS, BIGTECH, DIGITAL, CONNECTIVITY, SUSTAINABILITY, SUPPLYCHAIN, EMERGING>",
  "geo_scope": "<LOCAL, STATE, NATIONAL, or GLOBAL>",
  "yes_count": <1-6 based on how strongly it fits the KEEP criteria>
}"""


def _build_user_prompt(article: dict) -> str:
    title   = article.get("title", "")
    source  = article.get("source", "")
    content = (article.get("content", "") or article.get("summary", ""))[:2000]
    return f"SOURCE: {source}\nTITLE: {title}\n\nCONTENT:\n{content}"


def _call_groq(prompt: str) -> str | None:
    for idx in range(3):
        client = _get_groq_client(idx)
        if client is None:
            continue
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.1,
                max_tokens=300,
                timeout=LLM_TIMEOUT,
            )
            if idx > 0:
                logger.info(f"[Groq] Key #{idx + 1} succeeded")
            return response.choices[0].message.content

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate_limit" in err_str.lower():
                logger.warning(f"[Groq] Key #{idx + 1} rate limited — trying next key")
                time.sleep(0.5)
                continue
            elif "401" in err_str or "invalid_api_key" in err_str.lower():
                logger.error(f"[Groq] Key #{idx + 1} is invalid — skipping")
                continue
            else:
                logger.warning(f"[Groq] Key #{idx + 1} error: {e} — trying next key")
                continue

    logger.warning("[Groq] All 3 keys failed for this article")
    return None


def _parse_llm_response(raw: str) -> dict | None:
    if not raw:
        return None
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return None


def score_article(article: dict) -> dict | None:
    prompt = _build_user_prompt(article)
    raw    = _call_groq(prompt)

    if raw is None:
        return None

    result = _parse_llm_response(raw)
    if result is None:
        return None

    verdict = result.get("verdict", "REJECT").upper()
    if verdict != "KEEP":
        return None

    article["llm_summary"] = result.get("summary", article.get("summary", ""))
    article["category"]    = result.get("category", "BIGTECH")
    article["yes_count"]   = result.get("yes_count", 0)

    geo_raw = result.get("geo_scope", "GLOBAL").upper().strip()
    if geo_raw not in ("LOCAL", "STATE", "NATIONAL", "GLOBAL"):
        geo_raw = "GLOBAL"
    article["geo_scope"] = geo_raw
    return article


def score_all_articles(articles: list[dict]) -> list[dict]:
    logger.info(f"[LLM] Scoring {len(articles)} articles...")

    kept = []
    for i, art in enumerate(articles, 1):
        logger.info(f"[LLM] {i}/{len(articles)}: {art.get('title', '')[:70]}")
        result = score_article(art)

        if result:
            kept.append(result)
            logger.info(f"  ✅ KEEP — {result.get('category')} | geo={result.get('geo_scope')} | yes={result.get('yes_count')}")
        else:
            logger.info(f"  ❌ REJECT")

        if i < len(articles):
            time.sleep(1.2)

    kept.sort(key=lambda a: a.get("yes_count", 0), reverse=True)
    final = kept[:MAX_ARTICLES_IN_EMAIL]
    logger.info(f"[LLM] Final: {len(final)} articles for email.")
    return final