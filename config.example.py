# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
ADMIN_ID = 123456789  # Your Telegram ID (legacy, use ADMIN_IDS instead)

# Список админов (получают уведомления о новых заявках)
ADMIN_IDS = [123456789]  # Telegram ID админов
ADMIN_USERNAMES = ["admin1", "admin2"]  # Username админов (без @)

# Project Settings
PROJECT_NAME = "PrideVPN"
VPN_BRAND_NAME = "PrideVPN"
DB_PATH = "vpn_users.db"

# Trial Settings
TRIAL_DAYS = 3
TRIAL_DURATION_MINUTES = 4320  # 3 days in minutes

# Business Logic
DAYS_PER_PAYMENT = 30
REFERRAL_BONUS_DAYS = 7
CRYPTO_PRICE = 5  # Example: 5 USDT/month
STRIKE_LIMIT = 3.0  # Block user after 3 strikes

# X-UI Panel Configuration
XUI_BASE_URL = "https://vpn.example.com/panel"
XUI_URL = "https://vpn.example.com/panel"
XUI_USERNAME = "admin"
XUI_LOGIN = "admin"
XUI_PASSWORD = "your_password"

# VPN Settings
XUI_INBOUND_ID = 1  # Your VLESS inbound ID
SERVER_DOMAIN = "vpn.example.com"
DOMAIN = "vpn.example.com"
WS_PATH = "/api/"
SUBSCRIPTION_URL = "https://vpn.example.com/sub/"

# Subscription Aggregator
SUBSCRIPTION_AGGREGATOR_URL = "https://vpn.example.com/sub/"

# Payment Systems
CRYPTOBOT_TOKEN = "YOUR_CRYPTOBOT_TOKEN"
CRYPTOBOT_CURRENCY = "USDT"

# YooKassa (optional)
# YOOKASSA_SHOP_ID = "your_shop_id"
# YOOKASSA_SECRET_KEY = "your_secret_key"

# Telegram Stars
STARS_PRICE = 20  # Price of 1 Star in rubles

# Tariffs (in rubles)
TARIFFS = {
    1: {"price": 150, "traffic_gb": 100},
    3: {"price": 350, "traffic_gb": 300},
    6: {"price": 600, "traffic_gb": 600},
    12: {"price": 900, "traffic_gb": 1200}
}

# Anti-abuse Settings
XUI_ACCESS_LOG = "/usr/local/x-ui/access.log"

# Referral Commission
REFERRAL_COMMISSION = 0.25  # 25% commission for referrers

# Reality VPN configs
VPN_SERVERS = {
    "main": {
        "ip": "YOUR_SERVER_IP",
        "port": 51191,
        "type": "tcp",
        "security": "reality",
        "flow": "xtls-rprx-vision",
        "sni": "ads.x5.ru",
        "fp": "chrome",
        "pbk": "YOUR_PUBLIC_KEY",
        "sid": "YOUR_SHORT_ID",
        "name": "PRIDE-VPN"
    },
    # Aliases for compatibility
    "mts": {
        "ip": "YOUR_SERVER_IP",
        "port": 51191,
        "type": "tcp",
        "security": "reality",
        "flow": "xtls-rprx-vision",
        "sni": "ads.x5.ru",
        "fp": "chrome",
        "pbk": "YOUR_PUBLIC_KEY",
        "sid": "YOUR_SHORT_ID",
        "name": "PRIDE-VPN"
    },
    "wifi": {
        "ip": "YOUR_SERVER_IP",
        "port": 51191,
        "type": "tcp",
        "security": "reality",
        "flow": "xtls-rprx-vision",
        "sni": "ads.x5.ru",
        "fp": "chrome",
        "pbk": "YOUR_PUBLIC_KEY",
        "sid": "YOUR_SHORT_ID",
        "name": "PRIDE-VPN"
    }
}
