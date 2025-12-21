# PRIDE VPN Bot

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![aiogram 3.4+](https://img.shields.io/badge/aiogram-3.4+-green.svg)](https://docs.aiogram.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Корпоративный Telegram-бот для управления VPN-доступом с системой модерации заявок, интеграцией с X-UI панелью и автоматической генерацией конфигов.

![PRIDE VPN](pridevpn.png)

## Возможности

### Система модерации доступа
- **Запрос доступа** - пользователь нажимает кнопку и пишет комментарий (кто он, зачем VPN)
- **Уведомление админам** - все админы получают заявку с кнопками "Подтвердить" / "Отказать"
- **Автоматическое создание** - при одобрении создаётся VPN-клиент в X-UI и генерируется ссылка на подписку
- **Транслитерация имён** - sub_id генерируется из имени пользователя (Иван Петров → ivan_petrov)

### Subscription Aggregator
- **Красивая HTML-страница** с QR-кодом для каждого пользователя
- **VLESS + Reality** конфигурация
- **Автоматическое обновление** при добавлении новых пользователей

### Интеграция с X-UI
- **Автоматическое добавление клиентов** через API
- **Поддержка 3X-UI** панели
- **VLESS + TCP + Vision + Reality** протокол

### Реферальная система
- **+7 дней бонуса** рефереру при активации trial другом
- **Уникальные реферальные ссылки** для каждого пользователя

## Быстрый старт

### Требования
- Python 3.11+
- X-UI / 3X-UI панель
- VPS с nginx
- Telegram Bot Token

### Установка на сервере

```bash
# Клонируйте репозиторий
git clone https://github.com/ircitdev/pride-corpvpn-bot.git
cd pride-corpvpn-bot

# Создайте виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установите зависимости
pip install -r requirements.txt

# Настройте конфигурацию
cp config.example.py config.py
nano config.py

# Запустите бота
python bot.py
```

### Настройка systemd

```bash
sudo nano /etc/systemd/system/pride-vpn-bot.service
```

```ini
[Unit]
Description=Pride VPN Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/pride-vpn-bot
ExecStart=/opt/pride-vpn-bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable pride-vpn-bot
sudo systemctl start pride-vpn-bot
```

## Конфигурация

### Основные параметры (`config.py`)

```python
# Telegram Bot
TELEGRAM_BOT_TOKEN = "your_bot_token_here"

# Админы (получают уведомления о новых заявках)
ADMIN_IDS = [123456789]  # Telegram ID админов
ADMIN_USERNAMES = ["admin1", "admin2"]  # Username админов (без @)

# X-UI панель
XUI_URL = "https://vpn.example.com/panel"
XUI_LOGIN = "admin"
XUI_PASSWORD = "password"
XUI_INBOUND_ID = 1

# Subscription Aggregator
SUBSCRIPTION_AGGREGATOR_URL = "https://vpn.example.com/sub/"

# VPN сервер (Reality)
VPN_SERVERS = {
    "main": {
        "ip": "91.132.163.75",
        "port": 51191,
        "type": "tcp",
        "security": "reality",
        "flow": "xtls-rprx-vision",
        "sni": "ads.x5.ru",
        "fp": "chrome",
        "pbk": "your_public_key",
        "sid": "your_short_id",
        "name": "PRIDE-VPN"
    }
}
```

## Структура проекта

```
pride-corpvpn-bot/
├── bot.py                      # Главный файл бота
├── config.py                   # Конфигурация
├── requirements.txt            # Зависимости
├── hello.jpg                   # Приветственное изображение
│
├── handlers/                   # Обработчики команд
│   ├── menu.py                # Главное меню и /start
│   ├── access_request.py      # Система модерации заявок
│   ├── trial.py               # Trial-доступ
│   ├── admin.py               # Админ-панель
│   ├── payments.py            # Система оплаты
│   ├── partner.py             # Партнёрская программа
│   ├── check_vpn.py           # Проверка VPN
│   └── help.py                # Помощь
│
└── utils/                      # Утилиты
    ├── db.py                  # Работа с SQLite
    ├── xui_api.py             # Интеграция с X-UI
    ├── xui_client.py          # Клиент X-UI
    └── subscription.py        # Генерация ссылок
```

## Subscription Aggregator

Отдельный HTTP-сервер для генерации страниц подписок.

### Установка

```bash
# Создайте директорию
mkdir -p /opt/subscription-aggregator

# Скопируйте aggregator.py
cp aggregator.py /opt/subscription-aggregator/

# Создайте systemd сервис
sudo nano /etc/systemd/system/subscription-aggregator.service
```

```ini
[Unit]
Description=VPN Subscription Aggregator
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/subscription-aggregator
ExecStart=/usr/bin/python3 aggregator.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### Nginx конфигурация

```nginx
server {
    server_name vpn.example.com;

    location /panel/ {
        proxy_pass http://127.0.0.1:20851/panel/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /sub/ {
        proxy_pass http://127.0.0.1:2097/sub/;
        proxy_set_header Host $host;
        proxy_set_header Accept $http_accept;
        proxy_set_header User-Agent $http_user_agent;
    }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/vpn.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vpn.example.com/privkey.pem;
}
```

## Процесс получения доступа

1. Пользователь нажимает `/start` в боте
2. Видит приветствие и кнопку "Запросить доступ"
3. Пишет комментарий (кто он, зачем VPN)
4. Заявка отправляется всем админам
5. Админ нажимает "Подтвердить" или "Отказать"
6. При подтверждении:
   - Создаётся клиент в X-UI с уникальным UUID
   - Добавляется запись в subscription aggregator
   - Пользователь получает ссылку на подписку
7. Пользователь открывает ссылку, сканирует QR-код в v2rayNG/Happ

## База данных

SQLite база `vpn_users.db` содержит таблицы:

- `users` - пользователи бота
- `access_requests` - заявки на доступ (pending/approved/rejected)
- `referral_usage` - использование реферальных ссылок

## Команды

### Для пользователей
- `/start` - Запуск бота
- `/help` - Помощь

### Для администраторов
- `/stats` - Статистика
- `/adminhelp` - Список админ-команд

## Безопасность

- Пароли X-UI хранятся в bcrypt хеше
- API-запросы через HTTPS
- Валидация всех входных данных
- Логирование всех операций

## Мониторинг

```bash
# Статус бота
systemctl status pride-vpn-bot

# Логи бота
journalctl -u pride-vpn-bot -f

# Статус aggregator
systemctl status subscription-aggregator

# Логи X-UI
journalctl -u x-ui -f
```

## Лицензия

MIT License - см. файл [LICENSE](LICENSE)

## Автор

**ircitdev**
- GitHub: [@ircitdev](https://github.com/ircitdev)
- Telegram: [@uspeshnyy](https://t.me/uspeshnyy)
