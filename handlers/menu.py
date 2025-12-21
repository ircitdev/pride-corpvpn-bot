# handlers/menu.py
import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)

from utils.db import get_approved_request_by_user
from config import SUBSCRIPTION_AGGREGATOR_URL

logger = logging.getLogger(__name__)
router = Router()


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔐 Запросить доступ")],
        ],
        resize_keyboard=True
    )


@router.message(CommandStart())
async def start_command(message: Message):
    """
    Приветствие при старте — с фото hello.jpg и кнопкой "Запросить доступ".
    """
    user_id = message.from_user.id
    username = message.from_user.username or ""

    logger.info(f"[START] Пользователь @{username} ({user_id}) запустил бота.")

    # Проверяем, есть ли уже доступ
    approved = get_approved_request_by_user(user_id)

    if approved:
        # У пользователя уже есть доступ
        sub_id = approved.get('sub_id', f'user_{user_id}')
        sub_url = f"{SUBSCRIPTION_AGGREGATOR_URL}{sub_id}"

        text = (
            "👋 <b>С возвращением!</b>\n\n"
            "У вас уже есть доступ к VPN.\n\n"
            "🔗 Ваша ссылка на подписку:\n"
            f"<code>{sub_url}</code>\n\n"
            "Откройте в браузере или добавьте в VPN-приложение."
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Открыть подписку", url=sub_url)],
            [
                InlineKeyboardButton(text="📱 Android", url="https://play.google.com/store/apps/details?id=com.happproxy"),
                InlineKeyboardButton(text="🍎 iOS", url="https://apps.apple.com/app/id6746188973")
            ],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
        ])
    else:
        # Новый пользователь
        text = (
            "👋 <b>Добро пожаловать в PRIDE VPN!</b>\n\n"
            "🔐 Корпоративный VPN для обхода блокировок\n"
            "📱 Работает на всех операторах\n"
            "⚡ Высокая скорость\n\n"
            "Для получения доступа нажмите кнопку ниже.\n"
            "Администратор рассмотрит вашу заявку."
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔐 Запросить доступ", callback_data="request_access")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
        ])

    try:
        await message.answer_photo(
            photo=FSInputFile("hello.jpg"),
            caption=text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.warning(f"[START] Ошибка при отправке hello.jpg: {e}")
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: types.CallbackQuery):
    """Возврат в главное меню"""
    user_id = callback.from_user.id

    # Проверяем, есть ли уже доступ
    approved = get_approved_request_by_user(user_id)

    if approved:
        sub_id = approved.get('sub_id', f'user_{user_id}')
        sub_url = f"{SUBSCRIPTION_AGGREGATOR_URL}{sub_id}"

        text = (
            "🏠 <b>Главное меню</b>\n\n"
            "🔗 Ваша подписка:\n"
            f"<code>{sub_url}</code>"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Открыть подписку", url=sub_url)],
            [
                InlineKeyboardButton(text="📱 Android", url="https://play.google.com/store/apps/details?id=com.happproxy"),
                InlineKeyboardButton(text="🍎 iOS", url="https://apps.apple.com/app/id6746188973")
            ],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
        ])
    else:
        text = (
            "🏠 <b>Главное меню</b>\n\n"
            "🔐 PRIDE VPN - корпоративный VPN\n\n"
            "Для получения доступа нажмите кнопку ниже."
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔐 Запросить доступ", callback_data="request_access")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
        ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "help")
async def help_handler(callback: types.CallbackQuery):
    """Показать помощь"""
    text = (
        "❓ <b>Помощь</b>\n\n"
        "<b>Как подключиться:</b>\n"
        "1. Запросите доступ через бота\n"
        "2. Дождитесь подтверждения от администратора\n"
        "3. Откройте полученную ссылку в браузере\n"
        "4. Отсканируйте QR-код в VPN-приложении\n\n"
        "<b>Приложения:</b>\n"
        "• Android: v2rayNG (Play Store)\n"
        "• iOS: Happ (App Store)\n"
        "• Windows: v2rayN (GitHub)\n\n"
        "<b>Поддержка:</b> @uspeshnyy"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📱 Android", url="https://play.google.com/store/apps/details?id=com.happproxy"),
            InlineKeyboardButton(text="🍎 iOS", url="https://apps.apple.com/app/id6746188973")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()
