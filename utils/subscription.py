"""
Утилиты для работы с подписками и генерации VPN-конфигов
"""
import uuid
import qrcode
from io import BytesIO
from config import VPN_SERVERS, SUBSCRIPTION_AGGREGATOR_URL


def generate_user_uuid() -> str:
    """Генерирует новый UUID для пользователя"""
    return str(uuid.uuid4())


def generate_vless_link(user_uuid: str, server_key: str = "mts") -> str:
    """
    Генерирует VLESS-ссылку для пользователя

    Args:
        user_uuid: UUID пользователя
        server_key: Ключ сервера из VPN_SERVERS (mts, wifi)

    Returns:
        str: VLESS-ссылка
    """
    server = VPN_SERVERS.get(server_key, VPN_SERVERS["mts"])

    params = [
        f"flow={server['flow']}",
        f"type={server['type']}",
        "headerType=none",
        f"security={server['security']}",
        f"fp={server['fp']}",
        f"sni={server['sni']}",
        f"pbk={server['pbk']}",
        f"sid={server['sid']}"
    ]

    return f"vless://{user_uuid}@{server['ip']}:{server['port']}?{'&'.join(params)}#{server['name']}"


def generate_all_vless_links(user_uuid: str) -> list:
    """
    Генерирует все VLESS-ссылки для всех серверов

    Args:
        user_uuid: UUID пользователя

    Returns:
        list: Список VLESS-ссылок
    """
    links = []
    for server_key in VPN_SERVERS.keys():
        links.append(generate_vless_link(user_uuid, server_key))
    return links


def get_subscription_url(sub_id: str) -> str:
    """
    Возвращает URL подписки для пользователя

    Args:
        sub_id: ID подписки пользователя

    Returns:
        str: URL подписки
    """
    return f"{SUBSCRIPTION_AGGREGATOR_URL}{sub_id}"


def generate_qr_code(data: str) -> BytesIO:
    """
    Генерирует QR-код из данных

    Args:
        data: Данные для кодирования (ссылка)

    Returns:
        BytesIO: QR-код как изображение в памяти
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    return buffer


def generate_subscription_qr(sub_id: str) -> BytesIO:
    """
    Генерирует QR-код для URL подписки

    Args:
        sub_id: ID подписки

    Returns:
        BytesIO: QR-код как изображение
    """
    url = get_subscription_url(sub_id)
    return generate_qr_code(url)


def generate_vless_qr(user_uuid: str, server_key: str = "mts") -> BytesIO:
    """
    Генерирует QR-код для VLESS-ссылки

    Args:
        user_uuid: UUID пользователя
        server_key: Ключ сервера

    Returns:
        BytesIO: QR-код как изображение
    """
    link = generate_vless_link(user_uuid, server_key)
    return generate_qr_code(link)
