"""
YooKassa (ЮKassa) payment integration
Documentation: https://yookassa.ru/developers/api
"""
import logging
import uuid
from yookassa import Configuration, Payment
from config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY

logger = logging.getLogger(__name__)

# Настройка конфигурации YooKassa
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY


def create_payment(amount: float, description: str, return_url: str = None, metadata: dict = None):
    """
    Создаёт платеж в YooKassa

    Args:
        amount: Сумма в рублях
        description: Описание платежа
        return_url: URL для возврата после оплаты
        metadata: Дополнительные данные (например, payment_id, user_id)

    Returns:
        dict: {'payment_id': str, 'confirmation_url': str, 'status': str}
    """
    try:
        # Генерируем уникальный ключ идемпотентности
        idempotence_key = str(uuid.uuid4())

        # Создаём платеж
        payment = Payment.create({
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url or "https://t.me/YourBotUsername"  # TODO: заменить на реальное имя бота
            },
            "capture": True,  # Автоматическое подтверждение платежа
            "description": description,
            "metadata": metadata or {}
        }, idempotence_key)

        logger.info(f"[YOOKASSA] Создан платеж {payment.id} на {amount}₽")

        return {
            'payment_id': payment.id,
            'confirmation_url': payment.confirmation.confirmation_url,
            'status': payment.status,
            'amount': amount
        }

    except Exception as e:
        logger.error(f"[YOOKASSA] Ошибка создания платежа: {e}")
        raise


def check_payment_status(payment_id: str):
    """
    Проверяет статус платежа

    Args:
        payment_id: ID платежа в YooKassa

    Returns:
        dict: {'status': str, 'paid': bool, 'amount': float}
    """
    try:
        payment = Payment.find_one(payment_id)

        logger.info(f"[YOOKASSA] Статус платежа {payment_id}: {payment.status}")

        return {
            'status': payment.status,
            'paid': payment.status == 'succeeded',
            'amount': float(payment.amount.value),
            'currency': payment.amount.currency,
            'metadata': payment.metadata
        }

    except Exception as e:
        logger.error(f"[YOOKASSA] Ошибка проверки статуса платежа: {e}")
        raise


def cancel_payment(payment_id: str):
    """
    Отменяет платеж

    Args:
        payment_id: ID платежа в YooKassa

    Returns:
        bool: True если успешно отменён
    """
    try:
        payment = Payment.cancel(payment_id, str(uuid.uuid4()))

        logger.info(f"[YOOKASSA] Платеж {payment_id} отменён")

        return payment.status == 'canceled'

    except Exception as e:
        logger.error(f"[YOOKASSA] Ошибка отмены платежа: {e}")
        return False
