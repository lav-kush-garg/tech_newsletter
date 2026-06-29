"""
Card Generator
==============
Generates PNG card images (826x241) and dynamically builds header/badge assets.
"""

import os
import hashlib
import logging
import requests
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ── Card dimensions ───────────────────────────────────────────────────────────
CARD_W    = 826
CARD_H    = 241
THUMB_W   = 241   # square thumbnail matching the height
THUMB_H   = 241
PAD       = 24    # padding around text area

OUTPUT_DIR = Path("generated_cards")
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Colors ────────────────────────────────────────────────────────────────────
C_BG         = (255, 255, 255)
C_BORDER     = (220, 224, 230)
C_SOURCE     = (148, 163, 184)
C_TITLE      = (15,  23,  42)
C_SUMMARY    = (71,  85, 105)
C_BTN_L      = (255, 81,  47)
C_BTN_R      = (221, 36, 118)
C_BTN_TEXT   = (255, 255, 255)
C_DIVIDER    = (226, 232, 240)
C_THUMB_BG   = (27,  58, 107)
C_THUMB_TEXT = (255, 255, 255)

# ── Per-category badge colour themes (gradient left, gradient right, accent bar, text) ──
CATEGORY_COLORS = {
    "AI":             ((15,  23,  80),  (45,  85, 180),  (99, 179, 237),  (255, 255, 255)),
    "MANUFACTURING":  ((20,  60,  20),  (40, 120,  40),  (104, 211, 145), (255, 255, 255)),
    "IIOT":           ((10,  60,  80),  (20, 130, 160),  (99, 210, 219),  (255, 255, 255)),
    "CLOUD":          ((30,  30, 100),  (70,  70, 200),  (139, 148, 255), (255, 255, 255)),
    "CYBERSECURITY":  ((80,  10,  10),  (180,  30,  30), (252, 129, 129), (255, 255, 255)),
    "DATACENTERS":    ((20,  20,  60),  (50,  50, 130),  (160, 174, 232), (255, 255, 255)),
    "SEMICONDUCTOR":  ((60,  20,  80),  (130,  50, 170), (183, 148, 246), (255, 255, 255)),
    "STARTUPS":       ((120, 40,   0),  (210,  90,   0), (251, 191,  36), (255, 255, 255)),
    "BIGTECH":        ((10,  40,  80),  (20,  80, 160),  (96, 165, 250),  (255, 255, 255)),
    "DIGITAL":        ((0,   80,  80),  (0,  160, 140),  (52, 211, 153),  (255, 255, 255)),
    "CONNECTIVITY":   ((60,   0,  80),  (120,   0, 160), (192,  86, 240), (255, 255, 255)),
    "SUSTAINABILITY": ((0,   70,  30),  (0,  140,  60),  (74, 222, 128),  (255, 255, 255)),
    "SUPPLYCHAIN":    ((80,  40,   0),  (160,  80,   0), (251, 146,  60), (255, 255, 255)),
    "EMERGING":       ((40,  10,  80),  (100,  20, 160), (216, 180, 254), (255, 255, 255)),
}

# Fallback if category not in map
DEFAULT_COLORS = ((27, 58, 107), (45, 90, 160), (99, 179, 237), (255, 255, 255))

# ── Badge dimensions ──────────────────────────────────────────────────────────
BADGE_W  = 1160
BADGE_H  = 60      # reduced from 100 → 60
ACCENT_W = 8       # left colour accent bar width
TEXT_PAD = 22      # left padding after accent bar


def clear_old_cards():
    purged = 0
    for f in OUTPUT_DIR.glob("*.png"):
        try:
            f.unlink()
            purged += 1
        except Exception:
            pass
    logger.info(f"[CardGen] Cleared {purged} old cards")


def _slug(article: dict) -> str:
    key = article.get("url") or article.get("title") or "article"
    return hashlib.md5(key.encode()).hexdigest()[:16]


def _load_fonts():
    candidates_bold = [
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    candidates_reg = [
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]

    def find(paths, size):
        for p in paths:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    return {
        "source":  find(candidates_reg,  14),
        "title":   find(candidates_bold, 24),
        "summary": find(candidates_reg,  18),
        "btn":     find(candidates_bold, 16),
        "fallback":find(candidates_bold, 20),
        "header":  find(candidates_bold, 22),   # slightly smaller to fit 60px height
        "date":    find(candidates_bold, 26),
    }

_FONTS = None
def fonts():
    global _FONTS
    if _FONTS is None:
        _FONTS = _load_fonts()
    return _FONTS


def _tw(draw, text, font):
    try:
        return draw.textbbox((0,0), text, font=font)[2]
    except Exception:
        return len(text) * 8

def _th(draw, text, font):
    try:
        bb = draw.textbbox((0,0), text, font=font)
        return bb[3] - bb[1]
    except Exception:
        return 14

def _wrap(draw, text, font, max_w, max_lines=3):
    words = text.split()
    lines, line = [], ""
    for word in words:
        test = (line + " " + word).strip()
        if _tw(draw, test, font) <= max_w:
            line = test
        else:
            if line:
                lines.append(line)
                if len(lines) >= max_lines:
                    break
            line = word
    if line and len(lines) < max_lines:
        lines.append(line)
    if len(lines) == max_lines:
        last = lines[-1]
        while last and _tw(draw, last + "…", font) > max_w:
            last = last.rsplit(" ", 1)[0]
        lines[-1] = last + "…" if last != lines[-1] else lines[-1]
    return lines


# ── Brand/logo signal words — if these appear in the image URL, reject it ────
_LOGO_URL_SIGNALS = [
    "logo", "icon", "favicon", "avatar", "brand", "badge",
    "placeholder", "default", "fallback", "generic", "watermark",
    "apple-touch", "og-default", "site-image", "header-image",
    "banner-default", "social-default",
]

# ── Known brand domains — images from these are rejected unless the article
#    source actually belongs to that brand ────────────────────────────────────
_BRAND_DOMAIN_MAP = {
    "apple.com":      "Apple",
    "amazon.com":     "Amazon",
    "aws.amazon.com": "AWS Blog",
    "google.com":     "Google",
    "microsoft.com":  "Microsoft",
    "meta.com":       "Meta",
    "samsung.com":    "Samsung",
    "nvidia.com":     "NVIDIA",
    "intel.com":      "Intel",
    "openai.com":     "OpenAI",
    "redhat.com":     "Red Hat",
    "static.xx.fbcdn.net": "Meta",
    "googleusercontent.com": "Google",
}


def _image_url_is_valid(img_url: str, article_source: str) -> bool:
    """
    Returns False if the image URL is a logo/icon or belongs to a brand
    that does NOT match the article source — stops cross-brand thumbnail pollution.
    """
    if not img_url:
        return False

    url_lower = img_url.lower()

    # Reject obvious logo/icon URLs by filename signals
    for signal in _LOGO_URL_SIGNALS:
        if signal in url_lower:
            logger.debug(f"[CardGen] Rejected logo-signal image: {img_url}")
            return False

    # Reject brand-domain images that don't belong to this article's source
    from urllib.parse import urlparse
    try:
        img_domain = urlparse(img_url).netloc.lower().lstrip("www.")
    except Exception:
        return True  # can't parse, allow

    for brand_domain, brand_name in _BRAND_DOMAIN_MAP.items():
        if brand_domain in img_domain:
            source_lower = article_source.lower()
            brand_lower  = brand_name.lower()
            if brand_lower not in source_lower:
                logger.debug(
                    f"[CardGen] Rejected cross-brand image from {img_domain} "
                    f"for source '{article_source}'"
                )
                return False

    return True


def _download_thumb(url: str, article_source: str = "") -> Image.Image | None:
    if not url or url.startswith("data:"):
        return None

    # Pre-validate URL before downloading
    if not _image_url_is_valid(url, article_source):
        return None

    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")

        # Reject tiny images — likely icons or logos (under 200x150 px)
        if img.width < 200 or img.height < 150:
            logger.debug(f"[CardGen] Rejected tiny image {img.width}x{img.height}: {url}")
            return None

        # Reject extreme aspect ratios — banners, strips, icons
        aspect = img.width / max(img.height, 1)
        if aspect < 0.5 or aspect > 5.0:
            logger.debug(f"[CardGen] Rejected odd-aspect image {img.width}x{img.height}: {url}")
            return None

        return img

    except Exception:
        return None


def _make_thumb(img: Image.Image | None, source: str) -> Image.Image:
    if img:
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top  = max(0, (h - side) // 4)
        img  = img.crop((left, top, left + side, top + side))
        return img.resize((THUMB_W, THUMB_H), Image.LANCZOS)
    
    fb = Image.new("RGB", (THUMB_W, THUMB_H), C_THUMB_BG)
    d  = ImageDraw.Draw(fb)
    for x in range(0, THUMB_W + THUMB_H, 30):
        d.line([(x, 0), (x - THUMB_H, THUMB_H)], fill=(40, 75, 130), width=1)
    f = fonts()
    txt = (source or "Tech")[:12]
    tw  = _tw(d, txt, f["fallback"])
    th  = _th(d, txt, f["fallback"])
    d.text(((THUMB_W - tw)//2, (THUMB_H - th)//2), txt, font=f["fallback"], fill=C_THUMB_TEXT)
    return fb


def _gradient_rect(draw, x0, y0, x1, y1, c_left, c_right):
    w = x1 - x0
    for i in range(w):
        t = i / max(w - 1, 1)
        r = int(c_left[0] + (c_right[0] - c_left[0]) * t)
        g = int(c_left[1] + (c_right[1] - c_left[1]) * t)
        b = int(c_left[2] + (c_right[2] - c_left[2]) * t)
        draw.line([(x0 + i, y0), (x0 + i, y1)], fill=(r, g, b))


def _draw_badge(img: Image.Image, cat: str, label: str):
    """
    Draws a colourful gradient badge with:
    - Horizontal gradient background (dark left → slightly lighter right)
    - Bright left accent bar (8px)
    - LEFT-ALIGNED bold uppercase label text
    - NO emoji (avoids font rendering issues)
    """
    draw = ImageDraw.Draw(img)
    c_left, c_right, c_accent, c_text = CATEGORY_COLORS.get(cat, DEFAULT_COLORS)

    # Gradient background across full width
    _gradient_rect(draw, 0, 0, BADGE_W, BADGE_H, c_left, c_right)

    # Left accent bar
    draw.rectangle([0, 0, ACCENT_W - 1, BADGE_H], fill=c_accent)

    # Subtle diagonal line texture
    for x in range(0, BADGE_W + BADGE_H, 40):
        draw.line([(x, 0), (x - BADGE_H, BADGE_H)], fill=(255, 255, 255, 15), width=1)

    # Left-aligned label text, vertically centred
    f   = fonts()
    txt = label.upper()
    th  = _th(draw, txt, f["header"])
    tx  = ACCENT_W + TEXT_PAD
    ty  = (BADGE_H - th) // 2 - 1
    draw.text((tx, ty), txt, font=f["header"], fill=c_text)


def generate_email_assets(date_str: str, categories: set) -> dict:
    """Generates the 1160x60 date header and the 1160x60 category separator badges."""
    assets = {}
    f = fonts()

    # 1. Date Header Image (1160x60)
    dh_path = OUTPUT_DIR / "date_header.png"
    img_dh  = Image.new("RGB", (BADGE_W, BADGE_H), C_THUMB_BG)
    draw_dh = ImageDraw.Draw(img_dh)

    # Gradient background for date header
    _gradient_rect(draw_dh, 0, 0, BADGE_W, BADGE_H, (15, 30, 80), (27, 58, 107))
    draw_dh.rectangle([0, 0, ACCENT_W - 1, BADGE_H], fill=(99, 179, 237))

    txt_dh = date_str.upper()
    th_dh  = _th(draw_dh, txt_dh, f["date"])
    draw_dh.text(
        (ACCENT_W + TEXT_PAD, (BADGE_H - th_dh) // 2 - 1),
        txt_dh, font=f["date"], fill=C_THUMB_TEXT
    )
    img_dh.save(dh_path, "PNG", optimize=True)
    assets["date_header"] = str(dh_path)

    # 2. Category Badges (1160x60)
    from config.settings import SECTIONS
    for cat in categories:
        cb_path = OUTPUT_DIR / f"badge_{cat}.png"
        img_cb  = Image.new("RGB", (BADGE_W, BADGE_H), (30, 30, 30))
        info    = SECTIONS.get(cat, {"label": cat})
        _draw_badge(img_cb, cat, info["label"])
        img_cb.save(cb_path, "PNG", optimize=True)
        assets[f"badge_{cat}"] = str(cb_path)

    return assets


def generate_card(article: dict) -> str | None:
    slug     = _slug(article)
    out_path = OUTPUT_DIR / f"{slug}.png"
    if out_path.exists():
        return str(out_path)

    try:
        f       = fonts()
        title   = (article.get("title", "") or "").strip()
        summary = (article.get("llm_summary") or article.get("summary", "") or "").strip()
        source  = (article.get("source", "") or "").strip()
        
        card = Image.new("RGB", (CARD_W, CARD_H), C_BG)
        draw = ImageDraw.Draw(card)

        # Priority 1: pre-fetched content-relevant thumbnail saved by content_enricher
        thumb_path = article.get("thumb_path", "")
        raw_thumb  = None
        if thumb_path and Path(thumb_path).exists():
            try:
                from PIL import Image as _PIL_Image
                raw_thumb = _PIL_Image.open(thumb_path).convert("RGB")
                logger.debug(f"[CardGen] Using pre-fetched thumb: {thumb_path}")
            except Exception:
                raw_thumb = None

        # Priority 2: fallback — download from image_url (less reliable)
        if raw_thumb is None:
            raw_thumb = _download_thumb(article.get("image_url", ""), source)

        thumb = _make_thumb(raw_thumb, source)
        card.paste(thumb, (0, 0))
        draw.line([(THUMB_W, 0), (THUMB_W, CARD_H)], fill=C_DIVIDER, width=1)

        tx     = THUMB_W + PAD
        max_tw = CARD_W - tx - PAD
        y      = PAD + 6

        if source:
            draw.text((tx, y), source.upper(), font=f["source"], fill=C_SOURCE)
            y += _th(draw, source, f["source"]) + 12

        title_lines = _wrap(draw, title, f["title"], max_tw, max_lines=2)
        title_lh    = _th(draw, "Ag", f["title"]) + 6
        for line in title_lines:
            draw.text((tx, y), line, font=f["title"], fill=C_TITLE)
            y += title_lh
        y += 8

        sum_lines = _wrap(draw, summary, f["summary"], max_tw, max_lines=3)
        sum_lh    = _th(draw, "Ag", f["summary"]) + 6
        for line in sum_lines:
            draw.text((tx, y), line, font=f["summary"], fill=C_SUMMARY)
            y += sum_lh

        btn_text = "  Read more  "
        btn_tw   = _tw(draw, btn_text, f["btn"])
        btn_th   = _th(draw, btn_text, f["btn"])
        btn_pad  = 10
        btn_w    = btn_tw + btn_pad * 2
        btn_h    = btn_th + btn_pad * 2
        btn_x    = CARD_W - PAD - btn_w
        btn_y    = CARD_H - PAD - btn_h

        _gradient_rect(draw, btn_x, btn_y, btn_x + btn_w, btn_y + btn_h, C_BTN_L, C_BTN_R)
        draw.text((btn_x + btn_pad, btn_y + btn_pad), btn_text, font=f["btn"], fill=C_BTN_TEXT)
        draw.rectangle([0, 0, CARD_W - 1, CARD_H - 1], outline=C_BORDER, width=1)

        card.save(str(out_path), "PNG", optimize=True)
        return str(out_path)

    except Exception as e:
        logger.error(f"[CardGen] ❌ Failed: {e}")
        return None


def generate_all_cards(articles: list[dict]) -> list[dict]:
    ok = 0
    for art in articles:
        p = generate_card(art)
        art["card_path"] = p or ""
        if p:
            ok += 1
    return articles