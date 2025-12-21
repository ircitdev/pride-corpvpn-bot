# handlers/trial.py
import logging
import time
import datetime
from typing import Optional, Dict, Any

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    CallbackQuery,
    FSInputFile,
    BufferedInputFile
)

from utils.xui_client import XUIClient
from utils.db import ensure_user_row  # обязательная функция
from utils.subscription import (
    generate_user_uuid,
    generate_vless_link,
    generate_all_vless_links,
    get_subscription_url,
    generate_subscription_qr,
    generate_vless_qr
)
import config

logger = logging.getLogger(__name__)
router = Router()

# Константы trial
TRIAL_DAYS_DEFAULT = 3
TRIAL_TRAFFIC_GB = 15
REFERRAL_BONUS_DAYS = 7


# helper: безопасно вызвать функцию в utils.db, если есть
def call_db_func(name: str, *args, **kwargs):
    try:
        import utils.db as _db
        func = getattr(_db, name, None)
        if callable(func):
            return func(*args, **kwargs)
        else:
            logger.debug("[DB] Функция %s не найдена в utils.db", name)
            return None
    except Exception as e:
        logger.exception("[DB] Ошибка при вызове %s: %s", name, e)
        return None


def clean_text(text: str) -> str:
    """Удаление потенциально опасных markdown-символов для вывода в Telegram."""
    if not text:
        return ""
    return text.replace("*", "").replace("_", "").replace("`", "")


@router.message(F.text.in_(["🎁 Получить тест-доступ", "🚀 Доступ на 3 дня бесплатно", "/trial"]))
async def get_trial(message: types.Message):
    tg_id: int = message.from_user.id
    username: str = message.from_user.username or f"user_{tg_id}"
    full_name: str = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()

    logger.info(f"[TRIAL] Пользователь @{username} ({tg_id}) запросил trial-доступ")

    # 1) ensure user in DB
    try:
        ensure_user_row(tg_id, username, full_name)
    except Exception:
        logger.exception("[TRIAL] ensure_user_row упала")

    # 2) информируем пользователя
    await message.answer("🕓 Создаю ваш тестовый VPN-доступ... Это займёт несколько секунд.")

    # 3) логика создания trial через XUI
    try:
        xui = XUIClient()
        if not xui.login():
            await message.answer("❌ Не удалось авторизоваться в панели XUI.")
            return

        xui.detect_api()

        ttl_seconds = TRIAL_DAYS_DEFAULT * 24 * 3600
        traffic_bytes = TRIAL_TRAFFIC_GB * 1024 * 1024 * 1024

        create_fn = getattr(xui, "create_trial_client", None)
        if not create_fn:
            await message.answer("❌ Метод create_trial_client не найден в XUIClient.")
            return

        # Пробуем вызвать метод
        try:
            result = create_fn(str(tg_id), ttl_seconds, traffic_bytes, return_full=True)
            if getattr(result, "__await__", None):
                result = await result
        except TypeError:
            result = create_fn(str(tg_id))

        if not result:
            await message.answer("⚠️ Ошибка при создании trial-доступа. Панель не ответила корректно.")
            return

        # Парсим ответ
        # если панель вернула просто строку (например, ссылку) — оборачиваем в dict
                # если панель вернула просто строку (например, ссылку) — оборачиваем в dict
        if isinstance(result, str):
            link_str = result.strip()
            client_id = None
            if link_str.startswith("vless://"):
                try:
                    client_id = link_str.split("vless://")[1].split("@")[0]
                except Exception:
                    client_id = None
            result = {"link": link_str, "client_id": client_id}

        link = result.get("link") or result.get("config") or result.get("url") or ""
        expiry_raw = result.get("expiry") or result.get("expires") or result.get("ttl_seconds")
        client_id = result.get("client_id") or result.get("id")

        expiry_ts = None
        if expiry_raw:
            expiry_raw = int(expiry_raw)
            expiry_ts = expiry_raw // 1000 if expiry_raw > 10**10 else expiry_raw

        expiry_time_str = "неизвестно"
        if expiry_ts:
            expiry_time_str = datetime.datetime.fromtimestamp(expiry_ts).strftime("%Y-%m-%d %H:%M:%S")

        if not link:
            link = f"vless://{client_id or 'unknown'}@vpn.uspeshnyy.ru:443?type=ws&security=tls&path=/vpn&encryption=none#UspeshnyyVPN-{tg_id}"

        # 4) сохраняем trial в БД
        try:
            call_db_func("add_trial", tg_id, client_id, link, expiry_ts or int(time.time()) + ttl_seconds, traffic_bytes)
        except Exception:
            logger.debug("[DB] add_trial не выполнен — продолжаем")

        # 5) проверка реферала
        try:
            ref = call_db_func("get_user_referrer", tg_id)
            if ref:
                referrer_id = int(ref.get("referrer_id") or ref)
                call_db_func("add_referral_usage", referrer_id, tg_id, client_id)
                call_db_func("add_referral_bonus", referrer_id, REFERRAL_BONUS_DAYS)
        except Exception:
            logger.debug("[TRIAL] Ошибка при обработке реферала")

        # 6) сообщение пользователю
        reply_text = (
            "✅ Тестовый VPN-доступ успешно активирован!\n\n"
            f"👤 Пользователь: @{clean_text(username)}\n"
            f"⏳ Срок действия: {TRIAL_DAYS_DEFAULT} дня(ей)\n"
            f"📦 Трафик: {TRIAL_TRAFFIC_GB} GB\n"
            f"🕒 Действителен до: {expiry_time_str}\n\n"
            "Скопируйте VPN-конфиг и импортируйте в приложение."
        )

        invite_link = f"https://t.me/pride34vpn_bot?start=ref_{tg_id}"

        # Получаем UUID клиента для QR-кодов
        user_uuid = client_id or str(tg_id)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Скопировать VPN-конфиг", callback_data=f"copy_config:{tg_id}")],
            [
                InlineKeyboardButton(text="📱 QR МТС/LTE", callback_data=f"qr_mts:{user_uuid}"),
                InlineKeyboardButton(text="📶 QR WiFi", callback_data=f"qr_wifi:{user_uuid}")
            ],
            [InlineKeyboardButton(text="👥 Пригласить друзей (+7 дней)", url=invite_link)],
            [InlineKeyboardButton(text="📖 Инструкция по настройке", web_app=WebAppInfo(url="https://telegra.ph/Podklyuchenie-VPN-dlya-Android-11-04"))],
            [
                InlineKeyboardButton(text="📱 Android", url="https://play.google.com/store/apps/details?id=com.happproxy"),
                InlineKeyboardButton(text="🍎 iOS", url="https://apps.apple.com/app/id6746188973")
            ],
            [
                InlineKeyboardButton(text="💻 Windows", url="https://github.com/2dust/v2rayN/releases"),
                InlineKeyboardButton(text="🧠 macOS", url="https://apps.apple.com/app/nekoray/id1620345338")
            ]
        ])

        # Приветственное фото + сообщение
        try:
            await message.answer_photo(
                photo=FSInputFile("hello.jpg"),
                caption=reply_text,
                reply_markup=keyboard
            )
        except Exception:
            await message.answer(reply_text, reply_markup=keyboard)

        logger.info(f"[TRIAL] ✅ Trial создан для @{username} ({tg_id})")

    except Exception as e:
        logger.exception(f"[TRIAL] Ошибка trial: {e}")
        await message.answer("❌ Произошла ошибка при создании trial-доступа. Попробуйте позже.")


# Обработчик кнопки "Скопировать VPN-конфиг"
@router.callback_query(F.data.startswith("copy_config:"))
async def copy_config_handler(callback: CallbackQuery):
    try:
        _, uid = callback.data.split(":", 1)
        user_id = int(uid)
    except Exception:
        await callback.answer("Ошибка обработки запроса.", show_alert=True)
        return

    config_text = None
    try:
        cfg = call_db_func("get_latest_trial", user_id)
        if cfg:
            config_text = cfg.get("link") or cfg.get("config") or str(cfg)
    except Exception:
        logger.debug("[TRIAL] get_latest_trial не доступен или упал")

    if not config_text:
        await callback.message.answer("⚠️ Конфиг не найден. Создайте trial заново.")
        await callback.answer()
        return

    await callback.message.answer(
        f"🔐 Ваш VPN-конфиг:\n\n<code>{clean_text(config_text)}</code>",
        parse_mode="HTML"
    )
    await callback.answer("Ссылка отправлена ✅", show_alert=False)


# Обработчик кнопки "QR-код подписки"
@router.callback_query(F.data.startswith("qr_sub:"))
async def qr_subscription_handler(callback: CallbackQuery):
    try:
        _, sub_id = callback.data.split(":", 1)
    except Exception:
        await callback.answer("Ошибка обработки запроса.", show_alert=True)
        return

    try:
        qr_buffer = generate_subscription_qr(sub_id)
        await callback.message.answer_photo(
            photo=BufferedInputFile(qr_buffer.read(), filename="subscription_qr.png"),
            caption=f"📱 QR-код для подписки\n\nОтсканируйте в приложении VPN или добавьте ссылку:\n<code>{get_subscription_url(sub_id)}</code>",
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.exception(f"[QR] Ошибка генерации QR: {e}")
        await callback.answer("Ошибка генерации QR-кода", show_alert=True)


# Обработчик кнопки "QR-код MTS"
@router.callback_query(F.data.startswith("qr_mts:"))
async def qr_mts_handler(callback: CallbackQuery):
    try:
        _, user_uuid = callback.data.split(":", 1)
    except Exception:
        await callback.answer("Ошибка обработки запроса.", show_alert=True)
        return

    try:
        qr_buffer = generate_vless_qr(user_uuid, "mts")
        link = generate_vless_link(user_uuid, "mts")
        await callback.message.answer_photo(
            photo=BufferedInputFile(qr_buffer.read(), filename="mts_qr.png"),
            caption=f"📱 QR-код для МТС/LTE\n\n<code>{link}</code>",
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.exception(f"[QR] Ошибка генерации QR MTS: {e}")
        await callback.answer("Ошибка генерации QR-кода", show_alert=True)


# Обработчик кнопки "QR-код WiFi"
@router.callback_query(F.data.startswith("qr_wifi:"))
async def qr_wifi_handler(callback: CallbackQuery):
    try:
        _, user_uuid = callback.data.split(":", 1)
    except Exception:
        await callback.answer("Ошибка обработки запроса.", show_alert=True)
        return

    try:
        qr_buffer = generate_vless_qr(user_uuid, "wifi")
        link = generate_vless_link(user_uuid, "wifi")
        await callback.message.answer_photo(
            photo=BufferedInputFile(qr_buffer.read(), filename="wifi_qr.png"),
            caption=f"📱 QR-код для WiFi\n\n<code>{link}</code>",
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        logger.exception(f"[QR] Ошибка генерации QR WiFi: {e}")
        await callback.answer("Ошибка генерации QR-кода", show_alert=True)


# Команда /trial_info — отладочная
@router.message(Command(commands=["trial_info"]))
async def trial_info_cmd(message: types.Message):
    user_id = message.from_user.id
    row = call_db_func("get_latest_trial", user_id)
    if not row:
        await message.answer("Информация о trial не найдена.")
        return
    text = f"Trial: client_id={row.get('client_id')}, expires={row.get('expires')}, link={row.get('link')}"
    await message.answer(text)
