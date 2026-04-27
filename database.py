"""
Datenbank-Modul: Turso (libsql) wenn TURSO_DATABASE_URL gesetzt, sonst SQLite (lokal).
"""
import os
import json
import logging
from pathlib import Path
from crypto import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

TURSO_URL = os.getenv("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")
DB_PATH = Path(__file__).parent / "data" / "users.db"

AVAILABLE_SPORTS = [
    "laufen", "radfahren", "bouldern", "seilklettern",
    "schwimmen", "krafttraining", "crossfit", "yoga", "meditation", "faszienrolle",
]

# ── Connection-Layer ───────────────────────────────────────────────────

_USE_TURSO = bool(TURSO_URL and TURSO_TOKEN)

if _USE_TURSO:
    import libsql_experimental as libsql
    logger.info("Turso-Modus (persistent)")
else:
    import sqlite3
    logger.info("SQLite-Modus (lokal)")


def _conn():
    if _USE_TURSO:
        conn = libsql.connect("training-coach.db", sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
        conn.sync()
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def _execute(conn, sql, params=()):
    """Führt SQL aus. SQLite-Syntax für beide (Turso ist SQLite-kompatibel)."""
    sql = sql.replace("BIGINT", "INTEGER")
    sql = sql.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
    sql = sql.replace("TIMESTAMP DEFAULT NOW()", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    return conn.execute(sql, params)


def _sync(conn):
    """Synct Turso-Verbindung wenn nötig."""
    if _USE_TURSO:
        conn.sync()


def _fetchone(conn, sql, params=()):
    cur = _execute(conn, sql, params)
    row = cur.fetchone()
    if row is None:
        return None
    if _USE_TURSO:
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))
    return dict(row)


def _fetchall(conn, sql, params=()):
    cur = _execute(conn, sql, params)
    rows = cur.fetchall()
    if _USE_TURSO:
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, r)) for r in rows]
    return [dict(r) for r in rows]


# ── Schema-Initialisierung ─────────────────────────────────────────────

def init_db():
    conn = _conn()
    try:
        _execute(conn, """CREATE TABLE IF NOT EXISTS users (
            chat_id BIGINT PRIMARY KEY,
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
            strava_token_expires BIGINT DEFAULT 0,
            city TEXT DEFAULT 'Hannover',
            plz TEXT DEFAULT '',
            umkreis INTEGER DEFAULT 20,
            setup_complete INTEGER DEFAULT 0,
            setup_step TEXT DEFAULT 'privacy',
            extra_notes TEXT DEFAULT '',
            suunto_access_token TEXT DEFAULT '',
            suunto_refresh_token TEXT DEFAULT '',
            suunto_token_expires BIGINT DEFAULT 0,
            suunto_username TEXT DEFAULT '',
            privacy_accepted INTEGER DEFAULT 0,
            injuries TEXT DEFAULT '',
            competition_date TEXT DEFAULT '',
            competition_name TEXT DEFAULT ''
        )""")

        _execute(conn, """CREATE TABLE IF NOT EXISTS training_logs (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT,
            week_start TEXT,
            data_json TEXT,
            plan_json TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )""")

        _execute(conn, """CREATE TABLE IF NOT EXISTS suunto_sleep_logs (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT,
            date TEXT,
            deep_sleep_min REAL,
            light_sleep_min REAL,
            rem_sleep_min REAL,
            hr_avg INTEGER,
            hr_min INTEGER,
            sleep_quality_score INTEGER,
            avg_hrv REAL,
            created_at TIMESTAMP DEFAULT NOW()
        )""")

        _execute(conn, """CREATE TABLE IF NOT EXISTS suunto_recovery_logs (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT,
            date TEXT,
            balance REAL,
            stress_state INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        )""")

        _execute(conn, """CREATE TABLE IF NOT EXISTS suunto_webhook_workouts (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT,
            workout_key TEXT,
            sport TEXT,
            duration_sec INTEGER,
            distance_m REAL,
            hr_avg INTEGER,
            hr_max INTEGER,
            ascent_m REAL,
            descent_m REAL,
            created_at TIMESTAMP DEFAULT NOW()
        )""")

        _execute(conn, """CREATE TABLE IF NOT EXISTS conversation_history (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )""")

        _execute(conn, """CREATE TABLE IF NOT EXISTS feedback (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT,
            text TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )""")

        logger.info("Datenbank initialisiert.")
        _sync(conn)
    finally:
        conn.close()


# ── User-Funktionen ───────────────────────────────────────────────────

def get_user(chat_id: int) -> dict | None:
    conn = _conn()
    try:
        row = _fetchone(conn, "SELECT * FROM users WHERE chat_id = ?", (chat_id,))
        if row:
            row["sports"] = json.loads(row.get("sports", "[]"))
            return row
        return None
    finally:
        conn.close()


def create_user(chat_id: int):
    conn = _conn()
    try:
        _execute(conn, "INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (chat_id,))
        _sync(conn)
    finally:
        conn.close()


_ALLOWED_USER_COLUMNS = {
    "name", "sports", "kraft_fokus", "has_dog", "dog_name", "has_hangboard",
    "watch", "data_source", "strava_access_token", "strava_refresh_token",
    "strava_token_expires", "city", "plz", "umkreis", "setup_complete",
    "setup_step", "extra_notes", "suunto_access_token", "suunto_refresh_token",
    "suunto_token_expires", "suunto_username", "privacy_accepted",
    "injuries", "competition_date", "competition_name",
}


def update_user(chat_id: int, **kwargs):
    conn = _conn()
    try:
        for key, val in kwargs.items():
            if key not in _ALLOWED_USER_COLUMNS:
                logger.warning(f"update_user: ungültiger Spaltenname '{key}' ignoriert")
                continue
            if key == "sports":
                val = json.dumps(val)
            _execute(conn, f"UPDATE users SET {key} = ? WHERE chat_id = ?", (val, chat_id))
        _sync(conn)
    finally:
        conn.close()


# ── Training Logs ──────────────────────────────────────────────────────

def save_training_log(chat_id: int, week_start: str, data: str, plan: str):
    conn = _conn()
    try:
        _execute(conn, "INSERT INTO training_logs (chat_id, week_start, data_json, plan_json) VALUES (?, ?, ?, ?)",
                 (chat_id, week_start, data, plan))
        _sync(conn)
    finally:
        conn.close()


def get_recent_logs(chat_id: int, limit: int = 4) -> list[dict]:
    conn = _conn()
    try:
        return _fetchall(conn, "SELECT * FROM training_logs WHERE chat_id = ? ORDER BY created_at DESC LIMIT ?",
                         (chat_id, limit))
    finally:
        conn.close()


def get_community_insights(limit: int = 20) -> list[dict]:
    conn = _conn()
    try:
        return _fetchall(conn, "SELECT data_json, plan_json FROM training_logs ORDER BY created_at DESC LIMIT ?",
                         (limit,))
    finally:
        conn.close()


# ── Suunto Tokens ──────────────────────────────────────────────────────

def save_suunto_tokens(chat_id: int, token_data: dict):
    conn = _conn()
    try:
        if _USE_PG:
            _execute(conn, """UPDATE users SET suunto_access_token = %s, suunto_refresh_token = %s,
                suunto_token_expires = %s, suunto_username = %s WHERE chat_id = %s""",
                     (encrypt_token(token_data.get("access_token", "")),
                      encrypt_token(token_data.get("refresh_token", "")),
                      token_data.get("expires_at", 0), token_data.get("username", ""), chat_id))
        else:
            _execute(conn, """UPDATE users SET suunto_access_token = ?, suunto_refresh_token = ?,
                suunto_token_expires = ?, suunto_username = ? WHERE chat_id = ?""",
                     (encrypt_token(token_data.get("access_token", "")),
                      encrypt_token(token_data.get("refresh_token", "")),
                      token_data.get("expires_at", 0), token_data.get("username", ""), chat_id))
    finally:
        conn.close()


def get_suunto_tokens(chat_id: int) -> dict | None:
    conn = _conn()
    try:
        row = _fetchone(conn, "SELECT suunto_access_token, suunto_refresh_token, suunto_token_expires, suunto_username FROM users WHERE chat_id = ?", (chat_id,))
        if not row or not row.get("suunto_access_token"):
            return None
        row["suunto_access_token"] = decrypt_token(row["suunto_access_token"])
        row["suunto_refresh_token"] = decrypt_token(row["suunto_refresh_token"])
        return row
    finally:
        conn.close()


# ── Suunto Sleep/Recovery/Workouts ─────────────────────────────────────

def save_suunto_sleep(chat_id: int, sleep_data: dict):
    conn = _conn()
    try:
        _execute(conn, """INSERT INTO suunto_sleep_logs (chat_id, date, deep_sleep_min, light_sleep_min, rem_sleep_min, hr_avg, hr_min, sleep_quality_score, avg_hrv) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                 (chat_id, sleep_data.get("date", ""), sleep_data.get("deep_sleep_min", 0), sleep_data.get("light_sleep_min", 0), sleep_data.get("rem_sleep_min", 0), sleep_data.get("hr_avg", 0), sleep_data.get("hr_min", 0), sleep_data.get("sleep_quality_score", 0), sleep_data.get("avg_hrv", 0)))
    finally:
        conn.close()


def save_suunto_recovery(chat_id: int, recovery_data: dict):
    conn = _conn()
    try:
        _execute(conn, "INSERT INTO suunto_recovery_logs (chat_id, date, balance, stress_state) VALUES (?, ?, ?, ?)",
                 (chat_id, recovery_data.get("date", ""), recovery_data.get("balance", 0), recovery_data.get("stress_state", 0)))
    finally:
        conn.close()


def save_suunto_webhook_workout(chat_id: int, workout_data: dict):
    conn = _conn()
    try:
        _execute(conn, """INSERT INTO suunto_webhook_workouts (chat_id, workout_key, sport, duration_sec, distance_m, hr_avg, hr_max, ascent_m, descent_m) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                 (chat_id, workout_data.get("workout_key", ""), workout_data.get("sport", ""), workout_data.get("duration_sec", 0), workout_data.get("distance_m", 0), workout_data.get("hr_avg", 0), workout_data.get("hr_max", 0), workout_data.get("ascent_m", 0), workout_data.get("descent_m", 0)))
    finally:
        conn.close()


def get_recent_suunto_sleep(chat_id: int, days: int = 7) -> list[dict]:
    conn = _conn()
    try:
        if _USE_PG:
            return _fetchall(conn, "SELECT * FROM suunto_sleep_logs WHERE chat_id = %s AND created_at >= NOW() - INTERVAL '%s days' ORDER BY date DESC", (chat_id, days))
        else:
            return _fetchall(conn, "SELECT * FROM suunto_sleep_logs WHERE chat_id = ? AND created_at >= datetime('now', ? || ' days') ORDER BY date DESC", (chat_id, -days))
    finally:
        conn.close()


def get_recent_suunto_recovery(chat_id: int, days: int = 7) -> list[dict]:
    conn = _conn()
    try:
        if _USE_PG:
            return _fetchall(conn, "SELECT * FROM suunto_recovery_logs WHERE chat_id = %s AND created_at >= NOW() - INTERVAL '%s days' ORDER BY date DESC", (chat_id, days))
        else:
            return _fetchall(conn, "SELECT * FROM suunto_recovery_logs WHERE chat_id = ? AND created_at >= datetime('now', ? || ' days') ORDER BY date DESC", (chat_id, -days))
    finally:
        conn.close()


def get_chat_id_by_suunto_username(username: str) -> int | None:
    conn = _conn()
    try:
        row = _fetchone(conn, "SELECT chat_id FROM users WHERE suunto_username = ?", (username,))
        return row["chat_id"] if row else None
    finally:
        conn.close()


# ── GDPR ───────────────────────────────────────────────────────────────

def delete_user_data(chat_id: int):
    conn = _conn()
    try:
        for table in ["suunto_webhook_workouts", "suunto_sleep_logs", "suunto_recovery_logs", "training_logs", "conversation_history", "feedback", "users"]:
            _execute(conn, f"DELETE FROM {table} WHERE chat_id = ?", (chat_id,))
        logger.info(f"Alle Daten für chat_id {chat_id} gelöscht (GDPR)")
    finally:
        conn.close()


def export_user_data(chat_id: int) -> dict:
    conn = _conn()
    try:
        user = _fetchone(conn, "SELECT * FROM users WHERE chat_id = ?", (chat_id,))
        if not user:
            return {}
        user["sports"] = json.loads(user.get("sports", "[]"))
        for key in ["strava_access_token", "strava_refresh_token", "suunto_access_token", "suunto_refresh_token"]:
            user.pop(key, None)
        logs = _fetchall(conn, "SELECT week_start, data_json, plan_json, created_at FROM training_logs WHERE chat_id = ? ORDER BY created_at DESC", (chat_id,))
        sleep = _fetchall(conn, "SELECT date, deep_sleep_min, light_sleep_min, rem_sleep_min, hr_avg, hr_min, sleep_quality_score, avg_hrv, created_at FROM suunto_sleep_logs WHERE chat_id = ? ORDER BY date DESC", (chat_id,))
        recovery = _fetchall(conn, "SELECT date, balance, stress_state, created_at FROM suunto_recovery_logs WHERE chat_id = ? ORDER BY date DESC", (chat_id,))
        return {"profil": user, "training_logs": logs, "schlaf_daten": sleep, "recovery_daten": recovery}
    finally:
        conn.close()


# ── Conversation History ───────────────────────────────────────────────

def save_conversation_messages(chat_id: int, messages: list[dict]):
    conn = _conn()
    try:
        _execute(conn, "DELETE FROM conversation_history WHERE chat_id = ?", (chat_id,))
        for msg in messages:
            _execute(conn, "INSERT INTO conversation_history (chat_id, role, content) VALUES (?, ?, ?)",
                     (chat_id, msg["role"], msg["content"]))
    finally:
        conn.close()


def load_conversation_history(chat_id: int, limit: int = 20) -> list[dict]:
    conn = _conn()
    try:
        rows = _fetchall(conn, "SELECT role, content FROM conversation_history WHERE chat_id = ? ORDER BY id DESC LIMIT ?", (chat_id, limit))
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    finally:
        conn.close()


def clear_conversation_history(chat_id: int):
    conn = _conn()
    try:
        _execute(conn, "DELETE FROM conversation_history WHERE chat_id = ?", (chat_id,))
    finally:
        conn.close()


# ── Sonstige ───────────────────────────────────────────────────────────

def get_all_active_users() -> list[dict]:
    conn = _conn()
    try:
        return _fetchall(conn, "SELECT chat_id, name FROM users WHERE setup_complete = 1")
    finally:
        conn.close()


def save_feedback(chat_id: int, feedback: str):
    conn = _conn()
    try:
        _execute(conn, "INSERT INTO feedback (chat_id, text) VALUES (?, ?)", (chat_id, feedback))
    finally:
        conn.close()


def find_training_partners(chat_id: int, plz: str, sports: list[str], limit: int = 5) -> list[dict]:
    conn = _conn()
    try:
        rows = _fetchall(conn, "SELECT chat_id, name, sports, plz FROM users WHERE setup_complete = 1 AND chat_id != ? AND plz != ''", (chat_id,))
        matches = []
        for row in rows:
            row["sports"] = json.loads(row.get("sports", "[]"))
            if plz and row.get("plz", "")[:2] == plz[:2]:
                common = set(sports) & set(row["sports"])
                if common:
                    row["common_sports"] = list(common)
                    matches.append(row)
                    if len(matches) >= limit:
                        break
        return matches
    finally:
        conn.close()


def get_plan_streak(chat_id: int) -> int:
    conn = _conn()
    try:
        rows = _fetchall(conn, "SELECT week_start FROM training_logs WHERE chat_id = ? ORDER BY created_at DESC", (chat_id,))
        if not rows:
            return 0
        from datetime import datetime
        streak = 1
        prev = None
        for row in rows:
            try:
                ws = row["week_start"]
                dt = datetime.fromisoformat(ws.replace("Z", "+00:00")).replace(tzinfo=None) if "T" in ws else datetime.strptime(ws, "%Y-%m-%d")
            except (ValueError, TypeError):
                continue
            if prev is None:
                prev = dt
                continue
            diff = (prev - dt).days
            if 5 <= diff <= 9:
                streak += 1
                prev = dt
            else:
                break
        return streak
    finally:
        conn.close()


def get_monthly_summary(chat_id: int) -> dict | None:
    from datetime import datetime
    conn = _conn()
    try:
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if _USE_PG:
            rows = _fetchall(conn, "SELECT data_json, plan_json, created_at FROM training_logs WHERE chat_id = %s AND created_at >= %s ORDER BY created_at", (chat_id, month_start))
        else:
            rows = _fetchall(conn, "SELECT data_json, plan_json, created_at FROM training_logs WHERE chat_id = ? AND created_at >= ? ORDER BY created_at", (chat_id, month_start.isoformat()))
        if not rows:
            return None
        from estimator import parse_metrics_from_text
        all_tss = []
        for row in rows:
            metrics = parse_metrics_from_text(row.get("data_json", ""))
            if metrics.get("tss"):
                all_tss.append(metrics["tss"])
        return {
            "monat": now.strftime("%B %Y"),
            "anzahl_plaene": len(rows),
            "total_tss": round(sum(all_tss), 1) if all_tss else 0,
            "avg_tss": round(sum(all_tss) / len(all_tss), 1) if all_tss else 0,
        }
    finally:
        conn.close()
