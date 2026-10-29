# Exabyte Digital Store — Telegram VPN Bot, Mini App & Web Admin Panel

[![CI](https://github.com/Evan200291/tgbotexa/actions/workflows/ci.yml/badge.svg)](https://github.com/Evan200291/tgbotexa/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-0284C7.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-00F0FF.svg)](https://fastapi.tiangolo.com/)
[![aiogram 3.x](https://img.shields.io/badge/aiogram-3.x-2563EB.svg)](https://docs.aiogram.dev/)

An enterprise-ready **Telegram VPN Store** designed for Shadowsocks key sales and lifecycle management on **3X-UI** panels. Features a conversational Telegram Bot, a pop-up **Telegram Mini App** with a **Cyber Blues & Neon Tech Liquid Glass UI**, a full **Web Admin Panel**, and **Multi-Panel 3X-UI key combinations**.

---

## ✨ Key Features

- **Instant Key on Screenshot:** When a customer sends a KBZ Pay slip screenshot, the bot immediately provisions/extends the VPN key and delivers the key, QR, and connection links to the user first.
- **Rich Admin Controls:**
  - **Paid (✅):** Confirms order idempotently.
  - **Unpaid (❌):** Automatically revokes/rolls back the optimistically issued key across all panels and notifies the customer.
  - **Suspend / Resume (⏸️ / ▶️):** Instantly enable or disable a user's key across all connected 3X-UI servers.
  - **Edit Key (✏️):** Add/subtract days (`+7d`, `-7d`, `+30d`), add quota (`+5GB`), or revoke key.
  - **Direct Message (✉️):** Send a message to the customer straight from Telegram or the Web Admin Panel.
- **Multi-Panel 3X-UI Support (Key Combinations):**
  - Connect multiple 3X-UI servers sharing the same API version.
  - Provision keys identically across all active servers simultaneously.
  - Unified **Subscription Link** (`/sub/{sub_id}`) containing base64 configuration links for all nodes.
- **Telegram Mini App (`https://tgbot.lhpvpn.online`):**
  - High-end **Cyber Blues & Neon Tech** aesthetic with frosted liquid-glass panels (`backdrop-filter: blur(20px)`), electric cyan glows, and ambient cyber mesh.
  - Complete Burmese localization (Noto Sans Myanmar) with zero text clipping.
  - Real-time animated data usage gauge, countdown timers, one-click copy, and QR display.
- **Web Admin Panel (`/admin`):**
  - Access from any desktop or mobile browser using Telegram Login Widget or WebApp session.
  - Live revenue analytics, screenshot review gallery, client search & key management, 3X-UI server CRUD, store configuration, and global broadcasts to all active users.
- **Automated Background Jobs:**
  - Panel usage synchronization every 3 minutes.
  - Expiry notifications at 24 hours and 1 hour before key expiration.
  - Automatic expiration and key cleanup.
  - Order expiration for pending unpaid checkouts.

---

## 🛠️ Technology Stack

- **Backend:** Python 3.11+, FastAPI (ASGI), aiogram 3.x, HTTPX (async 3X-UI client), Pydantic Settings.
- **Database:** SQLite with Write-Ahead Logging (`WAL`), `foreign_keys=ON`, and automated schema migrations.
- **Reverse Proxy & SSL:** Caddy 2 with automated Let's Encrypt / ZeroSSL TLS certificates and HSTS security headers.
- **Containerization:** Docker & Docker Compose (running as non-root user `exabyte` with UID 10001).
- **Frontend:** Vanilla modern ES6+ JavaScript, CSS custom properties (no raw hex literals outside `theme.css`), SVG vector brand assets.

---

## 🚀 Local Development Setup

### 1. Clone & Set Up Virtual Environment

#### On Windows (PowerShell):
```powershell
git clone https://github.com/Evan200291/tgbotexa.git
cd tgbotexa
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
python scripts/install_hooks.py
```

#### On Linux / macOS:
```bash
git clone https://github.com/Evan200291/tgbotexa.git
cd tgbotexa
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python scripts/install_hooks.py
```

### 2. Run Tests & Code Quality Checks
```bash
# Run full test suite (59 unit and integration tests)
pytest -q

# Run Ruff linter
ruff check .

# Scan repository for accidental secret leaks
python scripts/check_secrets.py --all
```

### 3. Start Local Mock Development Server
```bash
python scripts/dev_server.py
```
Open your browser:
- **Customer Mini App:** `http://127.0.0.1:8080/` (click `👑` in header to toggle Customer/Admin view)
- **Web Admin Panel:** `http://127.0.0.1:8080/admin`
- **Living Design Kit:** `http://127.0.0.1:8080/dev/kit`

---

## 🌐 Ubuntu 22.04 / 24.04 VPS Step-by-Step Deployment

### Step 1: Server Prerequisites & DNS Verification
Ensure your domain `tgbot.lhpvpn.online` points to your VPS IP (`119.10.138.44`):
```bash
# Check DNS propagation
dig +short tgbot.lhpvpn.online
# Should output: 119.10.138.44
```

### Step 2: Install Docker & Docker Compose
If Docker is not already installed on your Ubuntu VPS:
```bash
# Update package index and install certificates
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Set up Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine and Compose plugin
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Enable Docker to start on boot
sudo systemctl enable --now docker
```

### Step 3: Check Port Conflicts (80 & 443)
The Caddy service requires ports `80` and `443` for automated Let's Encrypt certificates. Check if other web servers are occupying them:
```bash
sudo ss -tulpn | grep -E ':(80|443)'
```
- If your 3X-UI panel runs on port `8080` (e.g. `https://tpone.lhpvpn.online:8080/...`), ports `80` and `443` are free.
- If Apache or Nginx is occupying port 80/443 and not needed, stop and disable them:
  ```bash
  sudo systemctl stop apache2 nginx 2>/dev/null || true
  sudo systemctl disable apache2 nginx 2>/dev/null || true
  ```
- Allow incoming HTTP/HTTPS traffic through UFW firewall:
  ```bash
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
  ```

### Step 4: Clone Repository & Create Directory Structure
```bash
sudo mkdir -p /opt/tgbotexa
sudo chown -R $USER:$USER /opt/tgbotexa
git clone https://github.com/Evan200291/tgbotexa.git /opt/tgbotexa
cd /opt/tgbotexa

# Create persistent data and backup directories
mkdir -p data/backups data/screenshots
chmod 755 data
chmod +x scripts/*.sh
```

### Step 5: Configure Production Environment Variables
Create your production `.env` file from the template:
```bash
cp .env.example .env
nano .env
```
Fill in your production values:
```ini
ENVIRONMENT=production
DEV_MODE=false
BOT_TOKEN=<BOT_TOKEN>
ADMIN_IDS=1877867098

# Primary 3X-UI Panel
PANEL_BASE_URL=https://panel.example.com:8080/<SECRET_PATH>
PANEL_USERNAME=your_panel_username
PANEL_PASSWORD=your_panel_password
INBOUND_REMARK=exabytetgbot
SERVER_HOST=tpone.lhpvpn.online

# Public URLs
WEBAPP_URL=https://tgbot.lhpvpn.online
DATABASE_URL=sqlite+aiosqlite:///data/exabyte.sqlite3

# Store Details & KBZ Pay
KBZ_NUMBER=<KBZ_NUMBER>
KBZ_NAME=<KBZ_NAME>
SUPPORT_URL=https://t.me/Exabytedigitals
STORE_TAGLINE=လုံခြုံ မြန်ဆန် စိတ်ချရသော ဒစ်ဂျစ်တယ်ဆိုင်
```
> [!IMPORTANT]
> Keep `.env` strictly confidential. Permissions should be restricted:
> `chmod 600 .env`

### Step 6: Launch Containers with Docker Compose
```bash
docker compose up -d --build
```

### Step 7: Verify Service Health
Check container status:
```bash
docker compose ps
```
Both `exabyte-bot` and `exabyte-caddy` should display status `Up (healthy)` or `Up`.

Test the public HTTPS endpoint and healthcheck:
```bash
curl -I https://tgbot.lhpvpn.online/healthz
# HTTP/2 200 OK
```

View live container logs:
```bash
docker compose logs -f bot
```

---

## 🤖 Telegram @BotFather Configuration

Follow these steps with `@BotFather` on Telegram to complete your setup:

1. **Set Bot Description & About Text:**
   - `/setdescription` -> Send the text from [`exabyte_bot/webapp/static/brand/botfather.txt`](file:///e:/tgexabot/exabyte_bot/webapp/static/brand/botfather.txt).
   - `/setabouttext` -> `Exabyte Digital Store — High-Speed Shadowsocks VPN Service`.

2. **Set Profile Picture:**
   - `/setuserpic` -> Upload the generated high-resolution avatar image:
     `exabyte_bot/webapp/static/brand/avatar-640.png`

3. **Configure the WebApp Menu Button:**
   - `/setmenubutton`
   - Select your bot.
   - Enter button text: `🚀 Open Store` (or `✨ စတိုးဖွင့်ရန်`)
   - Enter Mini App URL: `https://tgbot.lhpvpn.online`

4. **Set Bot Commands List:**
   - `/setcommands`
   ```text
   start - စတိုး ပင်မစာမျက်နှာသို့ သွားမည်
   key - ကျွန်ုပ်၏ VPN Key နှင့် QR ကြည့်မည်
   buy - VPN Plan ဝယ်ယူရန်
   trial - အခမဲ့ 7 ရက် စမ်းသပ် Key ရယူမည်
   help - အသုံးပြုနည်း နှင့် Support ဆက်သွယ်ရန်
   admin - Admin Panel (Admin သာ အသုံးပြုနိုင်သည်)
   ```

---

## 🖧 Multi-Panel 3X-UI Key Combinations

To replicate keys across multiple 3X-UI servers:
1. Open the Web Admin Panel at `https://tgbot.lhpvpn.online/admin` (or use `/admin` in the Telegram Bot).
2. Scroll to the **3X-UI ဆာဗာများ (Multi-Panel)** section.
3. Click **➕ 3X-UI ဆာဗာ ပေါင်းထည့်မည်** and enter:
   - **ဆာဗာအမည်:** e.g., `Server 2 - Singapore`
   - **Panel Base URL:** e.g., `https://server2.example.com:8080/<SECRET_PATH>`
   - **SERVER_HOST:** e.g., `sg2.lhpvpn.online`
   - **Username / Password:** Credentials for the secondary panel
   - **Inbound Remark:** `exabytetgbot`
4. Once added, all new trial and paid VPN keys are automatically provisioned across all active panels.
5. Customers receive individual `ss://` links for each location as well as an **All-in-One Subscription Link** (`https://tgbot.lhpvpn.online/sub/{sub_id}`).

---

## 🔄 Daily Operations & Updates

### Automated Updater Script
To update your running VPS deployment to the latest commit on `main`:
```bash
cd /opt/tgbotexa
./scripts/update.sh
```
This script automatically:
1. Backs up the SQLite database to `data/backups/`.
2. Pulls the latest changes from `origin/main`.
3. Rebuilds and restarts the Docker containers with zero downtime.
4. Prunes stale Docker images.

### Automated Nightly Database Backups
Add a cron job to automatically backup your SQLite database every midnight:
```bash
crontab -e
```
Add the following line:
```cron
0 0 * * * cp /opt/tgbotexa/data/exabyte.sqlite3 /opt/tgbotexa/data/backups/backup_$(date +\%Y\%m\%d).sqlite3 && find /opt/tgbotexa/data/backups/ -name "backup_*.sqlite3" -mtime +30 -delete
```

### Database Restoration Procedure
In the event you need to restore from a backup:
```bash
docker compose stop bot
cp data/backups/exabyte_db_YYYYMMDD_HHMMSS.sqlite3 data/exabyte.sqlite3
docker compose start bot
```

---

## 🔒 Security & Best Practices

- **Pre-Commit Secret Hooks:** Any attempt to commit `.env`, private keys, or credentials will be rejected by `scripts/check_secrets.py`.
- **Non-Root Execution:** The application executes inside Docker under UID 10001 (`exabyte`) with minimal privileges.
- **HMAC Verification:** All Telegram Mini App data is cryptographically verified using SHA-256 HMAC against your `BOT_TOKEN`.
- **Database Safety:** SQLite operates in `WAL` mode with foreign keys enabled to prevent corruption during concurrent reads/writes.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
