#!/usr/bin/env python3
"""
Netflix OTP Telegram Bot
========================
Monitors an email inbox via IMAP for Netflix verification emails and
forwards the OTP code to a configured Telegram group/chat.

Setup:
  1. Copy .env.example to .env and fill in your credentials.
  2. Run: python Telegram_BOT.py
"""

import asyncio
import email
import imaplib
import logging
import os
import re
from email.header import decode_header
from typing import Optional

from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

# ─── Load configuration ───────────────────────────────────────────────────────
load_dotenv()

BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
EMAIL_ADDRESS: str = os.getenv("EMAIL_ADDRESS", "")
EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")
IMAP_SERVER: str = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))
POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
# Accept comma-separated list of Netflix sender addresses
NETFLIX_SENDERS: list[str] = [
    s.strip().lower()
    for s in os.getenv(
        "NETFLIX_SENDER", "info@account.netflix.com,info@mailer.netflix.com"
    ).split(",")
]

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logger = logging.getLogger("netflix-otp-bot")


# ─── OTP extraction ───────────────────────────────────────────────────────────

# Patterns ordered from most specific to least specific
OTP_PATTERNS = [
    # "Your verification code is: 123456"
    r"(?:verification|confirm|access|security|sign.?in)[^\d]{0,30}(\d{4,8})",
    # "Code: 123456" or "OTP: 123456"
    r"(?:code|OTP|passcode)[^\d]{0,10}(\d{4,8})",
    # Standalone 4-8 digit number (last resort)
    r"\b(\d{4,8})\b",
]


def extract_otp(text: str) -> Optional[str]:
    """Try to extract an OTP code from email body text."""
    for pattern in OTP_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


# ─── Email utilities ──────────────────────────────────────────────────────────


def decode_mime_words(value: str) -> str:
    """Decode encoded email header values."""
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def get_email_body(msg: email.message.Message) -> str:
    """Extract plain-text body from an email message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="replace")
            elif content_type == "text/html" and not body and "attachment" not in disposition:
                # Fallback: strip HTML tags from HTML-only emails
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    body += re.sub(r"<[^>]+>", " ", html)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
    return body


def is_netflix_sender(from_header: str) -> bool:
    """Check whether the From: header matches any configured Netflix sender."""
    from_lower = from_header.lower()
    return any(sender in from_lower for sender in NETFLIX_SENDERS)


# ─── IMAP polling loop ────────────────────────────────────────────────────────


async def poll_email(bot: Bot) -> None:
    """
    Background task: poll the inbox every POLL_INTERVAL seconds.
    Marks processed emails as seen so they are never forwarded twice.
    """
    logger.info(
        "📬 Email poller started — checking every %ds for emails from: %s",
        POLL_INTERVAL,
        ", ".join(NETFLIX_SENDERS),
    )

    while True:
        try:
            await _check_inbox(bot)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("❌ Error during inbox check: %s", exc)

        await asyncio.sleep(POLL_INTERVAL)


async def _check_inbox(bot: Bot) -> None:
    """Connect to IMAP, search for unread Netflix emails, and forward OTPs."""
    # Run blocking IMAP I/O in a thread so we don't block the event loop
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, _fetch_netflix_emails)

    for subject, sender, otp in results:
        logger.info("🔐 OTP found: %s | Subject: %s", otp, subject)
        await _send_otp_to_telegram(bot, subject, sender, otp)


def _fetch_netflix_emails() -> list[tuple[str, str, str]]:
    """
    Synchronous IMAP fetch (runs in executor).
    Returns list of (subject, sender, otp) tuples for unread Netflix OTP emails.
    Scans across all available folders, not just INBOX.
    """
    found: list[tuple[str, str, str]] = []

    with imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT) as imap:
        imap.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        
        # Get list of all mailboxes
        status, mailboxes = imap.list()
        if status != "OK":
            return found
            
        # Extract mailbox names handling spaces and quotes correctly
        mailbox_names = []
        for mailbox in mailboxes:
            # imap.list() returns items like: b'(\\HasNoChildren) "/" "INBOX"'
            # or b'(\\HasNoChildren) "/" "[Gmail]/All Mail"'
            parts = mailbox.decode("utf-8").split(' "/" ')
            if len(parts) == 2:
                mailbox_names.append(parts[1].strip('"'))
                
        for name in list(mailbox_names):
            if "updates" in name.lower():
                mailbox_names.remove(name)
                mailbox_names.insert(0, name)

        for mailbox in mailbox_names:
            try:
                # Need to quote mailbox names spaces, e.g. "[Gmail]/All Mail"
                status, _ = imap.select(f'"{mailbox}"', readonly=False)
                if status != "OK":
                    continue

                # Search for UNSEEN emails
                status, message_ids = imap.search(None, "UNSEEN")
                if status != "OK" or not message_ids[0]:
                    continue

                msg_ids = message_ids[0].split()
                msg_ids.reverse()  # Process newest emails first

                for msg_id in msg_ids:
                    # If we already found an OTP in any folder, mark the rest as SEEN and skip
                    if found:
                        imap.store(msg_id, "+FLAGS", "\\Seen")
                        continue

                    status, msg_data = imap.fetch(msg_id, "(RFC822)")
                    if status != "OK":
                        continue

                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)

                    from_header = decode_mime_words(msg.get("From", ""))
                    subject = decode_mime_words(msg.get("Subject", "(no subject)"))

                    # Filter: only Netflix senders
                    if not is_netflix_sender(from_header):
                        # Mark back as unread so we don't skip legitimate unread mail
                        imap.store(msg_id, "-FLAGS", "\\Seen")
                        continue

                    logger.info("📧 Netflix email found in %s — Subject: %s", mailbox, subject)

                    body = get_email_body(msg)
                    otp = extract_otp(body)

                    if otp:
                        found.append((subject, from_header, otp))
                    else:
                        logger.warning(
                            "⚠️  Could not extract OTP from Netflix email. Subject: %s", subject
                        )
            except Exception as e:
                logger.error("Error scanning mailbox %s: %s", mailbox, e)

    return found


async def _send_otp_to_telegram(bot: Bot, subject: str, sender: str, otp: str) -> None:
    """Send an OTP notification message to the configured Telegram chat."""
    message = (
        "🔐 *Netflix Verification Code*\n\n"
        f"Your OTP code is:  `{otp}`\n\n"
        f"📧 *From:* {sender}\n"
        f"📝 *Subject:* {subject}"
    )
    await bot.send_message(
        chat_id=CHAT_ID,
        text=message,
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    logger.info("✅ OTP sent to Telegram chat %s", CHAT_ID)


# ─── Telegram command handlers ────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /start — shows a welcome message."""
    text = (
        "👋 Netflix OTP Bot is running!\n\n"
        "I watch your inbox for Netflix verification emails and forward "
        "the OTP code to this chat automatically.\n\n"
        "Available commands:\n"
        "  /start  — show this message\n"
        "  /status — show current configuration\n"
        "  /chatid — show this chat's ID"
    )
    await update.message.reply_text(text)


async def cmd_chatid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /chatid — useful for finding the group's chat ID."""
    chat = update.effective_chat
    await update.message.reply_text(
        f"ℹ️ Chat info:\n"
        f"  ID     : {chat.id}\n"        
        f"  Title  : {chat.title or 'N/A'}\n"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /status — shows the current bot configuration."""
    configured_chat = CHAT_ID if CHAT_ID else "not set"
    email_masked = (
        EMAIL_ADDRESS[:3] + "***" + EMAIL_ADDRESS[EMAIL_ADDRESS.index("@"):]
        if "@" in EMAIL_ADDRESS
        else "not set"
    )
    senders = ", ".join(NETFLIX_SENDERS)

    text = (
        "⚙️ Bot Status\n\n"
        f"📬 Monitoring  : {email_masked}\n"
        f"🖥️ IMAP        : {IMAP_SERVER}:{IMAP_PORT}\n"
        f"🎯 Senders     : {senders}\n"
        f"⏱️ Poll every  : {POLL_INTERVAL}s\n"
        f"💬 Target chat : {configured_chat}"
    )
    await update.message.reply_text(text)


# ─── Post-init hook: start the email polling background task ──────────────────


async def post_init(application: Application) -> None:
    """Called once after the Application is initialised — schedule the email poller."""
    # Schedule the polling coroutine on the already-running event loop
    asyncio.ensure_future(poll_email(application.bot))
    logger.info("✅ Bot started. Email poller scheduled.")


# ─── Config validation ────────────────────────────────────────────────────────


def _validate_config() -> None:
    """Raise an informative error if any required env var is missing."""
    required = {
        "TELEGRAM_BOT_TOKEN": BOT_TOKEN,
        "TELEGRAM_CHAT_ID": CHAT_ID,
        "EMAIL_ADDRESS": EMAIL_ADDRESS,
        "EMAIL_PASSWORD": EMAIL_PASSWORD,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variable(s): {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in the values."
        )


# ─── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    _validate_config()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("chatid", cmd_chatid))
    app.add_handler(CommandHandler("status", cmd_status))

    logger.info("🚀 Starting Netflix OTP Telegram Bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()