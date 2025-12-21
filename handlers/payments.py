"""
Обработчик системы оплаты
"""
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import utils.db as db
import logging

router = Router()
logger = logging.getLogger(__name__)

# Тарифы
TARIFFS = {
    1: {"months": 1, "price": 150, "traffic_gb": 100},
    3: {"months": 3, "price": 350, "traffic_gb": 300},
    6: {"months": 6, "price": 600, "traffic_gb": 600},
    12: {"months": 12, "price": 900, "traffic_gb": 1200}
}

# Реферальный процент
REFERRAL_COMMISSION = 0.25  # 25%


class PaymentStates(StatesGroup):
    choosing_tariff = State()
    entering_promocode = State()
    choosing_payment_method = State()


class TariffCallback(CallbackData, prefix="tariff"):
    months: int


class PaymentMethodCallback(CallbackData, prefix="payment"):
    method: str
    tariff_months: int


@router.message(F.text == "💳 Пополнить")
async def start_payment(message: types.Message, state: FSMContext):
    """Начало процесса оплаты - выбор тарифа"""
    user_id = message.from_user.id
    balance = db.get_user_balance(user_id)

    text = (
        f"💰 <b>Ваш баланс:</b> {balance:.2f}₽\n\n"
        f"<b>Выберите тариф:</b>\n\n"
    )

    for months, tariff in TARIFFS.items():
        price_per_month = tariff['price'] / months
        text += (
            f"• <b>{months} мес</b> — {tariff['price']}₽ "
            f"({price_per_month:.0f}₽/мес, {tariff['traffic_gb']} GB)\n"
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"1 месяц - 150₽", callback_data=TariffCallback(months=1).pack()),
            InlineKeyboardButton(text=f"3 месяца - 350₽", callback_data=TariffCallback(months=3).pack())
        ],
        [
            InlineKeyboardButton(text=f"6 месяцев - 600₽", callback_data=TariffCallback(months=6).pack()),
            InlineKeyboardButton(text=f"12 месяцев - 900₽", callback_data=TariffCallback(months=12).pack())
        ],
        [
            InlineKeyboardButton(text="💵 Пополнить баланс", callback_data="topup_balance")
        ]
    ])

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await state.set_state(PaymentStates.choosing_tariff)


@router.callback_query(TariffCallback.filter())
async def process_tariff_selection(callback: CallbackQuery, callback_data: TariffCallback, state: FSMContext):
    """Обработка выбора тарифа"""
    months = callback_data.months
    tariff = TARIFFS[months]
    price = tariff['price']

    await state.update_data(tariff_months=months, tariff_price=price)

    text = (
        f"✅ <b>Выбран тариф:</b> {months} мес - {price}₽\n\n"
        f"📝 Хотите использовать промокод?\n\n"
        f"Введите промокод или нажмите «Продолжить без промокода»"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Продолжить без промокода", callback_data=f"skip_promo:{months}")]
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await state.set_state(PaymentStates.entering_promocode)
    await callback.answer()


@router.message(PaymentStates.entering_promocode)
async def process_promocode(message: types.Message, state: FSMContext):
    """Обработка ввода промокода"""
    promocode = message.text.strip().upper()
    data = await state.get_data()

    tariff_months = data.get('tariff_months')
    original_price = data.get('tariff_price')

    # Проверяем промокод
    promo = db.get_promocode(promocode)

    if not promo:
        await message.answer("❌ Промокод не найден. Попробуйте еще раз или пропустите этот шаг.")
        return

    # Проверяем срок действия
    import time
    if promo['expires_at'] and promo['expires_at'] < time.time():
        await message.answer("❌ Промокод истек. Попробуйте другой.")
        return

    # Вычисляем скидку
    if promo['discount_percent'] > 0:
        discount = original_price * (promo['discount_percent'] / 100)
    else:
        discount = promo['discount_amount']

    final_price = max(0, original_price - discount)

    await state.update_data(promocode=promocode, final_price=final_price, discount=discount)

    await show_payment_methods(message, tariff_months, final_price, discount, promocode)
    await state.set_state(PaymentStates.choosing_payment_method)


@router.callback_query(F.data.startswith("skip_promo:"))
async def skip_promocode(callback: CallbackQuery, state: FSMContext):
    """Пропуск промокода"""
    data = await state.get_data()
    tariff_months = data.get('tariff_months')
    price = data.get('tariff_price')

    await state.update_data(final_price=price, promocode=None, discount=0)
    await show_payment_methods(callback.message, tariff_months, price)
    await state.set_state(PaymentStates.choosing_payment_method)
    await callback.answer()


async def show_payment_methods(message: types.Message, tariff_months: int, price: float, discount: float = 0, promocode: str = None):
    """Показывает способы оплаты"""
    user_id = message.chat.id if hasattr(message, 'chat') else message.from_user.id
    balance = db.get_user_balance(user_id)

    text = f"💳 <b>Способ оплаты</b>\n\n"
    text += f"📦 <b>Тариф:</b> {tariff_months} мес\n"

    if promocode:
        text += f"🎟️ <b>Промокод:</b> {promocode} (-{discount:.2f}₽)\n"

    text += f"💰 <b>К оплате:</b> {price:.2f}₽\n"
    text += f"💵 <b>Ваш баланс:</b> {balance:.2f}₽\n\n"

    keyboard_buttons = []

    # Оплата с баланса (если достаточно средств)
    if balance >= price:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"💰 Оплатить с баланса ({balance:.2f}₽)",
                callback_data=PaymentMethodCallback(method="balance", tariff_months=tariff_months).pack()
            )
        ])

    # Другие способы оплаты
    keyboard_buttons.extend([
        [InlineKeyboardButton(text="🏦 ЮKassa", callback_data=PaymentMethodCallback(method="yookassa", tariff_months=tariff_months).pack())],
        [InlineKeyboardButton(text="₿ Криптовалюта", callback_data=PaymentMethodCallback(method="crypto", tariff_months=tariff_months).pack())],
        [InlineKeyboardButton(text="🤖 CryptoBot", callback_data=PaymentMethodCallback(method="cryptobot", tariff_months=tariff_months).pack())],
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data=PaymentMethodCallback(method="stars", tariff_months=tariff_months).pack())]
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    if hasattr(message, 'edit_text'):
        await message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(PaymentMethodCallback.filter())
async def process_payment_method(callback: CallbackQuery, callback_data: PaymentMethodCallback, state: FSMContext):
    """Обработка выбора способа оплаты"""
    method = callback_data.method
    data = await state.get_data()

    tariff_months = data.get('tariff_months')
    final_price = data.get('final_price')
    promocode = data.get('promocode')

    user_id = callback.from_user.id

    if method == "balance":
        # Оплата с баланса
        try:
            # Списываем средства
            db.subtract_balance(user_id, final_price, "payment", f"Оплата тарифа {tariff_months} мес")

            # Создаем платеж
            payment_id = db.create_payment(user_id, final_price, "balance", tariff_months, promocode)
            db.update_payment_status(payment_id, "completed")

            # Начисляем реферальный бонус
            referrer_id = db.get_user_referrer(user_id)
            if referrer_id:
                bonus_amount = final_price * REFERRAL_COMMISSION
                db.add_balance(referrer_id, bonus_amount, "referral", f"Реферальный бонус от платежа #{payment_id}", payment_id)

                # Отправляем уведомление рефереру
                from aiogram import Bot
                from config import TELEGRAM_BOT_TOKEN
                bot = Bot(token=TELEGRAM_BOT_TOKEN)
                await bot.send_message(
                    referrer_id,
                    f"💰 <b>Реферальный бонус!</b>\n\n"
                    f"Ваш реферал оплатил подписку.\n"
                    f"Вам начислено: <b>{bonus_amount:.2f}₽</b>",
                    parse_mode="HTML"
                )

            # Активируем подписку
            from utils.xui_api import create_or_extend_subscription
            from config import SUBSCRIPTION_URL

            tariff = TARIFFS[tariff_months]
            subscription_link = None
            try:
                client_uuid, vless_link, expiry_ts, traffic_bytes = create_or_extend_subscription(
                    user_id,
                    tariff_months,
                    tariff['traffic_gb']
                )

                # Создаем запись о подписке в БД
                db.create_subscription(user_id, client_uuid, tariff_months, expiry_ts, traffic_bytes, payment_id)

                # Формируем ссылку на подписку
                subscription_link = f"{SUBSCRIPTION_URL}{client_uuid}"

                logger.info(f"[PAYMENT] Подписка активирована для {user_id}: {subscription_link}")

            except Exception as e:
                logger.error(f"[PAYMENT] Ошибка активации подписки для {user_id}: {e}")

            # Формируем сообщение об успешной оплате
            success_message = (
                f"✅ <b>Оплата успешна!</b>\n\n"
                f"💳 Списано с баланса: {final_price:.2f}₽\n"
                f"📦 Тариф: {tariff_months} мес\n"
                f"📊 Трафик: {tariff['traffic_gb']} GB\n\n"
            )

            if subscription_link:
                import datetime
                expiry_date = datetime.datetime.fromtimestamp(expiry_ts).strftime('%d.%m.%Y %H:%M')
                success_message += (
                    f"✅ Подписка активирована до {expiry_date}\n\n"
                    f"🔗 <b>Ссылка на подписку:</b>\n<code>{subscription_link}</code>\n\n"
                    f"Скопируйте эту ссылку в приложение Happ или другой VPN-клиент."
                )
            else:
                success_message += "⚠️ Подписка будет активирована в ближайшее время."

            await callback.message.edit_text(success_message, parse_mode="HTML")

        except ValueError as e:
            await callback.message.edit_text(
                f"❌ <b>Ошибка:</b>\n{str(e)}",
                parse_mode="HTML"
            )

    elif method == "cryptobot":
        # Оплата через CryptoBot
        try:
            from utils.cryptobot_pay import create_invoice

            # Создаем платеж в БД
            payment_id = db.create_payment(user_id, final_price, "cryptobot", tariff_months, promocode)

            # Создаём инвойс
            invoice = await create_invoice(
                amount=final_price,
                description=f"Оплата VPN подписки на {tariff_months} мес",
                user_id=user_id,
                payload=str(payment_id)
            )

            # Сохраняем invoice_id в платеже
            db.update_payment_status(payment_id, "pending", str(invoice['invoice_id']))

            # Отправляем ссылку на оплату
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=invoice['bot_invoice_url'])],
                [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment:{payment_id}")]
            ])

            await callback.message.edit_text(
                f"💰 <b>Оплата через CryptoBot</b>\n\n"
                f"💳 Сумма: {invoice['amount']} {invoice['currency']}\n"
                f"📦 Тариф: {tariff_months} мес\n\n"
                f"Нажмите кнопку «Оплатить» для перехода к оплате.\n"
                f"После оплаты нажмите «Проверить оплату».",
                parse_mode="HTML",
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"[CRYPTOBOT] Ошибка создания инвойса: {e}")
            await callback.message.edit_text(
                f"❌ <b>Ошибка создания платежа</b>\n\n"
                f"Попробуйте другой способ оплаты или обратитесь в поддержку.",
                parse_mode="HTML"
            )

    elif method == "yookassa":
        # Оплата через YooKassa
        try:
            from utils.yookassa_pay import create_payment as create_yookassa_payment

            # Создаем платеж в БД
            payment_id = db.create_payment(user_id, final_price, "yookassa", tariff_months, promocode)

            # Создаём платеж в YooKassa
            payment_data = create_yookassa_payment(
                amount=final_price,
                description=f"Оплата VPN подписки на {tariff_months} мес",
                return_url=f"https://t.me/UspeshnyyVPN_bot?start=payment_{payment_id}",
                metadata={
                    'payment_id': payment_id,
                    'user_id': user_id,
                    'tariff_months': tariff_months
                }
            )

            # Сохраняем payment_id в БД
            db.update_payment_status(payment_id, "pending", payment_data['payment_id'])

            # Отправляем ссылку на оплату
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=payment_data['confirmation_url'])],
                [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_yookassa:{payment_id}")]
            ])

            await callback.message.edit_text(
                f"💰 <b>Оплата через ЮKassa</b>\n\n"
                f"💳 Сумма: {final_price:.2f}₽\n"
                f"📦 Тариф: {tariff_months} мес\n\n"
                f"Нажмите кнопку «Оплатить» для перехода к оплате.\n"
                f"После оплаты нажмите «Проверить оплату».",
                parse_mode="HTML",
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"[YOOKASSA] Ошибка создания платежа: {e}")
            await callback.message.edit_text(
                f"❌ <b>Ошибка создания платежа</b>\n\n"
                f"Попробуйте другой способ оплаты или обратитесь в поддержку.",
                parse_mode="HTML"
            )

    elif method == "stars":
        # Оплата через Telegram Stars
        try:
            from aiogram import Bot
            from aiogram.types import LabeledPrice
            from config import TELEGRAM_BOT_TOKEN, STARS_PRICE

            # Создаем платеж в БД
            payment_id = db.create_payment(user_id, final_price, "stars", tariff_months, promocode)

            # Рассчитываем цену в Stars (1 Star ≈ определённая сумма в рублях)
            # Например, если STARS_PRICE = 20, то 1 Star = 7.5 рублей
            stars_amount = int(final_price / (STARS_PRICE / 1))  # Конвертация

            bot = Bot(token=TELEGRAM_BOT_TOKEN)

            # Отправляем инвойс
            await bot.send_invoice(
                chat_id=user_id,
                title=f"VPN подписка на {tariff_months} мес",
                description=f"Доступ к VPN сервису на {tariff_months} месяц(ев) с трафиком {TARIFFS[tariff_months]['traffic_gb']} GB",
                payload=str(payment_id),
                provider_token="",  # Для Stars не требуется
                currency="XTR",  # Telegram Stars
                prices=[LabeledPrice(label=f"Подписка {tariff_months} мес", amount=stars_amount)],
                start_parameter=f"pay_{payment_id}"
            )

            await callback.message.edit_text(
                f"⭐ <b>Оплата через Telegram Stars</b>\n\n"
                f"💳 Сумма: {stars_amount} Stars\n"
                f"📦 Тариф: {tariff_months} мес\n\n"
                f"Инвойс отправлен вам в личные сообщения.\n"
                f"Оплатите его для активации подписки.",
                parse_mode="HTML"
            )

            logger.info(f"[STARS] Создан инвойс для платежа #{payment_id} на {stars_amount} Stars")

        except Exception as e:
            logger.error(f"[STARS] Ошибка создания инвойса: {e}")
            await callback.message.edit_text(
                f"❌ <b>Ошибка создания платежа</b>\n\n"
                f"Попробуйте другой способ оплаты или обратитесь в поддержку.",
                parse_mode="HTML"
            )

    else:
        # Другие способы оплаты (заглушки)
        method_names = {
            "crypto": "Криптовалюта"
        }

        await callback.message.edit_text(
            f"🚧 <b>Интеграция с {method_names.get(method, method)} в разработке</b>\n\n"
            f"Пожалуйста, используйте другой способ оплаты или пополните баланс.",
            parse_mode="HTML"
        )

    await state.clear()
    await callback.answer()


@router.callback_query(F.data.startswith("check_yookassa:"))
async def check_yookassa_payment(callback: CallbackQuery):
    """Проверка статуса платежа YooKassa"""
    payment_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    # Получаем информацию о платеже
    payment = db.get_payment(payment_id)

    if not payment or payment['user_id'] != user_id:
        await callback.answer("❌ Платеж не найден", show_alert=True)
        return

    if payment['status'] == 'completed':
        await callback.answer("✅ Платеж уже обработан", show_alert=True)
        return

    # Проверяем статус в YooKassa
    try:
        from utils.yookassa_pay import check_payment_status
        from utils.xui_api import create_or_extend_subscription
        from config import SUBSCRIPTION_URL

        yookassa_payment_id = payment['provider_payment_id']
        status = check_payment_status(yookassa_payment_id)

        if status['paid']:
            # Платеж оплачен, активируем подписку
            tariff_months = payment['tariff_months']
            tariff = TARIFFS[tariff_months]

            # Обновляем статус платежа
            db.update_payment_status(payment_id, "completed")

            # Начисляем реферальный бонус
            referrer_id = db.get_user_referrer(user_id)
            if referrer_id:
                bonus_amount = payment['amount'] * REFERRAL_COMMISSION
                db.add_balance(referrer_id, bonus_amount, "referral", f"Реферальный бонус от платежа #{payment_id}", payment_id)

                # Отправляем уведомление рефереру
                from aiogram import Bot
                from config import TELEGRAM_BOT_TOKEN
                bot = Bot(token=TELEGRAM_BOT_TOKEN)
                try:
                    await bot.send_message(
                        referrer_id,
                        f"💰 <b>Реферальный бонус!</b>\n\n"
                        f"Ваш реферал оплатил подписку.\n"
                        f"Вам начислено: <b>{bonus_amount:.2f}₽</b>",
                        parse_mode="HTML"
                    )
                except:
                    pass

            # Активируем подписку
            try:
                client_uuid, vless_link, expiry_ts, traffic_bytes = create_or_extend_subscription(
                    user_id,
                    tariff_months,
                    tariff['traffic_gb']
                )

                # Создаем запись о подписке в БД
                db.create_subscription(user_id, client_uuid, tariff_months, expiry_ts, traffic_bytes, payment_id)

                # Формируем ссылку на подписку
                subscription_link = f"{SUBSCRIPTION_URL}{client_uuid}"

                # Уведомляем пользователя об успешной оплате
                import datetime
                expiry_date = datetime.datetime.fromtimestamp(expiry_ts).strftime('%d.%m.%Y %H:%M')

                await callback.message.edit_text(
                    f"✅ <b>Оплата подтверждена!</b>\n\n"
                    f"💳 Сумма: {status['amount']:.2f}₽\n"
                    f"📦 Тариф: {tariff_months} мес\n"
                    f"📊 Трафик: {tariff['traffic_gb']} GB\n\n"
                    f"✅ Подписка активирована до {expiry_date}\n\n"
                    f"🔗 <b>Ссылка на подписку:</b>\n<code>{subscription_link}</code>\n\n"
                    f"Скопируйте эту ссылку в приложение Happ или другой VPN-клиент.",
                    parse_mode="HTML"
                )

                logger.info(f"[YOOKASSA] Платеж #{payment_id} подтвержден, подписка активирована")

            except Exception as e:
                logger.error(f"[YOOKASSA] Ошибка активации подписки: {e}")
                await callback.message.edit_text(
                    f"✅ <b>Оплата подтверждена!</b>\n\n"
                    f"⚠️ Произошла ошибка при активации подписки. Обратитесь в поддержку.",
                    parse_mode="HTML"
                )

        else:
            await callback.answer(
                f"⏳ Платеж еще не оплачен. Статус: {status['status']}",
                show_alert=True
            )

    except Exception as e:
        logger.error(f"[YOOKASSA] Ошибка проверки платежа: {e}")
        await callback.answer("❌ Ошибка проверки платежа", show_alert=True)


@router.callback_query(F.data.startswith("check_payment:"))
async def check_payment_status(callback: CallbackQuery):
    """Проверка статуса платежа"""
    payment_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    # Получаем информацию о платеже
    payment = db.get_payment(payment_id)

    if not payment or payment['user_id'] != user_id:
        await callback.answer("❌ Платеж не найден", show_alert=True)
        return

    if payment['status'] == 'completed':
        await callback.answer("✅ Платеж уже обработан", show_alert=True)
        return

    # Проверяем статус в CryptoBot
    try:
        from utils.cryptobot_pay import check_invoice_status
        from utils.xui_api import create_or_extend_subscription
        from config import SUBSCRIPTION_URL

        invoice_id = int(payment['provider_payment_id'])
        status = await check_invoice_status(invoice_id)

        if status['paid']:
            # Платеж оплачен, активируем подписку
            tariff_months = payment['tariff_months']
            tariff = TARIFFS[tariff_months]

            # Обновляем статус платежа
            db.update_payment_status(payment_id, "completed")

            # Начисляем реферальный бонус
            referrer_id = db.get_user_referrer(user_id)
            if referrer_id:
                bonus_amount = payment['amount'] * REFERRAL_COMMISSION
                db.add_balance(referrer_id, bonus_amount, "referral", f"Реферальный бонус от платежа #{payment_id}", payment_id)

                # Отправляем уведомление рефереру
                from aiogram import Bot
                from config import TELEGRAM_BOT_TOKEN
                bot = Bot(token=TELEGRAM_BOT_TOKEN)
                try:
                    await bot.send_message(
                        referrer_id,
                        f"💰 <b>Реферальный бонус!</b>\n\n"
                        f"Ваш реферал оплатил подписку.\n"
                        f"Вам начислено: <b>{bonus_amount:.2f}₽</b>",
                        parse_mode="HTML"
                    )
                except:
                    pass

            # Активируем подписку
            try:
                client_uuid, vless_link, expiry_ts, traffic_bytes = create_or_extend_subscription(
                    user_id,
                    tariff_months,
                    tariff['traffic_gb']
                )

                # Создаем запись о подписке в БД
                db.create_subscription(user_id, client_uuid, tariff_months, expiry_ts, traffic_bytes, payment_id)

                # Формируем ссылку на подписку
                subscription_link = f"{SUBSCRIPTION_URL}{client_uuid}"

                # Уведомляем пользователя об успешной оплате
                import datetime
                expiry_date = datetime.datetime.fromtimestamp(expiry_ts).strftime('%d.%m.%Y %H:%M')

                await callback.message.edit_text(
                    f"✅ <b>Оплата подтверждена!</b>\n\n"
                    f"💳 Сумма: {status['amount']} {status['currency']}\n"
                    f"📦 Тариф: {tariff_months} мес\n"
                    f"📊 Трафик: {tariff['traffic_gb']} GB\n\n"
                    f"✅ Подписка активирована до {expiry_date}\n\n"
                    f"🔗 <b>Ссылка на подписку:</b>\n<code>{subscription_link}</code>\n\n"
                    f"Скопируйте эту ссылку в приложение Happ или другой VPN-клиент.",
                    parse_mode="HTML"
                )

                logger.info(f"[CRYPTOBOT] Платеж #{payment_id} подтвержден, подписка активирована")

            except Exception as e:
                logger.error(f"[CRYPTOBOT] Ошибка активации подписки: {e}")
                await callback.message.edit_text(
                    f"✅ <b>Оплата подтверждена!</b>\n\n"
                    f"⚠️ Произошла ошибка при активации подписки. Обратитесь в поддержку.",
                    parse_mode="HTML"
                )

        else:
            await callback.answer(
                f"⏳ Платеж еще не оплачен. Статус: {status['status']}",
                show_alert=True
            )

    except Exception as e:
        logger.error(f"[CRYPTOBOT] Ошибка проверки платежа: {e}")
        await callback.answer("❌ Ошибка проверки платежа", show_alert=True)


@router.callback_query(F.data == "topup_balance")
async def topup_balance_menu(callback: CallbackQuery):
    """Меню пополнения баланса"""
    text = (
        "💵 <b>Пополнение баланса</b>\n\n"
        "Выберите способ пополнения:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏦 ЮKassa", callback_data="topup:yookassa")],
        [InlineKeyboardButton(text="₿ Криптовалюта", callback_data="topup:crypto")],
        [InlineKeyboardButton(text="🤖 CryptoBot", callback_data="topup:cryptobot")],
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="topup:stars")]
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


# ========== TELEGRAM STARS PAYMENT HANDLERS ==========

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: types.PreCheckoutQuery):
    """
    Обработчик перед оплатой через Stars
    Подтверждаем, что можем принять платёж
    """
    try:
        payment_id = int(pre_checkout_query.invoice_payload)

        # Проверяем существование платежа
        payment = db.get_payment(payment_id)

        if not payment:
            await pre_checkout_query.answer(ok=False, error_message="Платеж не найден")
            return

        if payment['status'] == 'completed':
            await pre_checkout_query.answer(ok=False, error_message="Платеж уже обработан")
            return

        # Всё ок, подтверждаем
        await pre_checkout_query.answer(ok=True)

        logger.info(f"[STARS] Pre-checkout OK для платежа #{payment_id}")

    except Exception as e:
        logger.error(f"[STARS] Ошибка pre-checkout: {e}")
        await pre_checkout_query.answer(ok=False, error_message="Внутренняя ошибка")


@router.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    """
    Обработчик успешной оплаты через Stars
    Активирует подписку после оплаты
    """
    try:
        user_id = message.from_user.id
        successful_payment = message.successful_payment

        payment_id = int(successful_payment.invoice_payload)
        stars_paid = successful_payment.total_amount

        logger.info(f"[STARS] Успешная оплата #{payment_id} от пользователя {user_id} на {stars_paid} Stars")

        # Получаем информацию о платеже
        payment = db.get_payment(payment_id)

        if not payment:
            await message.answer("❌ Ошибка: платеж не найден")
            return

        if payment['status'] == 'completed':
            await message.answer("✅ Этот платёж уже был обработан")
            return

        # Обновляем статус платежа
        db.update_payment_status(payment_id, "completed", successful_payment.telegram_payment_charge_id)

        tariff_months = payment['tariff_months']
        tariff = TARIFFS[tariff_months]

        # Начисляем реферальный бонус
        referrer_id = db.get_user_referrer(user_id)
        if referrer_id:
            bonus_amount = payment['amount'] * REFERRAL_COMMISSION
            db.add_balance(referrer_id, bonus_amount, "referral", f"Реферальный бонус от платежа #{payment_id}", payment_id)

            # Отправляем уведомление рефереру
            from aiogram import Bot
            from config import TELEGRAM_BOT_TOKEN
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            try:
                await bot.send_message(
                    referrer_id,
                    f"💰 <b>Реферальный бонус!</b>\n\n"
                    f"Ваш реферал оплатил подписку.\n"
                    f"Вам начислено: <b>{bonus_amount:.2f}₽</b>",
                    parse_mode="HTML"
                )
            except:
                pass

        # Активируем подписку
        try:
            from utils.xui_api import create_or_extend_subscription
            from config import SUBSCRIPTION_URL

            client_uuid, vless_link, expiry_ts, traffic_bytes = create_or_extend_subscription(
                user_id,
                tariff_months,
                tariff['traffic_gb']
            )

            # Создаем запись о подписке в БД
            db.create_subscription(user_id, client_uuid, tariff_months, expiry_ts, traffic_bytes, payment_id)

            # Формируем ссылку на подписку
            subscription_link = f"{SUBSCRIPTION_URL}{client_uuid}"

            # Уведомляем пользователя об успешной оплате
            import datetime
            expiry_date = datetime.datetime.fromtimestamp(expiry_ts).strftime('%d.%m.%Y %H:%M')

            await message.answer(
                f"✅ <b>Оплата через Stars подтверждена!</b>\n\n"
                f"⭐ Оплачено: {stars_paid} Stars\n"
                f"📦 Тариф: {tariff_months} мес\n"
                f"📊 Трафик: {tariff['traffic_gb']} GB\n\n"
                f"✅ Подписка активирована до {expiry_date}\n\n"
                f"🔗 <b>Ссылка на подписку:</b>\n<code>{subscription_link}</code>\n\n"
                f"Скопируйте эту ссылку в приложение Happ или другой VPN-клиент.",
                parse_mode="HTML"
            )

            logger.info(f"[STARS] Платеж #{payment_id} завершён, подписка активирована")

        except Exception as e:
            logger.error(f"[STARS] Ошибка активации подписки: {e}")
            await message.answer(
                f"✅ <b>Оплата подтверждена!</b>\n\n"
                f"⚠️ Произошла ошибка при активации подписки. Обратитесь в поддержку.",
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"[STARS] Ошибка обработки successful_payment: {e}")
        await message.answer(
            "❌ Ошибка обработки платежа. Обратитесь в поддержку.",
            parse_mode="HTML"
        )
