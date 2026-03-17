# Running Netflix OTP Bot on macOS

To keep the bot running automatically on your Mac (even after a reboot or crash/power loss), use the provided `com.telegram.opt-forwarder.bot.plist` configuration.

## Setup Instructions

### 1. Install Dependencies
Ensure you have the required Python packages installed on your Mac:
```bash
# It is recommended to use your project's virtual environment
# source .venv/bin/activate

pip3 install -r requirements.txt
```

### 2. Configure the Plist
   Open `com.telegram.opt-forwarder.bot.plist` and ensure the following paths are correct for your system:
   - Path to `caffeinate` (usually `/usr/bin/caffeinate`)
   - Path to `python3` (usually `/usr/bin/python3` or `/usr/local/bin/python3`)
   - **Crucial**: Update `/Users/YOUR_USER_NAME/Documents/Telegram_BOT.py` to the absolute path of your `Telegram_BOT.py` file.

### 3. Move to LaunchAgents
   Copy your configuration file to the macOS LaunchAgents directory:
   ```bash
   cp com.telegram.opt-forwarder.bot.plist ~/Library/LaunchAgents/
   ```

### 4. Load and Start the Service
   Activate the service using `launchctl`:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.telegram.opt-forwarder.bot.plist
   ```

## Keeping it Alive
The configuration uses several methods to ensure the bot stays running:
- **Caffeinate**: The `/usr/bin/caffeinate -ism` prefix prevents your Mac from sleeping or idling while the bot is active.
- **KeepAlive**: The `<key>KeepAlive</key><true/>` entry tells macOS to restart the bot immediately if it ever crashes.
- **RunAtLoad**: The bot will start automatically as soon as you log in.

## Maintenance Commands

**Stop the bot**:
```bash
launchctl unload ~/Library/LaunchAgents/com.telegram.opt-forwarder.bot.plist
```

**View logs**:
```bash
tail -f /tmp/tgbot.out   # Standard output
tail -f /tmp/tgbot.err   # Error logs
```
