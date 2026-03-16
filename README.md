# 🎬 Netflix OTP Telegram Bot

A lightweight Python bot that monitors your email inbox and automatically
forwards Netflix verification / OTP codes to a Telegram group or chat.

---

## Features

- 📬 Watches your inbox via **IMAP** (Gmail, Outlook, Yahoo, and more)
- 🎯 Filters specifically for **Netflix sender** addresses
- 🔐 Extracts the **OTP / verification code** using smart regex
- 💬 Posts the code instantly to a **Telegram group or private chat**
- ♻️ Marks processed emails as **read** so codes are never sent twice
- ⚙️ Helper bot commands: `/start`, `/status`, `/chatid`

---

## Prerequisites

- Python 3.10+
- A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- IMAP access to your email account

---

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and chat with [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the **Bot Token** you receive

> ⚠️ If your token appears in source code, **regenerate it immediately** via
> `/mybots → API Token → Revoke current token`.

### 2. Add the Bot to Your Group

1. Create (or open) the Telegram group that should receive OTP messages
2. Add your bot as a **member** of the group
3. (Optional) Make it an admin so it can always post

### 3. Find Your Group Chat ID

Start the bot first (step 5), then: send `/chatid` in your group — the bot will reply with its numeric ID (e.g. `-1001234567890`).

### 4. Enable IMAP on Your Email Account

**Gmail:**
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification**
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Create an App Password for "Mail / Windows Computer"
5. Use this 16-character password as `EMAIL_PASSWORD`

**Outlook / Hotmail:**
- IMAP is enabled by default. Use `outlook.office365.com` as `IMAP_SERVER`.

**Yahoo Mail:**
- Enable IMAP in account settings. Use `imap.mail.yahoo.com` as `IMAP_SERVER`.
- Generate an app-specific password in your Yahoo account security settings.

### 5. Configure the Bot

```bash
# Copy the template
copy .env.example .env
```

Then edit `.env` with your real values:

```env
TELEGRAM_BOT_TOKEN=123456789:AAB...
TELEGRAM_CHAT_ID=-1001234567890

EMAIL_ADDRESS=you@gmail.com
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx   # Gmail App Password

IMAP_SERVER=imap.gmail.com
IMAP_PORT=993

POLL_INTERVAL_SECONDS=30
NETFLIX_SENDER=info@account.netflix.com,info@mailer.netflix.com
```

### 6. Install Dependencies

```bash
# (Recommended) Activate your virtual environment first
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

### 7. Run the Bot

```bash
python Telegram_BOT.py
```

You should see:
```
... | INFO     | netflix-otp-bot | ✅ Bot started. Listening for Netflix emails...
... | INFO     | netflix-otp-bot | 📬 Email poller started — checking every 30s ...
```

---

## Bot Commands

| Command   | Description                              |
|-----------|------------------------------------------|
| `/start`  | Show welcome message                     |
| `/status` | Show current configuration               |
| `/chatid` | Display this chat's ID (useful for setup)|

---

## How it Works

```
┌──────────────────────────────────────────────────┐
│  Every POLL_INTERVAL seconds                      │
│                                                   │
│  1. Connect to IMAP server over SSL               │
│  2. Search for UNSEEN emails in INBOX             │
│  3. For each unread email:                         │
│     a. Check if From: matches Netflix sender       │
│     b. If not Netflix → mark unread again, skip   │
│     c. If Netflix → extract body text             │
│     d. Run OTP regex on body                      │
│     e. If OTP found → send to Telegram group     │
└──────────────────────────────────────────────────┘
```

---

## Telegram Message Format

```
🔐 Netflix Verification Code

Your OTP code is:  123456

📧 From: info@account.netflix.com
📝 Subject: Your Netflix verification code
```

---

## Security Notes

- **Never commit `.env`** to version control — it is listed in `.gitignore`
- Keep your bot token secret; anyone with it can send messages as your bot
- Use an **App Password** for email, not your main account password
- The bot only reads **UNSEEN** emails and immediately marks them as seen

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `Missing required environment variable` | Copy `.env.example` to `.env` and fill all fields |
| IMAP login fails | Check credentials; for Gmail use an App Password |
| Bot doesn't post to group | Make sure the bot is a member of the group and `TELEGRAM_CHAT_ID` is correct (negative number) |
| OTP not extracted | Netflix may have changed their email format — check logs and open an issue |
| `CERTIFICATE_VERIFY_FAILED` | Ensure Python has up-to-date CA certificates |
