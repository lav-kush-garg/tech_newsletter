"""
Main Pipeline
==============
Executes news fetching, content enrichment, data filtering, 
AI-scoring, visual layout assembly, and recipient mail delivery.
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

def _setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    fmt   = "%(asctime)s  %(levelname)-7s  %(message)s"
    logging.basicConfig(level=level, format=fmt, handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/pipeline.log", encoding="utf-8"),
    ])

Path("logs").mkdir(exist_ok=True)
Path("generated_cards").mkdir(exist_ok=True)

from config.settings           import TIMEZONE
from utils.database            import init_db, mark_articles_sent, log_run, get_active_recipients, purge_old_articles
from fetchers.rss_fetcher      import fetch_all_rss
from fetchers.scraper          import fetch_all_scraped
from fetchers.content_enricher import enrich_articles
from filters.preflight         import run_preflight_pipeline
from llm.scorer                import score_all_articles
from card_generator            import generate_all_cards, clear_old_cards, generate_email_assets
from newsletter.builder        import build_email_html, build_plain_text
from newsletter.sender         import send_newsletter


def run_pipeline(dry_run: bool = False, no_send: bool = False) -> dict:
    run_start = datetime.now(timezone.utc)
    logger    = logging.getLogger(__name__)
    init_db()
    purge_old_articles()

    recipients = get_active_recipients()
    if not recipients and not dry_run and not no_send:
        return {"status": "no_recipients", "fetched": 0, "sent": 0}

    all_raw = fetch_all_rss() + fetch_all_scraped()
    if not all_raw:
        return {"status": "no_articles", "fetched": 0, "sent": 0}

    enriched = enrich_articles(all_raw, max_workers=8)
    shortlist = run_preflight_pipeline(enriched)

    if dry_run:
        return {"status": "dry_run", "fetched": len(all_raw), "shortlist": len(shortlist)}

    final_articles = score_all_articles(shortlist)
    if not final_articles:
        return {"status": "no_articles_passed", "fetched": len(all_raw), "sent": 0}

    # Generate the cards
    clear_old_cards()
    final_articles = generate_all_cards(final_articles)

    # Generate the Date Header and Category Badges
    local_time = run_start.astimezone(ZoneInfo(TIMEZONE))
    date_str = local_time.strftime("%d %b %Y")
    unique_cats = {a.get("category", "BIGTECH") for a in final_articles}
    assets = generate_email_assets(date_str, unique_cats)

    # Pass the assets into the builder and sender
    html_body  = build_email_html(final_articles, assets)
    plain_body = build_plain_text(final_articles)

    if no_send:
        logger.info("\n🔇 NO SEND mode — pipeline executed, cards built, but email dispatch bypassed.")
        log_run(len(all_raw), len(final_articles), recipients, status="no_send")
        return {"status": "no_send", "fetched": len(all_raw), "sent": len(final_articles)}

    success = send_newsletter(html_body, plain_body, final_articles, recipients, assets)

    if success:
        mark_articles_sent(final_articles)
        log_run(len(all_raw), len(final_articles), recipients, status="ok")
        return {"status": "ok", "fetched": len(all_raw), "sent": len(final_articles)}
    else:
        log_run(len(all_raw), len(final_articles), recipients, status="send_failed")
        return {"status": "send_failed", "fetched": len(all_raw), "sent": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-send", action="store_true")
    parser.add_argument("--debug",   action="store_true")
    args = parser.parse_args()
    _setup_logging(debug=args.debug)
    print(run_pipeline(dry_run=args.dry_run, no_send=args.no_send))