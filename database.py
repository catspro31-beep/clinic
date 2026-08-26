import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "asr_shifo.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            telegram_id INTEGER PRIMARY KEY,
            full_name TEXT,
            phone_number TEXT,
            username TEXT,
            is_blocked INTEGER DEFAULT 0,
            warning_count INTEGER DEFAULT 0,
            chat_mode TEXT,
            registration_step TEXT,
            temp_name TEXT,
            temp_doctor TEXT,
            temp_appointment_time TEXT,
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            patient_name TEXT,
            service_name TEXT,
            appointment_date TEXT,
            appointment_time TEXT,
            reminded INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

    # Migratsiya: eski bazalarda yangi ustunlar bo'lmasligi mumkin
    conn = get_connection()
    cur = conn.cursor()
    for alter_sql in [
        "ALTER TABLE appointments ADD COLUMN status TEXT DEFAULT 'active'",
        "ALTER TABLE patients ADD COLUMN language TEXT DEFAULT 'uz'",
    ]:
        try:
            cur.execute(alter_sql)
            conn.commit()
        except sqlite3.OperationalError:
            pass
    conn.close()


def create_appointment(telegram_id, patient_name, service_name, appointment_date, appointment_time=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO appointments (telegram_id, patient_name, service_name, appointment_date, appointment_time) VALUES (?, ?, ?, ?, ?)",
        (telegram_id, patient_name, service_name, appointment_date, appointment_time)
    )
    conn.commit()
    appointment_id = cur.lastrowid
    conn.close()
    return appointment_id


def get_queue_position(service_name, appointment_date, appointment_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) as cnt FROM appointments WHERE service_name = ? AND appointment_date = ? AND id <= ? AND status = 'active'",
        (service_name, appointment_date, appointment_id)
    )
    position = cur.fetchone()["cnt"]
    conn.close()
    return position


def get_previous_patient(service_name, appointment_date, appointment_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT patient_name FROM appointments WHERE service_name = ? AND appointment_date = ? AND id < ? AND status = 'active' ORDER BY id DESC LIMIT 1",
        (service_name, appointment_date, appointment_id)
    )
    row = cur.fetchone()
    conn.close()
    return row["patient_name"] if row else None


def get_appointments_for_date_unreminded(date_str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM appointments WHERE appointment_date = ? AND reminded = 0",
        (date_str,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def mark_reminded(appointment_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE appointments SET reminded = 1 WHERE id = ?", (appointment_id,))
    conn.commit()
    conn.close()


def get_active_appointments_for_patient(telegram_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM appointments WHERE telegram_id = ? AND status = 'active' ORDER BY id DESC",
        (telegram_id,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def cancel_appointment_by_patient(telegram_id, appointment_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE appointments SET status = 'cancelled' WHERE id = ? AND telegram_id = ?",
        (appointment_id, telegram_id)
    )
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def get_appointments_for_date(date_str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.*, p.phone_number FROM appointments a
        LEFT JOIN patients p ON a.telegram_id = p.telegram_id
        WHERE a.appointment_date = ? AND a.status = 'active'
        ORDER BY a.id ASC
    """, (date_str,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_queue_counts_for_date(date_str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT service_name, COUNT(*) as cnt FROM appointments
        WHERE appointment_date = ? AND status = 'active'
        GROUP BY service_name
    """, (date_str,))
    result = {row["service_name"]: row["cnt"] for row in cur.fetchall()}
    conn.close()
    return result


def get_all_appointments_export():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, a.patient_name, a.service_name, a.appointment_date, a.appointment_time,
               a.status, p.phone_number, p.username
        FROM appointments a
        LEFT JOIN patients p ON a.telegram_id = p.telegram_id
        ORDER BY a.id ASC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def set_language(telegram_id, lang):
    update_patient(telegram_id, language=lang)


def get_language(telegram_id):
    p = get_patient(telegram_id)
    return p.get("language", "uz") if p else "uz"


def get_patient(telegram_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM patients WHERE telegram_id = ?", (telegram_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_or_create_patient(telegram_id, username=None):
    patient = get_patient(telegram_id)
    if patient:
        return patient
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO patients (telegram_id, username) VALUES (?, ?)",
        (telegram_id, username)
    )
    conn.commit()
    conn.close()
    return get_patient(telegram_id)


def update_patient(telegram_id, **fields):
    if not fields:
        return
    conn = get_connection()
    cur = conn.cursor()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [telegram_id]
    cur.execute(f"UPDATE patients SET {set_clause} WHERE telegram_id = ?", values)
    conn.commit()
    conn.close()


def get_chat_mode(telegram_id):
    p = get_patient(telegram_id)
    return p["chat_mode"] if p else None


def set_chat_mode(telegram_id, mode):
    update_patient(telegram_id, chat_mode=mode)


def is_blocked(telegram_id):
    p = get_patient(telegram_id)
    return bool(p and p["is_blocked"])


def add_warning(telegram_id):
    p = get_patient(telegram_id)
    count = (p["warning_count"] if p else 0) + 1
    update_patient(telegram_id, warning_count=count)
    return count


def block_patient(telegram_id):
    update_patient(telegram_id, is_blocked=1)


def log_history(telegram_id, message):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO history (telegram_id, message) VALUES (?, ?)",
        (telegram_id, message)
    )
    conn.commit()
    conn.close()


def get_history(telegram_id, limit=20):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM history WHERE telegram_id = ? ORDER BY id DESC LIMIT ?",
        (telegram_id, limit)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_all_patient_ids():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT telegram_id FROM patients WHERE is_blocked = 0")
    rows = [r["telegram_id"] for r in cur.fetchall()]
    conn.close()
    return rows


def get_stats():
    conn = get_connection()
    cur = conn.cursor()
    stats = {}

    cur.execute("SELECT COUNT(*) as cnt FROM patients")
    stats["total_patients"] = cur.fetchone()["cnt"]

    cur.execute("SELECT COUNT(*) as cnt FROM patients WHERE is_blocked = 1")
    stats["blocked"] = cur.fetchone()["cnt"]

    today_str = datetime.now().strftime("%Y-%m-%d")
    cur.execute("SELECT COUNT(*) as cnt FROM appointments WHERE appointment_date = ?", (today_str,))
    stats["today_appointments"] = cur.fetchone()["cnt"]

    cur.execute("SELECT COUNT(*) as cnt FROM appointments")
    stats["total_appointments"] = cur.fetchone()["cnt"]

    cur.execute("""
        SELECT service_name, COUNT(*) as cnt FROM appointments
        WHERE appointment_date = ?
        GROUP BY service_name ORDER BY cnt DESC
    """, (today_str,))
    stats["today_by_service"] = [dict(r) for r in cur.fetchall()]

    conn.close()
    return stats
