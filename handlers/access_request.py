# handlers/access_request.py
"""
Модуль обработки запросов на доступ к VPN.
Пользователь нажимает "Запросить доступ" -> вводит комментарий ->
админы получают уведомление -> админ подтверждает/отклоняет ->
пользователь получает ссылку на подписку.
"""
import logging
import uuid
from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS, ADMIN_USERNAMES, SUBSCRIPTION_AGGREGATOR_URL
from utils.db import (
    ensure_user_row,
    create_access_request,
    get_access_request,
    get_pending_request_by_user,
    get_approved_request_by_user,
    approve_access_request,
    reject_access_request
)


class AccessRequestStates(StatesGroup):
    """Состояния для запроса доступа"""
    waiting_for_comment = State()

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int, username: str = None) -> bool:
    """Проверяет, является ли пользователь админом"""
    if user_id in ADMIN_IDS:
        return True
    if username and username.lower() in [u.lower() for u in ADMIN_USERNAMES]:
        return True
    return False


async def get_admin_ids(bot: Bot) -> list:
    """
    Получает список ID админов.
    Для username пытается получить ID через getChat.
    """
    admin_ids = list(ADMIN_IDS)

    for username in ADMIN_USERNAMES:
        try:
            # Попробуем получить chat по username
            chat = await bot.get_chat(f"@{username}")
            if chat.id not in admin_ids:
                admin_ids.append(chat.id)
        except Exception as e:
            logger.warning(f"[ACCESS] Не удалось получить ID для @{username}: {e}")

    return admin_ids


def transliterate(text: str) -> str:
    """Транслитерация кириллицы в латиницу"""
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
        'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
        'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch',
        'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
        ' ': '_', '-': '_'
    }
    result = []
    for char in text:
        result.append(translit_map.get(char, char))
    return ''.join(result)


def generate_sub_id(full_name: str, user_id: int) -> str:
    """Генерирует sub_id из имени пользователя (транслит) или user_id"""
    if full_name and full_name.strip():
        # Транслитерируем и очищаем
        sub_id = transliterate(full_name.strip())
        # Оставляем только буквы, цифры и подчёркивания
        sub_id = ''.join(c for c in sub_id if c.isalnum() or c == '_')
        # Убираем двойные подчёркивания
        while '__' in sub_id:
            sub_id = sub_id.replace('__', '_')
        # Убираем подчёркивания по краям
        sub_id = sub_id.strip('_').lower()
        if sub_id:
            return sub_id
    return f"user_{user_id}"


async def notify_admins_about_request(bot: Bot, request_id: int, user_id: int, username: str, full_name: str, comment: str = ""):
    """Отправляет уведомление всем админам о новом запросе"""
    admin_ids = await get_admin_ids(bot)

    text = (
        f"📩 <b>Новый запрос на VPN доступ</b>\n\n"
        f"👤 Пользователь: {full_name or 'Без имени'}\n"
        f"🆔 Username: @{username if username else 'нет'}\n"
        f"🔢 ID: <code>{user_id}</code>\n"
        f"📝 Запрос: #{request_id}\n\n"
        f"💬 <b>Комментарий:</b>\n{comment or 'Не указан'}\n\n"
        f"Выберите действие:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"access_approve:{request_id}"),
            InlineKeyboardButton(text="❌ Отказать", callback_data=f"access_reject:{request_id}")
        ]
    ])

    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=keyboard)
            logger.info(f"[ACCESS] Уведомление отправлено админу {admin_id}")
        except Exception as e:
            logger.warning(f"[ACCESS] Не удалось отправить уведомление админу {admin_id}: {e}")


@router.callback_query(F.data == "request_access")
async def request_access_handler(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки 'Запросить доступ'"""
    user = callback.from_user
    user_id = user.id
    username = user.username or ""
    full_name = user.full_name or ""

    # Сохраняем пользователя в БД
    ensure_user_row(user_id, username, full_name)

    # Проверяем, есть ли уже одобренный доступ
    approved = get_approved_request_by_user(user_id)
    if approved:
        sub_id = approved.get('sub_id', f'user_{user_id}')
        sub_url = f"{SUBSCRIPTION_AGGREGATOR_URL}{sub_id}"

        await callback.message.edit_text(
            f"✅ <b>У вас уже есть VPN доступ!</b>\n\n"
            f"🔗 Ваша ссылка на подписку:\n<code>{sub_url}</code>\n\n"
            f"Откройте эту ссылку в браузере или добавьте в VPN-приложение.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🌐 Открыть подписку", url=sub_url)],
                [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")]
            ])
        )
        await callback.answer()
        return

    # Проверяем, есть ли уже ожидающий запрос
    pending = get_pending_request_by_user(user_id)
    if pending:
        await callback.message.edit_text(
            "⏳ <b>Ваш запрос уже отправлен!</b>\n\n"
            "Ожидайте подтверждения от администратора.\n"
            "Вам придёт уведомление когда доступ будет готов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")]
            ])
        )
        await callback.answer()
        return

    # Просим пользователя написать комментарий
    await callback.message.edit_text(
        "📝 <b>Запрос на VPN доступ</b>\n\n"
        "Пожалуйста, напишите кто вы и зачем вам нужен VPN.\n\n"
        "<i>Например: Иванов Иван, отдел продаж, для работы с заблокированными сервисами</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu")]
        ])
    )

    # Сохраняем данные и устанавливаем состояние ожидания комментария
    await state.set_state(AccessRequestStates.waiting_for_comment)
    await state.update_data(username=username, full_name=full_name)
    await callback.answer()


@router.message(AccessRequestStates.waiting_for_comment)
async def process_access_comment(message: Message, state: FSMContext):
    """Обработка комментария к запросу на доступ"""
    user = message.from_user
    user_id = user.id
    comment = message.text.strip()

    # Проверяем минимальную длину комментария
    if len(comment) < 5:
        await message.answer(
            "⚠️ Комментарий слишком короткий.\n"
            "Пожалуйста, напишите подробнее кто вы и зачем вам нужен VPN.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu")]
            ])
        )
        return

    # Получаем сохранённые данные
    data = await state.get_data()
    username = data.get('username', user.username or "")
    full_name = data.get('full_name', user.full_name or "")

    # Создаем новый запрос с комментарием
    request_id = create_access_request(user_id, username, full_name, comment)

    # Отправляем уведомление админам
    await notify_admins_about_request(
        message.bot, request_id, user_id, username, full_name, comment
    )

    await message.answer(
        "📨 <b>Запрос отправлен!</b>\n\n"
        "Администратор рассмотрит ваш запрос в ближайшее время.\n"
        "Вам придёт уведомление когда доступ будет готов.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")]
        ])
    )

    # Сбрасываем состояние
    await state.clear()

    logger.info(f"[ACCESS] Пользователь {user_id} (@{username}) запросил доступ, запрос #{request_id}")


@router.callback_query(F.data.startswith("access_approve:"))
async def approve_access_handler(callback: CallbackQuery):
    """Обработка подтверждения доступа админом"""
    admin = callback.from_user

    # Проверяем, что это админ
    if not is_admin(admin.id, admin.username):
        await callback.answer("У вас нет прав для этого действия!", show_alert=True)
        return

    try:
        request_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка: неверный ID запроса", show_alert=True)
        return

    # Получаем информацию о запросе
    request_info = get_access_request(request_id)
    if not request_info:
        await callback.answer("Запрос не найден!", show_alert=True)
        return

    if request_info['status'] != 'pending':
        status_text = "одобрен" if request_info['status'] == 'approved' else "отклонён"
        await callback.answer(f"Этот запрос уже {status_text}!", show_alert=True)
        return

    user_id = request_info['user_id']
    username = request_info['username'] or ""
    full_name = request_info['full_name'] or ""

    # Генерируем UUID и sub_id для пользователя (транслит имени)
    client_uuid = str(uuid.uuid4())
    sub_id = generate_sub_id(full_name, user_id)

    # Добавляем пользователя в aggregator на сервере
    success = add_user_to_aggregator(sub_id, client_uuid, full_name or f"User {user_id}")

    if not success:
        await callback.answer("Ошибка при создании VPN пользователя!", show_alert=True)
        return

    # Обновляем статус запроса в БД
    approve_access_request(request_id, admin.id, client_uuid, sub_id)

    # Формируем ссылку на подписку
    sub_url = f"{SUBSCRIPTION_AGGREGATOR_URL}{sub_id}"

    # Уведомляем пользователя
    try:
        await callback.bot.send_message(
            user_id,
            f"🎉 <b>Ваш запрос одобрен!</b>\n\n"
            f"🔗 Ваша персональная ссылка на VPN:\n<code>{sub_url}</code>\n\n"
            f"📱 <b>Как подключиться:</b>\n"
            f"1. Откройте ссылку в браузере\n"
            f"2. Отсканируйте QR-код в VPN-приложении\n"
            f"   • Android: v2rayNG\n"
            f"   • iOS: Happ\n\n"
            f"Или добавьте ссылку как подписку в приложении.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🌐 Открыть подписку", url=sub_url)],
                [
                    InlineKeyboardButton(text="📱 Android", url="https://play.google.com/store/apps/details?id=com.v2ray.ang"),
                    InlineKeyboardButton(text="🍎 iOS", url="https://apps.apple.com/app/id6746188973")
                ]
            ])
        )
        logger.info(f"[ACCESS] Пользователь {user_id} уведомлён об одобрении")
    except Exception as e:
        logger.warning(f"[ACCESS] Не удалось уведомить пользователя {user_id}: {e}")

    # Обновляем сообщение у админа
    await callback.message.edit_text(
        f"✅ <b>Запрос #{request_id} одобрен!</b>\n\n"
        f"👤 Пользователь: {full_name}\n"
        f"🆔 @{username if username else user_id}\n"
        f"🔗 Подписка: {sub_id}\n\n"
        f"Пользователь уведомлён."
    )
    await callback.answer("Доступ подтверждён!")

    logger.info(f"[ACCESS] Админ {admin.id} одобрил запрос #{request_id} от {user_id}")


@router.callback_query(F.data.startswith("access_reject:"))
async def reject_access_handler(callback: CallbackQuery):
    """Обработка отказа в доступе"""
    admin = callback.from_user

    # Проверяем, что это админ
    if not is_admin(admin.id, admin.username):
        await callback.answer("У вас нет прав для этого действия!", show_alert=True)
        return

    try:
        request_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка: неверный ID запроса", show_alert=True)
        return

    # Получаем информацию о запросе
    request_info = get_access_request(request_id)
    if not request_info:
        await callback.answer("Запрос не найден!", show_alert=True)
        return

    if request_info['status'] != 'pending':
        status_text = "одобрен" if request_info['status'] == 'approved' else "отклонён"
        await callback.answer(f"Этот запрос уже {status_text}!", show_alert=True)
        return

    user_id = request_info['user_id']
    username = request_info['username'] or ""
    full_name = request_info['full_name'] or ""

    # Обновляем статус запроса
    reject_access_request(request_id, admin.id)

    # Уведомляем пользователя
    try:
        await callback.bot.send_message(
            user_id,
            "❌ <b>К сожалению, ваш запрос отклонён.</b>\n\n"
            "Если вы считаете это ошибкой, свяжитесь с поддержкой: @uspeshnyy"
        )
        logger.info(f"[ACCESS] Пользователь {user_id} уведомлён об отказе")
    except Exception as e:
        logger.warning(f"[ACCESS] Не удалось уведомить пользователя {user_id}: {e}")

    # Обновляем сообщение у админа
    await callback.message.edit_text(
        f"❌ <b>Запрос #{request_id} отклонён</b>\n\n"
        f"👤 Пользователь: {full_name}\n"
        f"🆔 @{username if username else user_id}\n\n"
        f"Пользователь уведомлён."
    )
    await callback.answer("Запрос отклонён")

    logger.info(f"[ACCESS] Админ {admin.id} отклонил запрос #{request_id} от {user_id}")


def add_client_to_xui(client_uuid: str, email: str, sub_id: str) -> bool:
    """
    Добавляет клиента в X-UI панель через API.
    """
    import requests
    import json
    from config import XUI_URL, XUI_LOGIN, XUI_PASSWORD, XUI_INBOUND_ID

    try:
        session = requests.Session()
        session.verify = False

        # Авторизация
        login_res = session.post(
            f"{XUI_URL}/login",
            data={"username": XUI_LOGIN, "password": XUI_PASSWORD},
            timeout=10
        )
        if login_res.status_code != 200 or "success" not in login_res.text.lower() or '"success":false' in login_res.text.lower():
            logger.error(f"[XUI] Ошибка авторизации: {login_res.text}")
            return False

        logger.info("[XUI] Авторизация успешна")

        # Формируем данные клиента
        client_data = {
            "id": client_uuid,
            "flow": "xtls-rprx-vision",
            "email": email,
            "limitIp": 3,
            "totalGB": 0,
            "expiryTime": 0,
            "enable": True,
            "subId": sub_id
        }

        payload = {
            "id": XUI_INBOUND_ID,
            "settings": json.dumps({"clients": [client_data]})
        }

        # Добавляем клиента
        add_res = session.post(
            f"{XUI_URL}/panel/api/inbounds/addClient",
            data=payload,
            timeout=10
        )

        if add_res.status_code == 200 and '"success":true' in add_res.text.lower():
            logger.info(f"[XUI] Клиент {email} добавлен в x-ui")
            return True
        else:
            logger.error(f"[XUI] Ошибка добавления клиента: {add_res.text}")
            return False

    except Exception as e:
        logger.exception(f"[XUI] Ошибка: {e}")
        return False


def add_user_to_aggregator(sub_id: str, client_uuid: str, name: str) -> bool:
    """
    Добавляет пользователя в subscription aggregator и X-UI панель.
    """
    import subprocess

    safe_name = name.replace('"', '').replace("'", "").replace('\n', ' ')
    email = f"{sub_id}@pride34.ru"
    aggregator_path = '/opt/subscription-aggregator/aggregator.py'

    # 1) Сначала добавляем в X-UI панель (критично для работы VPN!)
    xui_success = add_client_to_xui(client_uuid, email, sub_id)
    if not xui_success:
        logger.error(f"[ACCESS] Не удалось добавить пользователя {sub_id} в X-UI")
        return False

    # 2) Добавляем в aggregator для генерации ссылок
    try:
        with open(aggregator_path, 'r') as f:
            lines = f.readlines()

        # Проверяем, существует ли уже пользователь
        content = ''.join(lines)
        if f'"{sub_id}"' in content:
            logger.info(f"[ACCESS] Пользователь {sub_id} уже существует в aggregator")
            return True

        # Находим строку "USERS = {" и вставляем нового пользователя после неё
        new_lines = []
        user_added = False
        for i, line in enumerate(lines):
            new_lines.append(line)
            if not user_added and 'USERS = {' in line:
                # Добавляем нового пользователя сразу после открывающей скобки
                new_user_line = f'    "{sub_id}": {{"uuid": "{client_uuid}"}},  # {safe_name}\n'
                new_lines.append(new_user_line)
                user_added = True

        if not user_added:
            logger.error("[ACCESS] Не найден USERS dict в aggregator.py")
            return False

        with open(aggregator_path, 'w') as f:
            f.writelines(new_lines)

        # Перезапускаем aggregator
        subprocess.run(['systemctl', 'restart', 'subscription-aggregator'], check=True)

        logger.info(f"[ACCESS] Пользователь {sub_id} добавлен в aggregator")
        return True

    except Exception as e:
        logger.exception(f"[ACCESS] Ошибка добавления пользователя: {e}")
        return False
