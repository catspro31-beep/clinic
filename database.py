import sqlite3
from datetime import datetime
from config import DB_PATH, TOTAL_ROOMS, ROOM_MIN_PRICE, ROOM_MAX_PRICE


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # Bemorlar jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            full_name TEXT,
            phone_number TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Shifokorlar jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            specialty TEXT NOT NULL,
            room_number TEXT,
            price INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Navbatlar (appointments) jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            reminded_24h INTEGER DEFAULT 0,
            reminded_1h INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients (id),
            FOREIGN KEY (doctor_id) REFERENCES doctors (id)
        )
    """)

    # To'lovlar jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            receipt_file_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (appointment_id) REFERENCES appointments (id)
        )
    """)

    # Xonalar jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT UNIQUE NOT NULL,
            price INTEGER NOT NULL
        )
    """)

    # Xona bandligi (bron qilish)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS room_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            booking_date TEXT NOT NULL,
            booking_time TEXT NOT NULL,
            status TEXT DEFAULT 'booked',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES rooms (id),
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        )
    """)

    # Qo'shimcha xizmatlar (stomatologiya, xijama, massaj - narxi kelishiladi)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        )
    """)

    conn.commit()

    # Shifokorlar (agar bo'sh bo'lsa)
    cur.execute("SELECT COUNT(*) as cnt FROM doctors")
    if cur.fetchone()["cnt"] == 0:
        sample_doctors = [
            ("Baxtiyor Akramjon", "Shifokor", "-", 50000),
            ("Qutbiddin", "Shifokor", "-", 50000),
        ]
        cur.executemany(
            "INSERT INTO doctors (full_name, specialty, room_number, price) VALUES (?, ?, ?, ?)",
            sample_doctors
        )
        conn.commit()

    # Xonalar (agar bo'sh bo'lsa) — 33 ta, 80,000 dan 150,000 gacha
    cur.execute("SELECT COUNT(*) as cnt FROM rooms")
    if cur.fetchone()["cnt"] == 0:
        import random
        rooms = []
        for i in range(1, TOTAL_ROOMS + 1):
            price = random.choice(range(ROOM_MIN_PRICE, ROOM_MAX_PRICE + 1, 10000))
            rooms.append((str(i), price))
        cur.executemany("INSERT INTO rooms (room_number, price) VALUES (?, ?)", rooms)
        conn.commit()

    # Xizmatlar (agar bo'sh bo'lsa) — narxi kelishiladi
    cur.execute("SELECT COUNT(*) as cnt FROM services")
    if cur.fetchone()["cnt"] == 0:
        sample_services = [
            ("Stomatologiya", "Narxi kelishiladi"),
            ("Xijama", "Narxi kelishiladi"),
            ("Massaj", "Narxi kelishiladi"),
        ]
        cur.executemany("INSERT INTO services (name, description) VALUES (?, ?)", sample_services)
        conn.commit()

    conn.close()


# ---------- Bemor funksiyalari ----------

def get_or_create_patient(telegram_id, full_name=None, phone_number=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM patients WHERE telegram_id = ?", (telegram_id,))
    patient = cur.fetchone()
    if patient is None:
        cur.execute(
            "INSERT INTO patients (telegram_id, full_name, phone_number) VALUES (?, ?, ?)",
            (telegram_id, full_name, phone_number)
        )
        conn.commit()
        cur.execute("SELECT * FROM patients WHERE telegram_id = ?", (telegram_id,))
        patient = cur.fetchone()
    conn.close()
    return dict(patient)


def update_patient_info(telegram_id, full_name=None, phone_number=None):
    conn = get_connection()
    cur = conn.cursor()
    if full_name:
        cur.execute("UPDATE patients SET full_name = ? WHERE telegram_id = ?", (full_name, telegram_id))
    if phone_number:
        cur.execute("UPDATE patients SET phone_number = ? WHERE telegram_id = ?", (phone_number, telegram_id))
    conn.commit()
    conn.close()


# ---------- Xonalar funksiyalari ----------

def get_all_rooms():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM rooms ORDER BY CAST(room_number AS INTEGER)")
    rooms = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rooms


def get_room_booking(room_id, date_str):
    """Shu kunga shu xona band qilinganmi, bo'lsa kim tomonidan"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT rb.*, p.full_name, p.telegram_id
        FROM room_bookings rb JOIN patients p ON rb.patient_id = p.id
        WHERE rb.room_id = ? AND rb.booking_date = ? AND rb.status != 'cancelled'
    """, (room_id, date_str))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def book_room(room_id, patient_id, date_str, time_str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO room_bookings (room_id, patient_id, booking_date, booking_time) VALUES (?, ?, ?, ?)",
        (room_id, patient_id, date_str, time_str)
    )
    conn.commit()
    booking_id = cur.lastrowid
    conn.close()
    return booking_id


def get_room_by_id(room_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM rooms WHERE id = ?", (room_id,))
    room = cur.fetchone()
    conn.close()
    return dict(room) if room else None


# ---------- Xizmatlar funksiyalari ----------

def get_all_services():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM services")
    services = [dict(r) for r in cur.fetchall()]
    conn.close()
    return services


# ---------- Shifokor funksiyalari ----------

def get_all_doctors():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM doctors WHERE is_active = 1")
    doctors = [dict(row) for row in cur.fetchall()]
    conn.close()
    return doctors


def get_doctor_by_id(doctor_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    doctor = cur.fetchone()
    conn.close()
    return dict(doctor) if doctor else None


def add_doctor(full_name, specialty, room_number, price):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO doctors (full_name, specialty, room_number, price) VALUES (?, ?, ?, ?)",
        (full_name, specialty, room_number, price)
    )
    conn.commit()
    doctor_id = cur.lastrowid
    conn.close()
    return doctor_id


def deactivate_doctor(doctor_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE doctors SET is_active = 0 WHERE id = ?", (doctor_id,))
    conn.commit()
    conn.close()


def get_stats():
    conn = get_connection()
    cur = conn.cursor()
    stats = {}

    cur.execute("SELECT COUNT(*) as cnt FROM patients")
    stats["total_patients"] = cur.fetchone()["cnt"]

    cur.execute("SELECT COUNT(*) as cnt FROM appointments WHERE status != 'cancelled'")
    stats["total_appointments"] = cur.fetchone()["cnt"]

    cur.execute("SELECT COUNT(*) as cnt FROM appointments WHERE status = 'confirmed'")
    stats["confirmed_appointments"] = cur.fetchone()["cnt"]

    cur.execute("SELECT COUNT(*) as cnt FROM appointments WHERE status = 'pending'")
    stats["pending_appointments"] = cur.fetchone()["cnt"]

    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE status = 'confirmed'
    """)
    stats["total_revenue"] = cur.fetchone()["total"]

    cur.execute("""
        SELECT d.full_name, COUNT(a.id) as cnt
        FROM appointments a JOIN doctors d ON a.doctor_id = d.id
        WHERE a.status != 'cancelled'
        GROUP BY d.id ORDER BY cnt DESC LIMIT 5
    """)
    stats["top_doctors"] = [dict(r) for r in cur.fetchall()]

    conn.close()
    return stats


# ---------- Navbat funksiyalari ----------

def get_booked_times(doctor_id, date_str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT appointment_time FROM appointments WHERE doctor_id = ? AND appointment_date = ? AND status != 'cancelled'",
        (doctor_id, date_str)
    )
    times = [row["appointment_time"] for row in cur.fetchall()]
    conn.close()
    return times


def create_appointment(patient_id, doctor_id, date_str, time_str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time) VALUES (?, ?, ?, ?)",
        (patient_id, doctor_id, date_str, time_str)
    )
    conn.commit()
    appointment_id = cur.lastrowid
    conn.close()
    return appointment_id


def get_patient_appointments(patient_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.*, d.full_name as doctor_name, d.specialty, d.room_number
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.patient_id = ? AND a.status != 'cancelled'
        ORDER BY a.appointment_date, a.appointment_time
    """, (patient_id,))
    appointments = [dict(row) for row in cur.fetchall()]
    conn.close()
    return appointments


def cancel_appointment(appointment_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE appointments SET status = 'cancelled' WHERE id = ?", (appointment_id,))
    conn.commit()
    conn.close()


def get_appointment_by_id(appointment_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.*, d.full_name as doctor_name, d.specialty, d.room_number, d.price,
               p.telegram_id as patient_telegram_id, p.full_name as patient_name
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        JOIN patients p ON a.patient_id = p.id
        WHERE a.id = ?
    """, (appointment_id,))
    appt = cur.fetchone()
    conn.close()
    return dict(appt) if appt else None


def reschedule_appointment(appointment_id, new_date, new_time):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE appointments SET appointment_date = ?, appointment_time = ?, reminded_24h = 0, reminded_1h = 0 WHERE id = ?",
        (new_date, new_time, appointment_id)
    )
    conn.commit()
    conn.close()


def get_upcoming_unreminded(field, window_start, window_end):
    """field is 'reminded_24h' or 'reminded_1h'. Returns appointments whose datetime falls within the window and not yet reminded."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT a.*, d.full_name as doctor_name, d.room_number, p.telegram_id as patient_telegram_id
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        JOIN patients p ON a.patient_id = p.id
        WHERE a.status != 'cancelled' AND a.{field} = 0
        AND (a.appointment_date || ' ' || a.appointment_time) BETWEEN ? AND ?
    """, (window_start, window_end))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def mark_reminded(appointment_id, field):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"UPDATE appointments SET {field} = 1 WHERE id = ?", (appointment_id,))
    conn.commit()
    conn.close()


# ---------- To'lov funksiyalari ----------

def create_payment(appointment_id, amount):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payments (appointment_id, amount) VALUES (?, ?)",
        (appointment_id, amount)
    )
    conn.commit()
    payment_id = cur.lastrowid
    conn.close()
    return payment_id


def submit_payment_receipt(payment_id, file_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE payments SET receipt_file_id = ?, status = 'review' WHERE id = ?",
        (file_id, payment_id)
    )
    conn.commit()
    conn.close()


def confirm_payment(payment_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE payments SET status = 'confirmed' WHERE id = ?", (payment_id,))
    cur.execute("""
        UPDATE appointments SET status = 'confirmed'
        WHERE id = (SELECT appointment_id FROM payments WHERE id = ?)
    """, (payment_id,))
    conn.commit()
    conn.close()
