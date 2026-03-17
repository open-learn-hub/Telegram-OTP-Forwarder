# Running Netflix OTP Bot on macOS

To keep the bot running automatically on your Mac (even after a reboot or crash/power loss), use the provided `com.telegrambot.plist` configuration.

## Setup Instructions

1. **Configure the Plist**:
   Open `com.telegrambot.plist` and ensure the following paths are correct for your system:
   - Path to `caffeinate` (usually `/usr/bin/caffeinate`)
   - Path to `python3` (usually `/usr/bin/python3` or `/usr/local/bin/python3`)
   - **Crucial**: Update `/Users/YOUR_USER_NAME/Documents/my_bot.py` to the absolute path of your `Telegram_BOT.py` file.

2. **Move to LaunchAgents**:
   Copy your configuration file to the macOS LaunchAgents directory:
   ```bash
   cp com.telegrambot.plist ~/Library/LaunchAgents/
   ```

3. **Load and Start the Service**:
   Activate the service using `launchctl`:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.telegrambot.plist
   ```

## Keeping it Alive
The configuration uses several methods to ensure the bot stays running:
- **Caffeinate**: The `/usr/bin/caffeinate -ism` prefix prevents your Mac from sleeping or idling while the bot is active.
- **KeepAlive**: The `<key>KeepAlive</key><true/>` entry tells macOS to restart the bot immediately if it ever crashes.
- **RunAtLoad**: The bot will start automatically as soon as you log in.

## Maintenance Commands

**Stop the bot**:
```bash
launchctl unload ~/Library/LaunchAgents/com.telegrambot.plist
```

**View logs**:
```bash
tail -f /tmp/tgbot.out   # Standard output
tail -f /tmp/tgbot.err   # Error logs
```
