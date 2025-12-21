"""
CryptoBot (Crypto Pay API) integration
Documentation: https://help.crypt.bot/crypto-pay-api
"""
import logging
from aiocryptopay import AioCryptoPay, Networks
from config import CRYPTOBOT_TOKEN, CRYPTOBOT_CURRENCY

logger = logging.getLogger(__name__)


async def create_invoice(amount: float, description: str, user_id: int, payload: str = None):
    """
    Создаёт инвойс в CryptoBot

    Args:
        amount: Сумма в рублях (будет конвертирована)
        description: Описание платежа
        user_id: Telegram ID пользователя (для проверки оплаты)
        payload: Дополнительные данные (например, payment_id)

    Returns:
        dict: {'invoice_id': str, 'bot_invoice_url': str, 'mini_app_invoice_url': str, 'web_app_invoice_url': str}
    """
    try:
        crypto = AioCryptoPay(token=CRYPTOBOT_TOKEN, network=Networks.MAIN_NET)

        # Конвертируем рубли в USDT (примерный курс, можно получить из API)
        # Для точности можно использовать API курсов валют
        usdt_amount = round(amount / 100, 2)  # Примерный курс 100 RUB = 1 USDT

        # Создаём инвойс
        invoice = await crypto.create_invoice(
            asset=CRYPTOBOT_CURRENCY,
            amount=usdt_amount,
            description=description,
            paid_btn_name="callback",  # Кнопка "Назад в бота" после оплаты
            paid_btn_url=f"https://t.me/YourBotUsername",  # TODO: заменить на реальное имя бота
            payload=payload or "",
            allow_comments=False,
            allow_anonymous=False
        )

        await crypto.close()

        logger.info(f"[CRYPTOBOT] Создан инвойс #{invoice.invoice_id} на {usdt_amount} {CRYPTOBOT_CURRENCY}")

        return {
            'invoice_id': invoice.invoice_id,
            'bot_invoice_url': invoice.bot_invoice_url,
            'mini_app_invoice_url': invoice.mini_app_invoice_url,
            'web_app_invoice_url': invoice.web_app_invoice_url,
            'amount': usdt_amount,
            'currency': CRYPTOBOT_CURRENCY
        }

    except Exception as e:
        logger.error(f"[CRYPTOBOT] Ошибка создания инвойса: {e}")
        raise


async def check_invoice_status(invoice_id: int):
    """
    Проверяет статус инвойса

    Args:
        invoice_id: ID инвойса

    Returns:
        dict: {'status': str, 'paid': bool, 'amount': float}
    """
    try:
        crypto = AioCryptoPay(token=CRYPTOBOT_TOKEN, network=Networks.MAIN_NET)

        # Получаем информацию об инвойсе
        invoices = await crypto.get_invoices(invoice_ids=[invoice_id])

        await crypto.close()

        if not invoices:
            return {'status': 'not_found', 'paid': False, 'amount': 0}

        invoice = invoices[0]

        logger.info(f"[CRYPTOBOT] Статус инвойса #{invoice_id}: {invoice.status}")

        return {
            'status': invoice.status,
            'paid': invoice.status == 'paid',
            'amount': invoice.amount,
            'currency': invoice.asset,
            'payload': invoice.payload
        }

    except Exception as e:
        logger.error(f"[CRYPTOBOT] Ошибка проверки статуса инвойса: {e}")
        raise


async def get_exchange_rates():
    """
    Получает курсы валют от CryptoBot

    Returns:
        dict: Курсы валют
    """
    try:
        crypto = AioCryptoPay(token=CRYPTOBOT_TOKEN, network=Networks.MAIN_NET)

        rates = await crypto.get_exchange_rates()

        await crypto.close()

        return rates

    except Exception as e:
        logger.error(f"[CRYPTOBOT] Ошибка получения курсов: {e}")
        return {}
