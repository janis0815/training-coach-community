import sqlite3
import json
import logging
from pathlib import Path
from crypto import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "data" / "users.db"

AVAILABLE_SPORTS = [
    "laufen", "radfahren", "bouldern", "seilklettern",
    "schwimmen", "krafttraining", "yoga", "meditation", "faszienrolle",
]


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            name TEXT,
            sports TEXT DEFAULT '[]',
            kraft_fokus TEXT DEFAULT '',
            has_dog INTEGER DEFAULT 0,
            dog_name TEXT DEFAULT '',
            has_hangboard INTEGER DEFAULT 0,
            watch TEXT DEFAULT 'manuell',
            data_source TEXT DEFAULT 'manuell',
            strava_access_token TEXT DEFAULT '',
            strava_refresh_token TEXT DEFAULT '',
            strava_token_expires INTEGER DEFAULT 0,
            city TEXT DEFAULT 'Hannover',
            plz TEXT DEFAULT '',
            umkreis INTEGER DEFAULT 20,
            setup_complete INTEGER DEFAULT 0,
            setup_step TEXT DEFAULT 'privacy',
            extra_notes TEXT DEFAULT ''
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS training_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            week_start TEXT,
            data_json TEXT,
            plan_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES users(chat_id)
        )""")

        # --- Suunto: migrate users table (safe for existing DBs) ---
        for col, typedef in [
            ("suunto_access_token", "TEXT DEFAULT ''"),
            ("suunto_refresh_token", "TEXT DEFAULT ''"),
            ("suunto_token_expires", "INTEGER DEFAULT 0"),
            ("suunto_username", "TEXT DEFAULT ''"),
            ("privacy_accepted", "INTEGER DEFAULT 0"),
            ("injuries", "TEXT DEFAULT ''"),
            ("competition_date", "TEXT DEFAULT ''"),
            ("competition_name", "TEXT DEFAULT ''"),
        ]:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass  # column already exists

        # --- Suunto: new tables ---
        c.execute("""CREATE TABLE IF NOT EXISTS suunto_sleep_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            date TEXT,
            deep_sleep_min REAL,
            light_sleep_min REAL,
            rem_sleep_min REAL,
            hr_avg INTEGER,
            hr_min INTEGER,
            sleep_quality_score INTEGER,
            avg_hrv REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES users(chat_id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS suunto_recovery_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            date TEXT,
            balance REAL,
            stress_state INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES users(chat_id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS suunto_webhook_workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            workout_key TEXT,
            sport TEXT,
            duration_sec INTEGER,
            distance_m REAL,
            hr_avg INTEGER,
            hr_max INTEGER,
            ascent_m REAL,
            descent_m REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES users(chat_id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES users(chat_id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES users(chat_id)
        )""")


def get_user(chat_id: int) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
        if row:
            d = dict(row)
            d["sports"] = json.loads(d["sports"])
            return d
    return None


def create_user(chat_id: int):
    with _conn() as c:
        c.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (chat_id,))


# Erlaubte Spalten für update_user (Whitelist gegen SQL Injection)
_ALLOWED_USER_COLUMNS = {
    "name", "sports", "kraft_fokus", "has_dog", "dog_name", "has_hangboard",
    "watch", "data_source", "strava_access_token", "strava_refresh_token",
    "strava_token_expires", "city", "plz", "umkreis", "setup_complete",
    "setup_step", "extra_notes", "suunto_access_token", "suunto_refresh_token",
    "suunto_token_expires", "suunto_username", "privacy_accepted",
    "injuries", "competition_date", "competition_name",
}


def update_user(chat_id: int, **kwargs):
    with _conn() as c:
        for key, val in kwargs.items():
            if key not in _ALLOWED_USER_COLUMNS:
                logger.warning(f"update_user: ungültiger Spaltenname '{key}' ignoriert")
                continue
            if key == "sports":
                val = json.dumps(val)
            c.execute(f"UPDATE users SET {key} = ? WHERE chat_id = ?", (val, chat_id))


def save_training_log(chat_id: int, week_start: str, data: str, plan: str):
    with _conn() as c:
        c.execute(
            "INSERT INTO training_logs (chat_id, week_start, data_json, plan_json) VALUES (?, ?, ?, ?)",
            (chat_id, week_start, data, plan),
        )


def get_recent_logs(chat_id: int, limit: int = 4) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM training_logs WHERE chat_id = ? ORDER BY created_at DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_community_insights(limit: int = 20) -> list[dict]:
    """Holt anonymisierte Trainings-Logs aller User für Cross-Learning."""
    with _conn() as c:
        rows = c.execute(
            "SELECT data_json, plan_json FROM training_logs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Suunto database functions ──────────────────────────────────────────


def save_suunto_tokens(chat_id: int, token_data: dict):
    """Speichert Suunto OAuth-Tokens (verschlüsselt) für einen Benutzer."""
    with _conn() as c:
        c.execute(
            """UPDATE users SET
                suunto_access_token = ?,
                suunto_refresh_token = ?,
                suunto_token_expires = ?,
                suunto_username = ?
            WHERE chat_id = ?""",
            (
                encrypt_token(token_data.get("access_token", "")),
                encrypt_token(token_data.get("refresh_token", "")),
                token_data.get("expires_at", 0),
                token_data.get("username", ""),
                chat_id,
            ),
        )


def get_suunto_tokens(chat_id: int) -> dict | None:
    """Liest Suunto-Tokens für einen Benutzer. Gibt None zurück wenn nicht vorhanden."""
    with _conn() as c:
        row = c.execute(
            "SELECT suunto_access_token, suunto_refresh_token, suunto_token_expires, suunto_username "
            "FROM users WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        if not d["suunto_access_token"]:
            return None
        d["suunto_access_token"] = decrypt_token(d["suunto_access_token"])
        d["suunto_refresh_token"] = decrypt_token(d["suunto_refresh_token"])
        return d


def save_suunto_sleep(chat_id: int, sleep_data: dict):
    """Speichert einen Suunto-Schlaf-Datensatz."""
    with _conn() as c:
        c.execute(
            """INSERT INTO suunto_sleep_logs
                (chat_id, date, deep_sleep_min, light_sleep_min, rem_sleep_min,
                 hr_avg, hr_min, sleep_quality_score, avg_hrv)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                chat_id,
                sleep_data.get("date", ""),
                sleep_data.get("deep_sleep_min", 0),
                sleep_data.get("light_sleep_min", 0),
                sleep_data.get("rem_sleep_min", 0),
                sleep_data.get("hr_avg", 0),
                sleep_data.get("hr_min", 0),
                sleep_data.get("sleep_quality_score", 0),
                sleep_data.get("avg_hrv", 0),
            ),
        )


def save_suunto_recovery(chat_id: int, recovery_data: dict):
    """Speichert einen Suunto-Recovery-Datensatz."""
    with _conn() as c:
        c.execute(
            """INSERT INTO suunto_recovery_logs
                (chat_id, date, balance, stress_state)
            VALUES (?, ?, ?, ?)""",
            (
                chat_id,
                recovery_data.get("date", ""),
                recovery_data.get("balance", 0),
                recovery_data.get("stress_state", 0),
            ),
        )


def save_suunto_webhook_workout(chat_id: int, workout_data: dict):
    """Speichert ein via Webhook empfangenes Suunto-Workout."""
    with _conn() as c:
        c.execute(
            """INSERT INTO suunto_webhook_workouts
                (chat_id, workout_key, sport, duration_sec, distance_m,
                 hr_avg, hr_max, ascent_m, descent_m)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                chat_id,
                workout_data.get("workout_key", ""),
                workout_data.get("sport", ""),
                workout_data.get("duration_sec", 0),
                workout_data.get("distance_m", 0),
                workout_data.get("hr_avg", 0),
                workout_data.get("hr_max", 0),
                workout_data.get("ascent_m", 0),
                workout_data.get("descent_m", 0),
            ),
        )


def get_recent_suunto_sleep(chat_id: int, days: int = 7) -> list[dict]:
    """Liest die letzten N Tage Schlaf-Daten für einen Benutzer."""
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM suunto_sleep_logs WHERE chat_id = ? "
            "AND created_at >= datetime('now', ? || ' days') "
            "ORDER BY date DESC",
            (chat_id, -days),
        ).fetchall()
        return [dict(r) for r in rows]


def get_recent_suunto_recovery(chat_id: int, days: int = 7) -> list[dict]:
    """Liest die letzten N Tage Recovery-Daten für einen Benutzer."""
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM suunto_recovery_logs WHERE chat_id = ? "
            "AND created_at >= datetime('now', ? || ' days') "
            "ORDER BY date DESC",
            (chat_id, -days),
        ).fetchall()
        return [dict(r) for r in rows]


def get_chat_id_by_suunto_username(username: str) -> int | None:
    """Löst einen Suunto-Username zu einer chat_id auf."""
    with _conn() as c:
        row = c.execute(
            "SELECT chat_id FROM users WHERE suunto_username = ?",
            (username,),
        ).fetchone()
        return row["chat_id"] if row else None


# ── GDPR: Datenlöschung und -export ────────────────────────────────────


def delete_user_data(chat_id: int):
    """Löscht alle Daten eines Users (GDPR: Recht auf Vergessenwerden)."""
    with _conn() as c:
        c.execute("DELETE FROM suunto_webhook_workouts WHERE chat_id = ?", (chat_id,))
        c.execute("DELETE FROM suunto_sleep_logs WHERE chat_id = ?", (chat_id,))
        c.execute("DELETE FROM suunto_recovery_logs WHERE chat_id = ?", (chat_id,))
        c.execute("DELETE FROM training_logs WHERE chat_id = ?", (chat_id,))
        c.execute("DELETE FROM users WHERE chat_id = ?", (chat_id,))
    logger.info(f"Alle Daten für chat_id {chat_id} gelöscht (GDPR)")


def export_user_data(chat_id: int) -> dict:
    """Exportiert alle Daten eines Users als Dict (GDPR: Recht auf Datenportabilität)."""
    with _conn() as c:
        user_row = c.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
        if not user_row:
            return {}

        user = dict(user_row)
        user["sports"] = json.loads(user.get("sports", "[]"))
        # Tokens nicht exportieren
        for key in ["strava_access_token", "strava_refresh_token", "suunto_access_token", "suunto_refresh_token"]:
            user.pop(key, None)

        logs = c.execute(
            "SELECT week_start, data_json, plan_json, created_at FROM training_logs WHERE chat_id = ? ORDER BY created_at DESC",
            (chat_id,),
        ).fetchall()

        sleep = c.execute(
            "SELECT date, deep_sleep_min, light_sleep_min, rem_sleep_min, hr_avg, hr_min, sleep_quality_score, avg_hrv, created_at FROM suunto_sleep_logs WHERE chat_id = ? ORDER BY date DESC",
            (chat_id,),
        ).fetchall()

        recovery = c.execute(
            "SELECT date, balance, stress_state, created_at FROM suunto_recovery_logs WHERE chat_id = ? ORDER BY date DESC",
            (chat_id,),
        ).fetchall()

        return {
            "profil": user,
            "training_logs": [dict(r) for r in logs],
            "schlaf_daten": [dict(r) for r in sleep],
            "recovery_daten": [dict(r) for r in recovery],
        }


# ── Conversation History (persistent) ─────────────────────────────────


def save_conversation_messages(chat_id: int, messages: list[dict]):
    """Speichert Conversation-History für einen User (überschreibt bestehende)."""
    with _conn() as c:
        c.execute("DELETE FROM conversation_history WHERE chat_id = ?", (chat_id,))
        for msg in messages:
            c.execute(
                "INSERT INTO conversation_history (chat_id, role, content) VALUES (?, ?, ?)",
                (chat_id, msg["role"], msg["content"]),
            )


def load_conversation_history(chat_id: int, limit: int = 20) -> list[dict]:
    """Lädt die letzten N Conversation-Messages für einen User."""
    with _conn() as c:
        rows = c.execute(
            "SELECT role, content FROM conversation_history WHERE chat_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
        # Umkehren weil DESC sortiert
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def clear_conversation_history(chat_id: int):
    """Löscht die Conversation-History für einen User."""
    with _conn() as c:
        c.execute("DELETE FROM conversation_history WHERE chat_id = ?", (chat_id,))


def get_all_active_users() -> list[dict]:
    """Holt alle User mit abgeschlossenem Setup für Scheduled Reminders."""
    with _conn() as c:
        rows = c.execute(
            "SELECT chat_id, name FROM users WHERE setup_complete = 1"
        ).fetchall()
        return [dict(r) for r in rows]


def save_feedback(chat_id: int, feedback: str):
    """Speichert User-Feedback."""
    with _conn() as c:
        c.execute(
            "INSERT INTO feedback (chat_id, text) VALUES (?, ?)",
            (chat_id, feedback),
        )
