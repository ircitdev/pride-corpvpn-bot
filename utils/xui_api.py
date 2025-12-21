import requests
import json
import datetime
import uuid
from config import (
    XUI_URL,
    XUI_LOGIN,
    XUI_PASSWORD,
    XUI_INBOUND_ID,
    DOMAIN,
    WS_PATH,
    TRIAL_DAYS,
)

def _login_session():
    """Авторизация в X-UI и возврат сессии с cookie"""
    s = requests.Session()
    r = s.post(f"{XUI_URL}/login", data={"username": XUI_LOGIN, "password": XUI_PASSWORD})
    if r.status_code != 200 or '"success":true' not in r.text:
        raise Exception(f"[XUI] ❌ Ошибка авторизации: {r.text}")
    print("[XUI] ✅ Авторизация успешна")
    return s

def _gen_uuid():
    return str(uuid.uuid4())

def _detect_api_base(s):
    """Автоматически определяем рабочий базовый путь API"""
    candidates = [
        "/xui/inbound/list",
        "/panel/api/inbounds/list",
        "/api/inbounds/list",
        "/xui/api/inbounds/list",
        "/api/xui/inbounds/list",
    ]
    for path in candidates:
        try:
            r = s.post(f"{XUI_URL}{path}", timeout=5)
            print(f"[XUI] 🔍 Проверяем {path} → {r.status_code}")
            if r.status_code == 200 and "obj" in r.text:
                print(f"[XUI] ✅ Найден рабочий API: {path}")
                return path.rsplit("/", 2)[0]
        except Exception as e:
            print(f"[XUI] ⚠️ {path} → {e}")
    raise Exception("[XUI] ❌ Не удалось определить API путь X-UI")

def create_trial_client():
    """Создать тестового клиента через addClient"""
    s = _login_session()
    api_base = _detect_api_base(s)

    expiry_ts = int((datetime.datetime.utcnow() + datetime.timedelta(days=TRIAL_DAYS)).timestamp() * 1000)
    client_uuid = _gen_uuid()

    payload = {
        "id": XUI_INBOUND_ID,
        "settings": json.dumps({
            "clients": [
                {
                    "id": client_uuid,
                    "email": f"trial-{client_uuid[:6]}",
                    "limitIp": 0,
                    "totalGB": 0,
                    "expiryTime": expiry_ts
                }
            ]
        })
    }

    # пробуем сначала старый /update, потом новый /addClient
    candidates = [
        f"{XUI_URL}{api_base}/update/{XUI_INBOUND_ID}",
        f"{XUI_URL}{api_base}/addClient",
        f"{XUI_URL}/xui/inbound/addClient",
        f"{XUI_URL}/panel/api/inbounds/addClient",
        f"{XUI_URL}/api/xui/inbounds/addClient",
    ]

    success = False
    for url in candidates:
        try:
            r = s.post(url, data=payload)
            print(f"[XUI] 🔧 POST {url} → {r.status_code}")
            if '"success":true' in r.text or '"msg":"success"' in r.text:
                print(f"[XUI] ✅ Клиент добавлен через {url}")
                success = True
                break
        except Exception as e:
            print(f"[XUI] ⚠️ Ошибка запроса {url}: {e}")

    if not success:
        raise Exception(f"[XUI] ❌ Ошибка при добавлении клиента: {r.text}")

    vless_link = (
        f"vless://{client_uuid}@{DOMAIN}:443"
        f"?type=ws&security=tls&path={WS_PATH}&encryption=none"
        f"#UspeshnyyVPN-{client_uuid[:6]}"
    )
    print(f"[XUI] 🎁 Trial client создан: {vless_link}")
    return vless_link, expiry_ts
import requests
from config import XUI_URL, XUI_LOGIN, XUI_PASSWORD
from loguru import logger

def check_xui_connection() -> bool:
    """
    Проверяет, отвечает ли X-UI API.
    Возвращает True, если запрос к /xui/api/inbounds/list возвращает 200.
    """
    try:
        urls_to_try = [
            f"{XUI_URL}/xui/api/inbounds/list",
            f"{XUI_URL}/panel/api/inbounds/list",
            f"{XUI_URL}/api/inbounds/list",
        ]
        for url in urls_to_try:
            r = requests.get(url, verify=False, timeout=5)
            logger.info(f"[XUI] Проверка {url} → {r.status_code}")
            if r.status_code == 200:
                return True
        return False
    except Exception as e:
        logger.error(f"[XUI] Ошибка соединения: {e}")
        return False

def extend_client_days(self, remark: str, days: int = 7):
    # пока только логируем — потом допилишь реальный запрос в /panel/api/inbounds/updateClient
    logging.info(f"[XUI] (stub) продлить клиента {remark} на {days} дней")


def create_or_extend_subscription(user_id: int, months: int, traffic_gb: int):
    """
    Создаёт или продлевает платную подписку для пользователя

    Args:
        user_id: Telegram ID пользователя
        months: Количество месяцев подписки
        traffic_gb: Лимит трафика в GB

    Returns:
        tuple: (client_uuid, vless_link, expiry_timestamp, traffic_bytes)
    """
    import utils.db as db

    s = _login_session()
    api_base = _detect_api_base(s)

    # Проверяем, есть ли уже активная подписка
    existing_subscription = db.get_active_subscription(user_id)

    if existing_subscription:
        # Продлеваем существующую подписку
        client_uuid = existing_subscription['client_id']
        current_expiry = existing_subscription['expires_at']

        # Если подписка ещё активна, продлеваем от текущей даты истечения
        # Если истекла, продлеваем от текущего момента
        import time
        base_time = max(current_expiry, time.time())
        expiry_ts = int((datetime.datetime.fromtimestamp(base_time) +
                        datetime.timedelta(days=months * 30)).timestamp() * 1000)

        # Добавляем трафик
        current_traffic = existing_subscription.get('traffic_limit_bytes', 0)
        new_traffic_bytes = current_traffic + (traffic_gb * 1024 * 1024 * 1024)

        print(f"[XUI] 🔄 Продление подписки для {user_id}: +{months} мес, +{traffic_gb} GB")

    else:
        # Создаём новую подписку
        client_uuid = _gen_uuid()
        expiry_ts = int((datetime.datetime.utcnow() +
                        datetime.timedelta(days=months * 30)).timestamp() * 1000)
        new_traffic_bytes = traffic_gb * 1024 * 1024 * 1024

        print(f"[XUI] 🆕 Создание новой подписки для {user_id}: {months} мес, {traffic_gb} GB")

    # Обновляем клиента в X-UI
    payload = {
        "id": XUI_INBOUND_ID,
        "settings": json.dumps({
            "clients": [
                {
                    "id": client_uuid,
                    "email": f"user-{user_id}",
                    "limitIp": 0,
                    "totalGB": new_traffic_bytes,
                    "expiryTime": expiry_ts
                }
            ]
        })
    }

    # Пробуем разные endpoints для добавления/обновления клиента
    if existing_subscription:
        candidates = [
            f"{XUI_URL}{api_base}/updateClient/{client_uuid}",
            f"{XUI_URL}/xui/inbound/updateClient",
            f"{XUI_URL}/panel/api/inbounds/updateClient",
        ]
    else:
        candidates = [
            f"{XUI_URL}{api_base}/addClient",
            f"{XUI_URL}/xui/inbound/addClient",
            f"{XUI_URL}/panel/api/inbounds/addClient",
            f"{XUI_URL}/api/xui/inbounds/addClient",
        ]

    success = False
    for url in candidates:
        try:
            r = s.post(url, data=payload)
            print(f"[XUI] 🔧 POST {url} → {r.status_code}")
            if '"success":true' in r.text or '"msg":"success"' in r.text:
                print(f"[XUI] ✅ Клиент {'обновлён' if existing_subscription else 'создан'} через {url}")
                success = True
                break
        except Exception as e:
            print(f"[XUI] ⚠️ Ошибка запроса {url}: {e}")

    if not success:
        raise Exception(f"[XUI] ❌ Ошибка при {'обновлении' if existing_subscription else 'создании'} клиента: {r.text}")

    # Генерируем VLESS-ссылку
    vless_link = (
        f"vless://{client_uuid}@{DOMAIN}:443"
        f"?type=ws&security=tls&path={WS_PATH}&encryption=none"
        f"#UspeshnyyVPN-user{user_id}"
    )

    print(f"[XUI] ✅ Подписка активирована: {vless_link}")

    return client_uuid, vless_link, expiry_ts // 1000, new_traffic_bytes