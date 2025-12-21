import requests
import logging
import json
import time
import uuid

logger = logging.getLogger(__name__)


class XUIClient:
    """
    Универсальный клиент X-UI для работы с API разных версий.
    """

    def __init__(self):
        from config import XUI_URL, XUI_LOGIN, XUI_PASSWORD
        self.base_url = XUI_URL
        self.username = XUI_LOGIN
        self.password = XUI_PASSWORD
        self.session = requests.Session()
        self.session.verify = False
        self.api_prefix = None

    def login(self):
        """Авторизация в X-UI"""
        try:
            res = self.session.post(
                f"{self.base_url}/login",
                data={"username": self.username, "password": self.password},
                timeout=10,
            )
            if res.status_code == 200 and "success" in res.text.lower():
                logger.info("[XUI] Авторизация успешна")
                return True
            logger.error(f"[XUI] Ошибка авторизации ({res.status_code})")
            return False
        except Exception as e:
            logger.exception(f"[XUI] Ошибка авторизации: {e}")
            return False

    def detect_api(self):
        """Находит доступный API путь"""
        candidates = [
            "/panel/api/inbounds",
            "/xui/api/inbounds",
            "/xui/inbound",
            "/api/inbounds",
        ]
        for path in candidates:
            try:
                url = f"{self.base_url}{path}/list"
                res = self.session.post(url, timeout=10)
                if res.status_code == 200:
                    self.api_prefix = path
                    logger.info(f"[XUI] Найден рабочий API: {path}")
                    return path
            except Exception:
                pass

        logger.error("[XUI] Не удалось определить API-путь")
        self.api_prefix = "/panel/api/inbounds"
        return self.api_prefix

    def get_inbounds(self):
        """Возвращает список inbound-конфигураций"""
        try:
            url = f"{self.base_url}{self.api_prefix}/list"
            res = self.session.post(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                return data.get("obj", [])
            return []
        except Exception as e:
            logger.exception(f"[XUI] Ошибка получения inbound list: {e}")
            return []

    def create_trial_client(self, remark, ttl_seconds=None, traffic_bytes=None, return_full=False):
        """
        Создает trial-клиента в XUI.
        """
        from config import XUI_INBOUND_ID, VPN_SERVERS

        client_uuid = str(uuid.uuid4())
        traffic_limit = traffic_bytes or (15 * 1024 * 1024 * 1024)  # 15 GB
        expire_time = int((time.time() + (ttl_seconds or 3 * 24 * 3600)) * 1000)  # в миллисекундах

        # Формируем клиента
        client_data = {
            "id": client_uuid,
            "flow": "xtls-rprx-vision",
            "email": f"trial_{remark}@pride34.ru",
            "limitIp": 2,
            "totalGB": traffic_limit,
            "expiryTime": expire_time,
            "enable": True,
            "tgId": str(remark),
            "subId": f"trial_{remark}"
        }

        payload = {
            "id": XUI_INBOUND_ID,
            "settings": json.dumps({"clients": [client_data]})
        }

        # Пробуем разные endpoints
        endpoints = [
            f"{self.base_url}{self.api_prefix}/addClient",
            f"{self.base_url}/panel/api/inbounds/addClient",
            f"{self.base_url}/xui/inbound/addClient",
        ]

        success = False
        for url in endpoints:
            try:
                res = self.session.post(url, data=payload, timeout=10)
                logger.info(f"[XUI] POST {url} -> {res.status_code}")
                if res.status_code == 200 and "success" in res.text.lower():
                    logger.info(f"[XUI] Клиент создан через {url}")
                    success = True
                    break
            except Exception as e:
                logger.warning(f"[XUI] Ошибка запроса {url}: {e}")

        if not success:
            logger.error("[XUI] Не удалось создать клиента")
            return None

        # Генерируем VLESS-ссылку с использованием нашего сервера
        server = VPN_SERVERS.get("mts", {})
        vless_link = (
            f"vless://{client_uuid}@{server.get('ip', '178.154.227.64')}:{server.get('port', 8443)}"
            f"?flow={server.get('flow', 'xtls-rprx-vision')}"
            f"&type={server.get('type', 'tcp')}"
            f"&headerType=none"
            f"&security={server.get('security', 'reality')}"
            f"&fp={server.get('fp', 'qq')}"
            f"&sni={server.get('sni', 'o-gate.perekrestok.ru')}"
            f"&pbk={server.get('pbk', '')}"
            f"&sid={server.get('sid', '')}"
            f"#PrideVPN-{remark}"
        )

        if return_full:
            return {
                "client_id": client_uuid,
                "link": vless_link,
                "expiry": expire_time,
                "traffic": traffic_limit
            }
        return vless_link
