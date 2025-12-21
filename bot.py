import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import TELEGRAM_BOT_TOKEN
from utils.db import init_db

# Handlers
from handlers.menu import router as menu_router
from handlers.access_request import router as access_router
from handlers.trial import router as trial_router
from handlers.partner import router as partner_router
from handlers.check_vpn import router as checkvpn_router
from handlers.payments import router as payments_router
from handlers.help import router as help_router
from handlers.admin import router as admin_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# регистрируем все роутеры
dp.include_router(menu_router)
dp.include_router(access_router)
dp.include_router(trial_router)
dp.include_router(partner_router)
dp.include_router(checkvpn_router)
dp.include_router(payments_router)
dp.include_router(help_router)
dp.include_router(admin_router)

from utils.xui_api import XUIClient, check_referral_usage
import asyncio

async def start_referral_watcher(bot):
    xui = XUIClient()
    if not xui.login():
        logger.warning("[REF] Не удалось авторизоваться в XUI для отслеживания")
        return

    while True:
        await check_referral_usage(bot, xui)
        await asyncio.sleep(600)  # проверять каждые 10 минут

async def main():
    # база (пользователи, балансы, страйки, и т.д.)
    init_db()
    asyncio.create_task(start_referral_watcher(bot))

    me = await bot.get_me()
    logging.info(f"🚀 Bot started as @{me.username}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
