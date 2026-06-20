#!/bin/bash
# deploy.sh — AI TO AI HOLDING: Oracle Cloud Ubuntu Setup
# รันครั้งเดียวหลัง SSH เข้า server ใหม่
# usage: bash deploy.sh

set -e
echo "======================================"
echo " AI TO AI HOLDING — Deploy Script"
echo "======================================"

APP_DIR="/home/ubuntu/ai-to-ai-holding"
SERVICE_NAME="ai-to-ai-holding"

# ── 1. System packages ────────────────────────────────────────
echo "[1/7] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git sqlite3

# ── 2. Clone / update code ────────────────────────────────────
echo "[2/7] Setting up application directory..."
if [ -d "$APP_DIR" ]; then
    echo "  Directory exists — pulling latest..."
    cd "$APP_DIR" && git pull
else
    echo "  Cloning repository..."
    git clone https://github.com/YOUR_GITHUB_USERNAME/ai-to-ai-holding.git "$APP_DIR"
fi

# ── 3. Python virtual environment ────────────────────────────
echo "[3/7] Creating Python virtual environment..."
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r AI_TO_AI_HOLDING/requirements.txt -q
echo "  Python packages installed."

# ── 4. Environment file ───────────────────────────────────────
echo "[4/7] Checking .env file..."
ENV_FILE="$APP_DIR/AI_TO_AI_HOLDING/.env"
if [ ! -f "$ENV_FILE" ]; then
    cp "$APP_DIR/AI_TO_AI_HOLDING/.env.example" "$ENV_FILE"
    echo ""
    echo "  ⚠️  .env file created from template."
    echo "  ➡️  แก้ไข .env ก่อนรัน service:"
    echo "      nano $ENV_FILE"
    echo ""
    echo "  สิ่งที่ต้องแก้:"
    echo "    API_KEYS=<สร้างด้วย: python3 -c \"import secrets; print(secrets.token_hex(32))\">"
    echo "    CHAIRMAN_ALLOWED_IPS=<IP จริงของคุณ>"
    echo "    ALLOWED_ORIGINS=https://yourdomain.com"
    echo ""
    read -p "  กด Enter หลังแก้ .env เสร็จแล้ว..."
else
    echo "  .env found — skipping."
fi

# ── 5. Database init ──────────────────────────────────────────
echo "[5/7] Initializing database..."
cd "$APP_DIR/AI_TO_AI_HOLDING"
source "$APP_DIR/venv/bin/activate"
python3 -c "import asyncio; from database import init_db; asyncio.run(init_db())"
echo "  Database initialized."

# ── 6. Systemd service ────────────────────────────────────────
echo "[6/7] Installing systemd service..."
sudo cp "$APP_DIR/AI_TO_AI_HOLDING/ai-to-ai-holding.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
sleep 2
STATUS=$(sudo systemctl is-active "$SERVICE_NAME")
if [ "$STATUS" = "active" ]; then
    echo "  ✅ Service running: $STATUS"
else
    echo "  ❌ Service failed. Check logs:"
    echo "     sudo journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

# ── 7. Nginx ──────────────────────────────────────────────────
echo "[7/7] Configuring nginx..."
sudo cp "$APP_DIR/AI_TO_AI_HOLDING/nginx.conf" /etc/nginx/sites-available/$SERVICE_NAME
sudo ln -sf /etc/nginx/sites-available/$SERVICE_NAME /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
echo "  nginx configured."

# ── Done ──────────────────────────────────────────────────────
echo ""
echo "======================================"
echo " ✅ Deploy เสร็จแล้ว!"
echo "======================================"
echo ""
echo "ขั้นตอนต่อไป:"
echo "  1. ชี้ domain ไปที่ IP นี้:"
echo "     $(curl -s https://api.ipify.org)"
echo ""
echo "  2. ขอ SSL certificate:"
echo "     sudo certbot --nginx -d yourdomain.com"
echo ""
echo "  3. ทดสอบ API:"
echo "     curl https://yourdomain.com/health"
echo ""
echo "  4. ดู logs:"
echo "     sudo journalctl -u $SERVICE_NAME -f"
