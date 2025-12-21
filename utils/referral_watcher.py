# utils/referral_watcher.py (можешь так назвать)
import sqlite3
import time
import logging
from config import DB_PATH

logger = logging.getLogger("referral_watcher")

async def check_referral_usage(bot, xui_client):
    """
    1. Смотрим, какие trial-клиенты появились/подключились в X-UI
    2. Понимаем их телеграм-id из email
    3. Если у них был реферер – даём рефереру +7 дней и пытаемся продлить его в панели
    """
    # 1. берём список инбаундов
    r = xui_client.session.get(f"{xui_client.base_url}/inbounds/list", verify=False)
    if r.status_code != 200:
        logger.warning("[REF] Не удалось получить список инбаундов")
        return

    data = r.json()
    inbounds = data.get("obj", [])
    if not inbounds:
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for inbound in inbounds:
        inbound_id = inbound.get("id")
        settings_raw = inbound.get("settings", "{}")

        import json
        try:
            settings = json.loads(settings_raw)
        except Exception:
            settings = {}

        clients = settings.get("clients", [])
        for cl in clients:
            email = cl.get("email", "")
            # мы раньше в trial делали тип "trial_<tg_id>@..." – вот и проверяем
            if not email.startswith("trial_"):
                continue

            # достаем tg_id
            try:
                tg_id = int(email.split("@")[0].replace("trial_", ""))
            except ValueError:
                continue

            client_id = cl.get("id") or email  # хоть что-то уникальное

            # уже начисляли за этого клиента?
            cur.execute("SELECT 1 FROM referral_usage WHERE client_id = ?", (client_id,))
            if cur.fetchone():
                continue  # уже учли

            # отмечаем использование
            cur.execute(
                "INSERT INTO referral_usage (referrer_id, referred_id, client_id, used_at) VALUES (?, ?, ?, ?)",
                (None, tg_id, client_id, time.time())
            )
            conn.commit()

            # узнаем, кто его пригласил
            cur.execute("SELECT referrer_id FROM users WHERE user_id = ?", (tg_id,))
            row = cur.fetchone()
            if not row or not row[0]:
                continue  # пользователя никто не приглашал

            referrer_id = row[0]

            # добавляем 7 дней в БД
            cur.execute("UPDATE users SET bonus_days = bonus_days + 7 WHERE user_id = ?", (referrer_id,))
            conn.commit()

            # пытаемся продлить в панели
            extended = xui_client.extend_client_in_panel(
                inbound_id=inbound_id,
                client_email=f"trial_{referrer_id}@vpn.local",  # если ты иначе называешь – подправь!
                add_days=7,
                add_gb=15
            )

            # шлем уведомление
            if extended:
                text = "🎉 Ваш друг начал пользоваться VPN — мы продлили вам доступ на +7 дней и добавили 15GB трафика!"
            else:
                text = (
                    "🎉 Ваш друг начал пользоваться VPN — мы добавили вам +7 дней в вашем профиле.\n"
                    "⚠️ Но продлить в панели не удалось автоматически, напишите администратору, если срок в приложении не обновился."
                )

            try:
                await bot.send_message(referrer_id, text)
            except Exception as e:
                logger.warning(f"[REF] Не удалось отправить сообщение {referrer_id}: {e}")

    conn.close()
