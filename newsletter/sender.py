"""
Email Sender
============
Sends the image-only structural email via SMTP.
Embeds `image.png`, `date_header.png`, category badges, and article cards via CID.
"""

import smtplib
import logging
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config.settings import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    SMTP_FROM_EMAIL, EMAIL_SENDER_NAME, TIMEZONE,
)

logger = logging.getLogger(__name__)

def send_newsletter(html_body: str, plain_body: str,
                    articles: list[dict], recipients: list[str], assets: dict) -> bool:
                    
    local_time = datetime.now(timezone.utc).astimezone(ZoneInfo(TIMEZONE))
    date_str   = local_time.strftime("%d %b %Y")
    
    # Exact subject string required
    subject = f"Daily tech news ({date_str})"

    try:
        root = MIMEMultipart("related")
        root["Subject"] = subject
        root["From"]    = f"{EMAIL_SENDER_NAME} <{SMTP_FROM_EMAIL or SMTP_USER}>"
        root["To"]      = ", ".join(recipients)

        alt = MIMEMultipart("alternative")
        root.attach(alt)
        alt.attach(MIMEText(plain_body, "plain", "utf-8"))
        alt.attach(MIMEText(html_body,  "html",  "utf-8"))

        # 1. Attach Root Folder Static Header (image.png)
        main_img_path = Path("image.png")
        if main_img_path.exists():
            mime_img = MIMEImage(main_img_path.read_bytes())
            mime_img.add_header("Content-ID", "<main_header_img>")
            mime_img.add_header("Content-Disposition", "inline", filename="image.png")
            root.attach(mime_img)

        # 2. Attach Date Header generated asset
        if "date_header" in assets and Path(assets["date_header"]).exists():
            mime_img = MIMEImage(Path(assets["date_header"]).read_bytes())
            mime_img.add_header("Content-ID", "<date_header_img>")
            mime_img.add_header("Content-Disposition", "inline", filename="date_header.png")
            root.attach(mime_img)

        # 3. Attach Category Badges generated assets
        for key, path in assets.items():
            if key.startswith("badge_") and Path(path).exists():
                mime_img = MIMEImage(Path(path).read_bytes())
                mime_img.add_header("Content-ID", f"<{key}>")
                mime_img.add_header("Content-Disposition", "inline", filename=Path(path).name)
                root.attach(mime_img)

        # 4. Attach 826x241 Article Cards
        for idx, art in enumerate(articles, 1):
            card_path = art.get("card_path", "")
            if not card_path or not Path(card_path).exists():
                continue
            mime_img = MIMEImage(Path(card_path).read_bytes(), _subtype="png")
            mime_img.add_header("Content-ID", f"<card_{idx:03d}>")
            mime_img.add_header("Content-Disposition", "inline", filename=Path(card_path).name)
            root.attach(mime_img)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM_EMAIL or SMTP_USER, recipients, root.as_string())

        logger.info(f"[Email] ✅ Sent '{subject}' to {len(recipients)} recipients")
        return True

    except Exception as e:
        logger.error(f"[Email] ❌ Failed: {e}")
        return False