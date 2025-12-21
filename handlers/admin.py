"""
Административные команды для управления ботом
"""
import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message
import utils.db as db
from config import ADMIN_ID
import time

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id == ADMIN_ID


# ========== УПРАВЛЕНИЕ ПРОМОКОДАМИ ==========

@router.message(Command("addpromo"))
async def add_promocode(message: Message):
    """
    Создать промокод
    Формат: /addpromo КОД СКИДКА_% МАКС_ИСПОЛЬЗОВАНИЙ СРОК_ДНЕЙ
    Пример: /addpromo SUMMER25 25 100 30
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
        args = message.text.split()
        if len(args) < 3:
            await message.answer(
                "ℹ️ <b>Формат команды:</b>\n\n"
                "/addpromo КОД СКИДКА_% [МАКС_ИСПОЛЬЗОВАНИЙ] [СРОК_ДНЕЙ]\n\n"
                "<b>Примеры:</b>\n"
                "/addpromo SUMMER25 25 100 30\n"
                "/addpromo VIP50 50 10 7\n"
                "/addpromo FOREVER10 10 -1 -1\n\n"
                "<b>Параметры:</b>\n"
                "• КОД - название промокода (заглавными буквами)\n"
                "• СКИДКА_% - процент скидки (0-100)\n"
                "• МАКС_ИСПОЛЬЗОВАНИЙ - макс. кол-во использований (-1 = безлимит)\n"
                "• СРОК_ДНЕЙ - срок действия в днях (-1 = бессрочно)",
                parse_mode="HTML"
            )
            return

        code = args[1].upper()
        discount_percent = int(args[2])

        # Опциональные параметры
        max_uses = int(args[3]) if len(args) > 3 else -1
        days_valid = int(args[4]) if len(args) > 4 else -1

        # Вычисляем срок действия
        expires_at = None
        if days_valid > 0:
            expires_at = time.time() + (days_valid * 24 * 60 * 60)

        # Создаём промокод
        db.create_promocode(
            code=code,
            discount_percent=discount_percent,
            max_uses=max_uses,
            expires_at=expires_at
        )

        # Формируем сообщение
        expires_text = f"{days_valid} дней" if days_valid > 0 else "бессрочно"
        uses_text = f"{max_uses} раз" if max_uses > 0 else "безлимит"

        await message.answer(
            f"✅ <b>Промокод создан!</b>\n\n"
            f"🎟️ Код: <code>{code}</code>\n"
            f"💰 Скидка: {discount_percent}%\n"
            f"📊 Макс. использований: {uses_text}\n"
            f"⏰ Срок действия: {expires_text}",
            parse_mode="HTML"
        )

        logger.info(f"[ADMIN] Промокод {code} создан администратором {message.from_user.id}")

    except ValueError:
        await message.answer("❌ Ошибка: проверьте формат команды. Числа должны быть целыми.")
    except Exception as e:
        logger.error(f"[ADMIN] Ошибка создания промокода: {e}")
        await message.answer(f"❌ Ошибка создания промокода: {str(e)}")


@router.message(Command("listpromos"))
async def list_promocodes(message: Message):
    """Показать все промокоды"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
        promos = db.get_all_promocodes()

        if not promos:
            await message.answer("📋 Промокодов пока нет.")
            return

        text = "📋 <b>Список промокодов:</b>\n\n"

        for promo in promos:
            status = "✅ Активен" if promo['active'] else "❌ Неактивен"
            expires = "бессрочно" if not promo.get('expires_at') else f"до {time.strftime('%d.%m.%Y', time.localtime(promo['expires_at']))}"
            uses = f"{promo['used_count']}/{promo['max_uses']}" if promo['max_uses'] > 0 else f"{promo['used_count']}/∞"

            text += (
                f"🎟️ <code>{promo['code']}</code> - {promo['discount_percent']}%\n"
                f"   {status} | {uses} использований | {expires}\n\n"
            )

        await message.answer(text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"[ADMIN] Ошибка получения списка промокодов: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(Command("delpromo"))
async def delete_promocode(message: Message):
    """
    Удалить промокод
    Формат: /delpromo КОД
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer("ℹ️ Формат: /delpromo КОД\nПример: /delpromo SUMMER25")
            return

        code = args[1].upper()

        # Деактивируем промокод
        db.deactivate_promocode(code)

        await message.answer(
            f"✅ Промокод <code>{code}</code> деактивирован.",
            parse_mode="HTML"
        )

        logger.info(f"[ADMIN] Промокод {code} деактивирован администратором {message.from_user.id}")

    except Exception as e:
        logger.error(f"[ADMIN] Ошибка деактивации промокода: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


# ========== УПРАВЛЕНИЕ БАЛАНСОМ ==========

@router.message(Command("addbalance"))
async def add_user_balance(message: Message):
    """
    Добавить баланс пользователю
    Формат: /addbalance USER_ID СУММА [ОПИСАНИЕ]
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
        args = message.text.split(maxsplit=3)
        if len(args) < 3:
            await message.answer(
                "ℹ️ Формат: /addbalance USER_ID СУММА [ОПИСАНИЕ]\n"
                "Пример: /addbalance 123456789 500 Подарок от администрации"
            )
            return

        user_id = int(args[1])
        amount = float(args[2])
        description = args[3] if len(args) > 3 else "Начисление от администратора"

        # Добавляем баланс
        db.add_balance(user_id, amount, "admin", description)

        # Получаем новый баланс
        new_balance = db.get_user_balance(user_id)

        await message.answer(
            f"✅ Пользователю <code>{user_id}</code> начислено <b>{amount:.2f}₽</b>\n"
            f"Новый баланс: <b>{new_balance:.2f}₽</b>",
            parse_mode="HTML"
        )

        logger.info(f"[ADMIN] Баланс {amount}₽ добавлен пользователю {user_id} администратором {message.from_user.id}")

    except ValueError:
        await message.answer("❌ Ошибка: проверьте формат команды. USER_ID и СУММА должны быть числами.")
    except Exception as e:
        logger.error(f"[ADMIN] Ошибка добавления баланса: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


# ========== СТАТИСТИКА ==========

@router.message(Command("stats"))
async def show_statistics(message: Message):
    """Показать статистику бота"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
        stats = db.get_statistics()

        text = (
            "📊 <b>Статистика бота</b>\n\n"
            f"👥 Всего пользователей: {stats.get('total_users', 0)}\n"
            f"💳 Всего платежей: {stats.get('total_payments', 0)}\n"
            f"💰 Сумма платежей: {stats.get('total_revenue', 0):.2f}₽\n"
            f"✅ Успешных платежей: {stats.get('completed_payments', 0)}\n"
            f"⏳ В ожидании: {stats.get('pending_payments', 0)}\n\n"
            f"📊 Активных подписок: {stats.get('active_subscriptions', 0)}\n"
            f"🔗 Реферальных связей: {stats.get('total_referrals', 0)}"
        )

        await message.answer(text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"[ADMIN] Ошибка получения статистики: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(Command("adminhelp"))
async def admin_help(message: Message):
    """Показать список админских команд"""
    if not is_admin(message.from_user.id):
        return

    text = (
        "🔧 <b>Административные команды</b>\n\n"
        "<b>Промокоды:</b>\n"
        "/addpromo КОД СКИДКА% [МАКС] [ДНЕЙ] - Создать промокод\n"
        "/listpromos - Список всех промокодов\n"
        "/delpromo КОД - Деактивировать промокод\n\n"
        "<b>Баланс:</b>\n"
        "/addbalance USER_ID СУММА [ОПИСАНИЕ] - Начислить баланс\n\n"
        "<b>Статистика:</b>\n"
        "/stats - Статистика бота"
    )

    await message.answer(text, parse_mode="HTML")
