from aiogram import Router, types, F
from utils.db import (
    log_vpn_check,
    get_user_row,
    get_strikes,
    set_user_status,
)
from config import STRIKE_LIMIT

router = Router()

@router.message(F.text == "🌐 Проверить VPN")
async def check_vpn(message: types.Message):
    tg_id = message.from_user.id

    # логируем факт, что пользователь нажал проверку
    log_vpn_check(tg_id)

    # проверяем страйки
    strikes = get_strikes(tg_id)
    status = "active"
    if strikes >= STRIKE_LIMIT:
        status = "blocked"
        set_user_status(tg_id, "blocked")

    row = get_user_row(tg_id)
    vpn_link = row["link"] if row and "link" in row.keys() else "—"

    text = (
        "🔍 Статус подключения:\n\n"
        f"Статус профиля: <b>{status}</b>\n"
        f"Нарушений: <b>{strikes}</b> / {STRIKE_LIMIT}\n\n"
        f"Твоя текущая конфигурация:\n<code>{vpn_link}</code>\n\n"
        "Если VPN включается и интернет идёт — всё отлично 👌\n"
        "Если не даёт интернет с включённым VPN:\n"
        "1. попробуй выключить/включить режим\n"
        "2. перезайти в приложение\n"
        "3. если не помогло — напиши в «❓ Помощь / FAQ»"
    )

    await message.answer(text)
