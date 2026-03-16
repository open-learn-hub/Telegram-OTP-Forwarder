# Deploying Netflix OTP Bot to Vultr VPS

> Target: **Vultr Cloud Compute — Regular Performance**
> OS: **Debian 12 (Bookworm)**

---

## 1. Create the VPS on Vultr

1. Log in at [vultr.com](https://vultr.com) → **Deploy New Server**
2. **Type:** Cloud Compute – Regular Performance
3. **Location:** pick the closest to you
4. **Image:** Debian 12 (Bookworm)
5. **Plan:** Select the tier that suits your needs — the lowest available option is sufficient for this bot
6. **SSH Keys:** add your public key (recommended) or use the root password emailed to you
7. Click **Deploy Now** — server is ready in ~60 seconds

---

## 2. Connect via SSH

```bash
ssh root@YOUR_SERVER_IP
```

> Replace `YOUR_SERVER_IP` with the IP shown on your Vultr dashboard.

### First-time server setup

```bash
# Update packages
apt update && apt upgrade -y

# Create a non-root user (safer than running as root)
adduser botuser
usermod -aG sudo botuser

# Switch to the new user
su - botuser
```

---

## 3. Install Python

Debian 12 ships with Python 3.11. Verify it:

```bash
python3 --version        # should show 3.11.x or higher
sudo apt install -y python3-pip python3-venv git
```

---

## 4. Clone the Repository

```bash
cd ~
git clone https://github.com/open-learn-hub/Telegram-OTP-Forwarder.git
cd Telegram-OTP-Forwarder
```

---

## 5. Set Up Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 6. Configure the Bot

```bash
cp .env.example .env
nano .env
```

Fill in all required values:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=-1001234567890

EMAIL_ADDRESS=your_email@gmail.com
EMAIL_PASSWORD=your_app_password

IMAP_SERVER=imap.gmail.com
IMAP_PORT=993

POLL_INTERVAL_SECONDS=30
NETFLIX_SENDER=info@account.netflix.com,info@mailer.netflix.com
```

Save with `Ctrl+O`, exit with `Ctrl+X`.

---

## 7. Test It Manually First

```bash
# Email connection test
python3 test_bot.py email

# Telegram send test
python3 test_bot.py
```

If both work, proceed to run it as a service.

---

## 8. Run as a systemd Service (auto-start + auto-restart)

Create the service file:

```bash
sudo nano /etc/systemd/system/netflix-otp-bot.service
```

Paste this (adjust `botuser` and path if different):

```ini
[Unit]
Description=Netflix OTP Telegram Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/Telegram-OTP-Forwarder
EnvironmentFile=/home/botuser/Telegram-OTP-Forwarder/.env
ExecStart=/home/botuser/Telegram-OTP-Forwarder/.venv/bin/python3 Telegram_BOT.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable netflix-otp-bot
sudo systemctl start netflix-otp-bot
```

Check status:

```bash
sudo systemctl status netflix-otp-bot
```

Expected output:
```
● netflix-otp-bot.service - Netflix OTP Telegram Bot
     Active: active (running) since ...
```

---

## 9. View Live Logs

```bash
# Follow live logs
sudo journalctl -u netflix-otp-bot -f

# Last 50 lines
sudo journalctl -u netflix-otp-bot -n 50
```

---

## 10. Useful Management Commands

| Task | Command |
|---|---|
| Stop the bot | `sudo systemctl stop netflix-otp-bot` |
| Restart the bot | `sudo systemctl restart netflix-otp-bot` |
| Disable auto-start | `sudo systemctl disable netflix-otp-bot` |
| Edit `.env` config | `nano ~/Telegram-OTP-Forwarder/.env` then restart |
| Pull latest code | `cd ~/Telegram-OTP-Forwarder && git pull` then restart |

---

## 11. Basic Security (Recommended)

```bash
# Enable firewall — only allow SSH
sudo ufw allow OpenSSH
sudo ufw enable

# Install fail2ban to block brute-force SSH attempts
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## Updating the Bot in Future

```bash
cd ~/Telegram-OTP-Forwarder
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart netflix-otp-bot
```

---

> [!NOTE]
> The `.env` file stays on the server only — it is never committed to GitHub.
> Keep a local backup of your credentials in case you rebuild the server.
