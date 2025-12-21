import sqlite3
import logging
import time
from config import DB_PATH

logger = logging.getLogger("db")

# ---------- Инициализация базы ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            created_at REAL DEFAULT (strftime('%s','now')),
            referrer_id INTEGER DEFAULT NULL,
            bonus_days INTEGER DEFAULT 0
        )
    """)

    # Таблица использования рефералов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS referral_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            client_id TEXT,
            used_at REAL
        )
    """)

    # Таблица запросов на доступ
    cur.execute("""
        CREATE TABLE IF NOT EXISTS access_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            full_name TEXT,
            comment TEXT,
            status TEXT DEFAULT 'pending',
            created_at REAL DEFAULT (strftime('%s','now')),
            processed_at REAL,
            processed_by INTEGER,
            client_uuid TEXT,
            sub_id TEXT
        )
    """)

    conn.commit()
    conn.close()
    logger.info("[DB] ✅ Таблицы успешно инициализированы.")


# ---------- Служебные функции ----------
def ensure_columns():
    """Добавляем недостающие колонки, если база старая."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # список нужных полей и их типов для таблицы users
    required_fields = {
        "referrer_id": "INTEGER DEFAULT NULL",
        "bonus_days": "INTEGER DEFAULT 0"
    }

    # получаем существующие поля таблицы users
    cur.execute("PRAGMA table_info(users)")
    existing = [r[1] for r in cur.fetchall()]

    for field, definition in required_fields.items():
        if field not in existing:
            cur.execute(f"ALTER TABLE users ADD COLUMN {field} {definition}")
            logger.info(f"[DB] ➕ Добавлено новое поле {field} в таблицу users")

    # Проверяем колонку comment в access_requests
    cur.execute("PRAGMA table_info(access_requests)")
    existing_ar = [r[1] for r in cur.fetchall()]
    if "comment" not in existing_ar:
        cur.execute("ALTER TABLE access_requests ADD COLUMN comment TEXT")
        logger.info("[DB] ➕ Добавлено новое поле comment в таблицу access_requests")

    conn.commit()
    conn.close()


# ---------- Работа с пользователями ----------
def ensure_user_row(user_id: int, username: str, full_name: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (user_id, username, full_name, created_at) VALUES (?, ?, ?, ?)",
            (user_id, username, full_name, time.time())
        )
        conn.commit()
        logger.info(f"[DB] ➕ Добавлен новый пользователь {user_id}")

    conn.close()


def add_referrer(user_id: int, referrer_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET referrer_id = ? WHERE user_id = ?", (referrer_id, user_id))
    conn.commit()
    conn.close()
    logger.info(f"[DB] 🔗 Пользователь {user_id} привязан к рефереру {referrer_id}")


def get_user_referrer(user_id: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
        result = cur.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"[DB] Ошибка при вызове get_user_referrer: {e}")
        return None


def add_referral_bonus(user_id: int, days: int = 7):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET bonus_days = bonus_days + ? WHERE user_id = ?", (days, user_id))
    conn.commit()
    conn.close()
    logger.info(f"[DB] 🎁 Пользователю {user_id} добавлено {days} бонусных дней")


# ---------- Работа с usage ----------
def add_referral_usage(referrer_id: int, referred_id: int, client_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO referral_usage (referrer_id, referred_id, client_id, used_at) VALUES (?, ?, ?, ?)",
        (referrer_id, referred_id, client_id, time.time())
    )
    conn.commit()
    conn.close()
    logger.info(f"[DB] 📈 Добавлена запись о реферале {referred_id} → {referrer_id}")


# ---------- Утилита для обновления бонусов ----------
def get_bonus_days(user_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT bonus_days FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else 0


# ---------- Работа с запросами на доступ ----------
def create_access_request(user_id: int, username: str, full_name: str, comment: str = "") -> int:
    """Создает запрос на доступ, возвращает ID запроса"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO access_requests (user_id, username, full_name, comment, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
        (user_id, username, full_name, comment, time.time())
    )
    request_id = cur.lastrowid
    conn.commit()
    conn.close()
    logger.info(f"[DB] 📝 Создан запрос на доступ #{request_id} от {user_id}")
    return request_id


def get_access_request(request_id: int) -> dict:
    """Получает информацию о запросе"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM access_requests WHERE id = ?", (request_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_pending_request_by_user(user_id: int) -> dict:
    """Проверяет, есть ли у пользователя ожидающий запрос"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM access_requests WHERE user_id = ? AND status = 'pending'", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_approved_request_by_user(user_id: int) -> dict:
    """Проверяет, есть ли у пользователя одобренный запрос (уже есть доступ)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM access_requests WHERE user_id = ? AND status = 'approved' ORDER BY id DESC LIMIT 1", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def approve_access_request(request_id: int, admin_id: int, client_uuid: str, sub_id: str) -> bool:
    """Одобряет запрос на доступ"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "UPDATE access_requests SET status = 'approved', processed_at = ?, processed_by = ?, client_uuid = ?, sub_id = ? WHERE id = ?",
        (time.time(), admin_id, client_uuid, sub_id, request_id)
    )
    conn.commit()
    success = cur.rowcount > 0
    conn.close()
    if success:
        logger.info(f"[DB] ✅ Запрос #{request_id} одобрен админом {admin_id}")
    return success


def reject_access_request(request_id: int, admin_id: int) -> bool:
    """Отклоняет запрос на доступ"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "UPDATE access_requests SET status = 'rejected', processed_at = ?, processed_by = ? WHERE id = ?",
        (time.time(), admin_id, request_id)
    )
    conn.commit()
    success = cur.rowcount > 0
    conn.close()
    if success:
        logger.info(f"[DB] ❌ Запрос #{request_id} отклонён админом {admin_id}")
    return success


# ---------- Инициализация при запуске ----------
try:
    init_db()
    ensure_columns()
except Exception as e:
    logger.error(f"[DB] ❌ Ошибка инициализации: {e}")
