#!/usr/bin/env python3
"""
test_bot.py — Diagnostic tool for the Netflix OTP Telegram Bot

Commands:
  python test_bot.py          → Test Telegram: show recent chat IDs + send test message
  python test_bot.py email    → Test Email: connect to IMAP and scan inbox
  python test_bot.py otp      → Test OTP regex against sample Netflix email text
"""

import imaplib
import email
import os
import re
import sys
import urllib.parse
import urllib.request
import json
from email.header import decode_header

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID     = os.getenv("TELEGRAM_CHAT_ID", "")
EMAIL_ADDR  = os.getenv("EMAIL_ADDRESS", "")
EMAIL_PASS  = os.getenv("EMAIL_PASSWORD", "")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT   = int(os.getenv("IMAP_PORT", "993"))
NETFLIX_SENDERS = [
    s.strip().lower()
    for s in os.getenv("NETFLIX_SENDER", "info@account.netflix.com,info@mailer.netflix.com").split(",")
]

BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def api(method, params=None):
    url = f"{BASE}/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def decode_mime(value):
    parts = decode_header(value)
    out = []
    for part, charset in parts:
        if isinstance(part, bytes):
            out.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(part)
    return "".join(out)


def get_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in disp:
                payload = part.get_payload(decode=True)
                if payload:
                    body += payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            elif ct == "text/html" and not body and "attachment" not in disp:
                payload = part.get_payload(decode=True)
                if payload:
                    html = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                    body += re.sub(r"<[^>]+>", " ", html)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return body


OTP_PATTERNS = [
    r"(?:verification|confirm|access|security|sign.?in)[^\d]{0,30}(\d{4,8})",
    r"(?:code|OTP|passcode)[^\d]{0,10}(\d{4,8})",
    r"\b(\d{4,8})\b",
]

def extract_otp(text):
    for pattern in OTP_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1), pattern
    return None, None


# ── Mode: telegram ────────────────────────────────────────────────────────────

def test_telegram():
    print("\n── Bot Info ─────────────────────────────────────")
    me = api("getMe")["result"]
    print(f"  Name     : {me['first_name']}")
    print(f"  Username : @{me['username']}")

    print("\n── Recent Updates (Chat IDs) ────────────────────")
    result = api("getUpdates", {"limit": 20})["result"]
    if not result:
        print("  ⚠️  No updates found.")
        print("  → Make sure the main bot is STOPPED, then send a message in Telegram and re-run.")
    else:
        seen = set()
        for u in result:
            chat = (u.get("message") or u.get("my_chat_member") or u.get("channel_post") or {}).get("chat", {})
            cid = chat.get("id")
            if cid and cid not in seen:
                seen.add(cid)
                print(f"\n  Chat ID : {cid}")
                print(f"  Type    : {chat.get('type', '?')}")
                print(f"  Name    : {chat.get('title') or chat.get('first_name', 'N/A')}")

    print("\n── Send Test Message ────────────────────────────")
    if not CHAT_ID:
        print("  ⚠️  TELEGRAM_CHAT_ID not set in .env — skipping.\n")
        return
    print(f"  Sending to {CHAT_ID} ...")
    try:
        resp = api("sendMessage", {"chat_id": CHAT_ID, "text": "✅ Bot test successful! OTP forwarding is ready."})
        if resp.get("ok"):
            print("  ✅ Message sent! Check your Telegram group.\n")
        else:
            print(f"  ❌ API error: {resp}\n")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        print("  → Bot may not be in the group, or CHAT_ID is wrong.\n")


# ── Mode: email ───────────────────────────────────────────────────────────────

def test_email():
    print("\n── Email / IMAP Test ────────────────────────────")
    print(f"  Server  : {IMAP_SERVER}:{IMAP_PORT}")
    print(f"  Account : {EMAIL_ADDR}")
    print(f"  Watching: {', '.join(NETFLIX_SENDERS)}")

    if not EMAIL_ADDR or not EMAIL_PASS:
        print("\n  ❌ EMAIL_ADDRESS or EMAIL_PASSWORD not set in .env")
        return

    print("\n  Connecting...")
    try:
        with imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT) as imap:
            imap.login(EMAIL_ADDR, EMAIL_PASS)
            print("  ✅ Login successful!")

            # Get list of all mailboxes
            status, mailboxes = imap.list()
            mailbox_names = []
            if status == "OK":
                for mailbox in mailboxes:
                    parts = mailbox.decode("utf-8").split(' "/" ')
                    if len(parts) == 2:
                        mailbox_names.append(parts[1].strip('"'))
            
            for name in list(mailbox_names):
                if "updates" in name.lower():
                    mailbox_names.remove(name)
                    mailbox_names.insert(0, name)

            found = 0
            scanned_total = 0

            print(f"  Scanning across {len(mailbox_names)} folders for recent Netflix emails...\n")

            for mailbox in mailbox_names:
                if found >= 5 or scanned_total >= 50:  # Cap the test scan
                    break

                try:
                    status, _ = imap.select(f'"{mailbox}"', readonly=True)
                    if status != "OK":
                        continue

                    # Search ALL to see recent history (not just unread)
                    status, data = imap.search(None, "ALL")
                    all_ids = data[0].split() if data[0] else []
                    
                    if not all_ids:
                        continue

                    # Look at the last 10 emails in this folder
                    recent = all_ids[-10:] if len(all_ids) >= 10 else all_ids
                    
                    for msg_id in reversed(recent):
                        scanned_total += 1
                        _, msg_data = imap.fetch(msg_id, "(RFC822)")
                        raw = msg_data[0][1]
                        msg = email.message_from_bytes(raw)

                        from_hdr = decode_mime(msg.get("From", ""))
                        subject  = decode_mime(msg.get("Subject", "(no subject)"))
                        from_lower = from_hdr.lower()

                        is_netflix = any(s in from_lower for s in NETFLIX_SENDERS)

                        if is_netflix:
                            found += 1
                            print(f"  [🎬 NETFLIX] {subject[:50]:<50} | Folder: {mailbox}")
                            body = get_body(msg)
                            otp, pattern = extract_otp(body)
                            if otp:
                                print(f"           └─ ✅ OTP extracted: {otp}  (matched: {pattern})")
                            else:
                                print(f"           └─ ⚠️  No OTP found in body")
                                snippet = " ".join(body.split())[:150]
                                print(f"              Snippet: {snippet}")

                except Exception as e:
                    print(f"  ❌ Error scanning {mailbox}: {e}")

            if found == 0:
                print(f"\n  ⚠️  No Netflix emails found in the last {scanned_total} messages across {len(mailbox_names)} folders.")
                print("  → Send yourself a Netflix verification email and re-run.")

    except imaplib.IMAP4.error as e:
        print(f"\n  ❌ IMAP error: {e}")
        print("  → For Gmail: use an App Password, not your regular password.")
        print("  → For Outlook: use outlook.office365.com as IMAP_SERVER.")
    except Exception as e:
        print(f"\n  ❌ Unexpected error: {e}")


# ── Mode: otp ─────────────────────────────────────────────────────────────────

def test_otp():
    samples = [
        ("Netflix code in body",      "Your verification code is: 483920. Use it within 15 minutes."),
        ("OTP label",                  "OTP: 7291"),
        ("Sign-in code",               "Sign-in code 123456 for your Netflix account."),
        ("Standalone number",          "Please use the code 8821 to verify your identity."),
        ("HTML-stripped",              "Enter code\n  \n482910\n to continue."),
        ("No number (should fail)",    "Welcome to Netflix! Enjoy your streaming."),
    ]

    print("\n── OTP Regex Test ───────────────────────────────")
    for label, text in samples:
        otp, pattern = extract_otp(text)
        status = f"✅ {otp}" if otp else "❌ not found"
        print(f"  {label:<35} → {status}")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "telegram"

    if mode == "email":
        test_email()
    elif mode == "otp":
        test_otp()
    else:
        test_telegram()
