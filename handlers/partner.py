import logging
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.db import ensure_partner, get_balance, add_referral, get_all_partners
from config import PROJECT_NAME

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text.in_(["📋 Панель партнёра", "/partner"]))
async def show_partner_panel(message: types.Message):
    """Показывает партнёрскую панель пользователя"""
    user_id = message.from_user.id
    ensure_partner(user_id)

    balance = get_balance(user_id)
    referral_link = f"https://t.me/{PROJECT_NAME}_bot?start={user_id}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Пригласить друзей", switch_inline_query=referral_link)],
        [InlineKeyboardButton(text="💸 Вывести средства", callback_data="partner_withdraw")],
        [InlineKeyboardButton(text="🔄 Обновить баланс", callback_data="partner_refresh")]
    ])

    text = (
        f"👥 <b>Партнёрская панель</b>\n\n"
        f"💰 Текущий баланс: <b>{balance:.2f} ₽</b>\n"
        f"🔗 Ваша ссылка для приглашений:\n<code>{referral_link}</code>\n\n"
        f"🪙 За каждого друга, оформившего подписку, вы получаете бонусы!\n"
        f"Вывод возможен после накопления суммы от <b>200 ₽</b>."
    )

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    logger.info(f"[PARTNER] Панель открыта для {user_id}")


@router.callback_query(F.data == "partner_refresh")
async def partner_refresh(call: types.CallbackQuery):
    """Обновление баланса в панели"""
    user_id = call.from_user.id
    balance = get_balance(user_id)
    await call.message.edit_text(
        f"💰 Ваш текущий баланс: <b>{balance:.2f} ₽</b>\n\n"
        "🔗 Приглашайте друзей и зарабатывайте бонусы!",
        parse_mode="HTML"
    )
    await call.answer("Баланс обновлён ✅")


@router.callback_query(F.data == "partner_withdraw")
async def partner_withdraw(call: types.CallbackQuery):
    """Заглушка на вывод средств"""
    await call.answer()
    await call.message.answer(
        "📩 Для вывода средств напишите менеджеру поддержки:\n"
        "👉 @UspeshnyyVPN_support\n\n"
        "Минимальная сумма вывода — <b>200 ₽</b>.",
        parse_mode="HTML"
    )


# ===== Дополнительно для будущего API =====

async def register_referral(referrer_id: int, bonus: float = 10.0):
    """
    Вызывается, когда приглашённый пользователь активировал подписку.
    Добавляет бонус рефереру.
    """
    add_referral(referrer_id, bonus)
    logger.info(f"[PARTNER] Начислен бонус {bonus}₽ партнёру {referrer_id}")
