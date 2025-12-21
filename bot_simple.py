"""
Pride VPN Bot - Простая версия для выдачи подписок с QR-кодами
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile
)
import uuid

from config import TELEGRAM_BOT_TOKEN, ADMIN_ID, VPN_SERVERS, SUBSCRIPTION_AGGREGATOR_URL
from utils.subscription import (
    generate_vless_link,
    generate_vless_qr,
    get_subscription_url,
    generate_subscription_qr
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
router = Router()


def generate_user_sub_id(user_id: int) -> str:
    """Генерирует ID подписки для пользователя"""
    return f"user_{user_id}"


def get_user_uuid(user_id: int) -> str:
    """Возвращает или генерирует UUID для пользователя"""
    # В реальном приложении это хранится в БД
    # Пока используем детерминистичный UUID на основе user_id
    import hashlib
    hash_input = f"pride_vpn_{user_id}".encode()
    hash_hex = hashlib.md5(hash_input).hexdigest()
    return f"{hash_hex[:8]}-{hash_hex[8:12]}-{hash_hex[12:16]}-{hash_hex[16:20]}-{hash_hex[20:32]}"


@router.message(CommandStart())
async def start_command(message: Message):
    """Приветствие при старте"""
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"

    logger.info(f"[START] User @{username} ({user_id}) started bot")

    text = (
        "👋 <b>Добро пожаловать в Pride VPN!</b>\n\n"
        "🔐 Безлимитный VPN для обхода блокировок\n"
        "📱 Работает на всех операторах\n"
        "⚡ Высокая скорость\n\n"
        "Нажмите кнопку ниже чтобы получить доступ:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Получить VPN", callback_data="get_vpn")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])

    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "get_vpn")
async def get_vpn_handler(callback: CallbackQuery):
    """Выдача VPN конфигов"""
    user_id = callback.from_user.id
    user_uuid = get_user_uuid(user_id)

    # Генерируем ссылки для обоих серверов
    mts_link = generate_vless_link(user_uuid, "mts")
    wifi_link = generate_vless_link(user_uuid, "wifi")

    text = (
        "✅ <b>Ваш VPN доступ готов!</b>\n\n"
        "📱 <b>Для МТС/LTE</b> (обход блокировок):\n"
        f"<code>{mts_link}</code>\n\n"
        "📶 <b>Для WiFi</b>:\n"
        f"<code>{wifi_link}</code>\n\n"
        "👆 Нажмите на ссылку чтобы скопировать\n\n"
        "Или используйте QR-коды:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📱 QR МТС/LTE", callback_data=f"qr_mts:{user_uuid}"),
            InlineKeyboardButton(text="📶 QR WiFi", callback_data=f"qr_wifi:{user_uuid}")
        ],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="instruction")],
        [
            InlineKeyboardButton(text="📱 Android", url="https://play.google.com/store/apps/details?id=com.happproxy"),
            InlineKeyboardButton(text="🍎 iOS", url="https://apps.apple.com/app/happ/id6504287215")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("qr_mts:"))
async def qr_mts_handler(callback: CallbackQuery):
    """QR-код для МТС"""
    try:
        user_uuid = callback.data.split(":")[1]
        qr_buffer = generate_vless_qr(user_uuid, "mts")
        link = generate_vless_link(user_uuid, "mts")

        await callback.message.answer_photo(
            photo=BufferedInputFile(qr_buffer.read(), filename="mts_qr.png"),
            caption=f"📱 <b>QR-код для МТС/LTE</b>\n\nОтсканируйте в приложении VPN\n\n<code>{link}</code>"
        )
        await callback.answer()
    except Exception as e:
        logger.exception(f"QR MTS error: {e}")
        await callback.answer("Ошибка генерации QR", show_alert=True)


@router.callback_query(F.data.startswith("qr_wifi:"))
async def qr_wifi_handler(callback: CallbackQuery):
    """QR-код для WiFi"""
    try:
        user_uuid = callback.data.split(":")[1]
        qr_buffer = generate_vless_qr(user_uuid, "wifi")
        link = generate_vless_link(user_uuid, "wifi")

        await callback.message.answer_photo(
            photo=BufferedInputFile(qr_buffer.read(), filename="wifi_qr.png"),
            caption=f"📶 <b>QR-код для WiFi</b>\n\nОтсканируйте в приложении VPN\n\n<code>{link}</code>"
        )
        await callback.answer()
    except Exception as e:
        logger.exception(f"QR WiFi error: {e}")
        await callback.answer("Ошибка генерации QR", show_alert=True)


@router.callback_query(F.data == "instruction")
async def instruction_handler(callback: CallbackQuery):
    """Инструкция по настройке"""
    text = (
        "📖 <b>Инструкция по настройке VPN</b>\n\n"
        "<b>Для Android:</b>\n"
        "1. Установите v2rayNG из Play Store\n"
        "2. Нажмите + → Импорт из буфера\n"
        "3. Вставьте скопированную ссылку\n"
        "4. Нажмите на конфиг → Подключить\n\n"
        "<b>Для iOS:</b>\n"
        "1. Установите Happ из App Store\n"
        "2. Добавить сервер → Импорт из буфера\n"
        "3. Вставьте ссылку и подключитесь\n\n"
        "<b>Для Windows:</b>\n"
        "1. Скачайте v2rayN с GitHub\n"
        "2. Серверы → Импорт из буфера\n"
        "3. Выберите сервер и подключитесь"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="get_vpn")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "help")
async def help_handler(callback: CallbackQuery):
    """Помощь"""
    text = (
        "❓ <b>Помощь</b>\n\n"
        "🔐 <b>Pride VPN</b> - сервис для обхода блокировок\n\n"
        "📱 <b>МТС/LTE конфиг</b> - используйте на мобильном интернете\n"
        "📶 <b>WiFi конфиг</b> - используйте на домашнем WiFi\n\n"
        "💬 Поддержка: @uspeshnyy"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: CallbackQuery):
    """Возврат в главное меню"""
    text = (
        "👋 <b>Pride VPN</b>\n\n"
        "🔐 Безлимитный VPN для обхода блокировок\n"
        "📱 Работает на всех операторах\n"
        "⚡ Высокая скорость\n\n"
        "Нажмите кнопку ниже чтобы получить доступ:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Получить VPN", callback_data="get_vpn")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(Command("id"))
async def id_command(message: Message):
    """Показать ID пользователя"""
    await message.answer(f"Ваш Telegram ID: <code>{message.from_user.id}</code>")


dp.include_router(router)


async def main():
    me = await bot.get_me()
    logger.info(f"🚀 Bot started as @{me.username}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
