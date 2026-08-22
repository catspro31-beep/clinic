import logging
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

import database as db
from config import (
    BOT_TOKEN, ADMIN_IDS, ADMIN_USERNAME, WORK_START_HOUR, WORK_END_HOUR,
    SLOT_DURATION_MINUTES, PAYMENT_CARD_NUMBER, PAYMENT_CARD_OWNER
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Suhbat holatlari (Conversation states)
REGISTER_NAME, REGISTER_PHONE = range(2)
CHOOSE_DOCTOR, CHOOSE_DATE, CHOOSE_TIME, CONFIRM_BOOKING = range(2, 6)
WAITING_RECEIPT = 6
RESCHEDULE_DATE, RESCHEDULE_TIME = range(7, 9)
ADMIN_ADD_NAME, ADMIN_ADD_SPECIALTY, ADMIN_ADD_ROOM, ADMIN_ADD_PRICE = range(9, 13)
CHOOSE_ROOM, ROOM_DATE, ROOM_TIME = range(13, 16)

MAIN_MENU = [
    ["🗓 Navbatga yozilish", "📋 Mening navbatlarim"],
    ["🚪 Xona band qilish", "💆 Xizmatlar"],
    ["👨‍⚕️ Shifokorlar", "ℹ️ Ma'lumot"],
]


def main_menu_markup():
    return ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)


# ---------------- /start va ro'yxatdan o'tish ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    patient = db.get_or_create_patient(user.id)

    if not patient["full_name"] or not patient["phone_number"]:
        await update.message.reply_text(
            f"Assalomu alaykum, {user.first_name}! 👋\n\n"
            "Klinika botiga xush kelibsiz. Avval ro'yxatdan o'tamiz.\n\n"
            "Iltimos, to'liq ismingizni kiriting:"
        )
        return REGISTER_NAME

    await update.message.reply_text(
        f"Xush kelibsiz, {patient['full_name']}! 😊\nQuyidagi menyudan tanlang:",
        reply_markup=main_menu_markup()
    )
    return ConversationHandler.END


async def register_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["full_name"] = update.message.text
    contact_button = KeyboardButton("📱 Raqamni yuborish", request_contact=True)
    await update.message.reply_text(
        "Rahmat! Endi telefon raqamingizni yuboring:",
        reply_markup=ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)
    )
    return REGISTER_PHONE


async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text

    user = update.effective_user
    db.update_patient_info(user.id, full_name=context.user_data["full_name"], phone_number=phone)

    await update.message.reply_text(
        "Ro'yxatdan muvaffaqiyatli o'tdingiz! ✅\n\nQuyidagi menyudan foydalanishingiz mumkin:",
        reply_markup=main_menu_markup()
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bekor qilindi.", reply_markup=main_menu_markup())
    return ConversationHandler.END


# ---------------- Shifokorlar ro'yxati ----------------

async def show_doctors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doctors = db.get_all_doctors()
    if not doctors:
        await update.message.reply_text("Hozircha shifokorlar mavjud emas.")
        return

    text = "👨‍⚕️ *Klinikamiz shifokorlari:*\n\n"
    for d in doctors:
        text += (
            f"*{d['full_name']}*\n"
            f"Mutaxassislik: {d['specialty']}\n"
            f"Xona: {d['room_number']}\n"
            f"Narx: {d['price']:,} so'm\n\n"
        )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------- Navbatga yozilish oqimi ----------------

async def booking_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doctors = db.get_all_doctors()
    if not doctors:
        await update.message.reply_text("Hozircha shifokorlar mavjud emas.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton(f"{d['full_name']} — {d['specialty']}", callback_data=f"doc_{d['id']}")]
        for d in doctors
    ]
    await update.message.reply_text(
        "Qaysi shifokorga yozilmoqchisiz?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSE_DOCTOR


async def choose_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    doctor_id = int(query.data.split("_")[1])
    context.user_data["doctor_id"] = doctor_id
    doctor = db.get_doctor_by_id(doctor_id)
    context.user_data["doctor"] = doctor

    keyboard = []
    today = datetime.now()
    for i in range(7):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        label = date.strftime("%d-%m (%a)")
        keyboard.append([InlineKeyboardButton(label, callback_data=f"date_{date_str}")])

    await query.edit_message_text(
        f"Shifokor: *{doctor['full_name']}*\n\nQaysi kunga yozilmoqchisiz?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return CHOOSE_DATE


async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = query.data.split("_")[1]
    context.user_data["date"] = date_str

    doctor_id = context.user_data["doctor_id"]
    booked_times = db.get_booked_times(doctor_id, date_str)

    available_slots = []
    current = datetime.strptime(f"{date_str} {WORK_START_HOUR}:00", "%Y-%m-%d %H:%M")
    end = datetime.strptime(f"{date_str} {WORK_END_HOUR}:00", "%Y-%m-%d %H:%M")
    while current < end:
        time_str = current.strftime("%H:%M")
        if time_str not in booked_times:
            available_slots.append(time_str)
        current += timedelta(minutes=SLOT_DURATION_MINUTES)

    if not available_slots:
        await query.edit_message_text("Afsuski, bu kunga bo'sh vaqt yo'q. /start ni qayta bosib, boshqa kunni tanlang.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton(t, callback_data=f"time_{t}") for t in available_slots[i:i+3]]
        for i in range(0, len(available_slots), 3)
    ]
    await query.edit_message_text(
        f"Sana: *{date_str}*\n\nBo'sh vaqtlardan birini tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return CHOOSE_TIME


async def choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    time_str = query.data.split("_")[1]
    context.user_data["time"] = time_str

    doctor = context.user_data["doctor"]
    date_str = context.user_data["date"]

    text = (
        "📋 *Navbatni tasdiqlang:*\n\n"
        f"Shifokor: {doctor['full_name']} ({doctor['specialty']})\n"
        f"Xona: {doctor['room_number']}\n"
        f"Sana: {date_str}\n"
        f"Vaqt: {time_str}\n"
        f"Narx: {doctor['price']:,} so'm\n\n"
        "Tasdiqlaysizmi?"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_yes")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="confirm_no")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CONFIRM_BOOKING


async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_no":
        await query.edit_message_text("Navbat bekor qilindi.")
        return ConversationHandler.END

    user = update.effective_user
    patient = db.get_or_create_patient(user.id)
    doctor = context.user_data["doctor"]
    date_str = context.user_data["date"]
    time_str = context.user_data["time"]

    appointment_id = db.create_appointment(patient["id"], doctor["id"], date_str, time_str)
    payment_id = db.create_payment(appointment_id, doctor["price"])
    context.user_data["payment_id"] = payment_id

    await query.edit_message_text(
        "✅ Navbatingiz band qilindi!\n\n"
        f"To'lov uchun quyidagi kartaga *{doctor['price']:,} so'm* o'tkazing:\n\n"
        f"💳 `{PAYMENT_CARD_NUMBER}`\n"
        f"👤 {PAYMENT_CARD_OWNER}\n\n"
        "To'lovni amalga oshirgach, chekning skrinshotini shu yerga yuboring.",
        parse_mode="Markdown"
    )
    return WAITING_RECEIPT


async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Iltimos, to'lov chekining rasmini (skrinshot) yuboring.")
        return WAITING_RECEIPT

    file_id = update.message.photo[-1].file_id
    payment_id = context.user_data.get("payment_id")
    db.submit_payment_receipt(payment_id, file_id)

    await update.message.reply_text(
        "Chek qabul qilindi! ✅ Adminstratsiya tekshirib, tasdiqlaydi.\n"
        "Tasdiqlangach sizga xabar beriladi.",
        reply_markup=main_menu_markup()
    )

    doctor = context.user_data["doctor"]
    date_str = context.user_data["date"]
    time_str = context.user_data["time"]
    user = update.effective_user

    admin_text = (
        f"💰 Yangi to'lov tekshiruvi!\n\n"
        f"Bemor: {user.full_name} (@{user.username})\n"
        f"Shifokor: {doctor['full_name']}\n"
        f"Sana/Vaqt: {date_str} {time_str}\n"
        f"Summasi: {doctor['price']:,} so'm\n\n"
        f"Tasdiqlash uchun: /confirm_{payment_id}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(admin_id, photo=file_id, caption=admin_text)
        except Exception as e:
            logger.error(f"Adminga xabar yuborishda xato: {e}")

    return ConversationHandler.END


# ---------------- Mening navbatlarim ----------------

async def my_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    patient = db.get_or_create_patient(user.id)
    appointments = db.get_patient_appointments(patient["id"])

    if not appointments:
        await update.message.reply_text("Sizda hozircha faol navbatlar yo'q.")
        return

    status_map = {"pending": "⏳ Kutilmoqda (to'lov)", "confirmed": "✅ Tasdiqlangan"}

    await update.message.reply_text("📋 *Sizning navbatlaringiz:*", parse_mode="Markdown")
    for a in appointments:
        status = status_map.get(a["status"], a["status"])
        text = (
            f"👨‍⚕️ {a['doctor_name']} ({a['specialty']})\n"
            f"📅 {a['appointment_date']} ⏰ {a['appointment_time']}\n"
            f"🚪 Xona: {a['room_number']}\n"
            f"Holati: {status}"
        )
        keyboard = [[
            InlineKeyboardButton("🔄 Qayta rejalashtirish", callback_data=f"resch_{a['id']}"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_{a['id']}"),
        ]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def cancel_appointment_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    appointment_id = int(query.data.split("_")[1])
    db.cancel_appointment(appointment_id)
    await query.edit_message_text("❌ Navbat bekor qilindi.")


async def reschedule_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    appointment_id = int(query.data.split("_")[1])
    appt = db.get_appointment_by_id(appointment_id)
    context.user_data["reschedule_appt_id"] = appointment_id
    context.user_data["reschedule_doctor_id"] = appt["doctor_id"]

    keyboard = []
    today = datetime.now()
    for i in range(7):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        label = date.strftime("%d-%m (%a)")
        keyboard.append([InlineKeyboardButton(label, callback_data=f"rdate_{date_str}")])

    await query.edit_message_text(
        f"Navbatni qayta rejalashtirish: *{appt['doctor_name']}*\n\nYangi kunni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return RESCHEDULE_DATE


async def reschedule_choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = query.data.split("_")[1]
    context.user_data["reschedule_date"] = date_str

    doctor_id = context.user_data["reschedule_doctor_id"]
    booked_times = db.get_booked_times(doctor_id, date_str)

    available_slots = []
    current = datetime.strptime(f"{date_str} {WORK_START_HOUR}:00", "%Y-%m-%d %H:%M")
    end = datetime.strptime(f"{date_str} {WORK_END_HOUR}:00", "%Y-%m-%d %H:%M")
    while current < end:
        time_str = current.strftime("%H:%M")
        if time_str not in booked_times:
            available_slots.append(time_str)
        current += timedelta(minutes=SLOT_DURATION_MINUTES)

    if not available_slots:
        await query.edit_message_text("Bu kunga bo'sh vaqt yo'q. /start ni bosib qayta urinib ko'ring.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton(t, callback_data=f"rtime_{t}") for t in available_slots[i:i+3]]
        for i in range(0, len(available_slots), 3)
    ]
    await query.edit_message_text(
        f"Sana: *{date_str}*\n\nYangi vaqtni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return RESCHEDULE_TIME


async def reschedule_choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    time_str = query.data.split("_")[1]
    date_str = context.user_data["reschedule_date"]
    appointment_id = context.user_data["reschedule_appt_id"]

    db.reschedule_appointment(appointment_id, date_str, time_str)

    await query.edit_message_text(
        f"✅ Navbat qayta rejalashtirildi!\n\n📅 {date_str} ⏰ {time_str}"
    )
    return ConversationHandler.END


# ---------------- Xizmatlar ----------------

async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    services = db.get_all_services()
    if not services:
        await update.message.reply_text("Hozircha xizmatlar mavjud emas.")
        return

    text = "💆 *Qo'shimcha xizmatlarimiz:*\n\n"
    for s in services:
        text += f"✨ *{s['name']}*\n{s['description']}\n\n"
    text += f"Batafsil narx uchun admin bilan bog'laning: @{ADMIN_USERNAME}"
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------------- Xona band qilish ----------------

async def room_booking_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    today = datetime.now()
    for i in range(7):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        label = date.strftime("%d-%m (%a)")
        keyboard.append([InlineKeyboardButton(label, callback_data=f"roomdate_{date_str}")])

    await update.message.reply_text(
        "🚪 Xona band qilish\n\nQaysi kunga xona band qilmoqchisiz?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ROOM_DATE


async def room_choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = query.data.split("_")[1]
    context.user_data["room_date"] = date_str

    rooms = db.get_all_rooms()
    keyboard = []
    row = []
    for r in rooms:
        booking = db.get_room_booking(r["id"], date_str)
        if booking:
            label = f"🚫 {r['room_number']}-band"
            callback = "noop"
        else:
            label = f"🚪 {r['room_number']} ({r['price']:,})"
            callback = f"roomsel_{r['id']}"
        row.append(InlineKeyboardButton(label, callback_data=callback))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await query.edit_message_text(
        f"Sana: *{date_str}*\n\nXonani tanlang (band xonalar tanlanmaydi):",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return CHOOSE_ROOM


async def room_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Bu xona band! ❌", show_alert=True)


async def room_choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    room_id = int(query.data.split("_")[1])
    room = db.get_room_by_id(room_id)
    context.user_data["room_id"] = room_id
    context.user_data["room"] = room

    await query.edit_message_text(
        f"🚪 Xona: *{room['room_number']}*\n💰 Narxi: {room['price']:,} so'm\n\n"
        "Vaqtni kiriting (masalan: 14:00):",
        parse_mode="Markdown"
    )
    return ROOM_TIME


async def room_enter_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_str = update.message.text.strip()
    date_str = context.user_data["room_date"]
    room = context.user_data["room"]
    room_id = context.user_data["room_id"]

    user = update.effective_user
    patient = db.get_or_create_patient(user.id)

    # Qayta tekshirib ko'ramiz — orada boshqa odam band qilmaganmi
    existing = db.get_room_booking(room_id, date_str)
    if existing:
        await update.message.reply_text(
            f"❌ Kechirasiz, bu xona allaqachon band bo'lib qoldi.\n"
            f"Boshqa xona tanlang: 🚪 Xona band qilish"
        )
        return ConversationHandler.END

    db.book_room(room_id, patient["id"], date_str, time_str)

    await update.message.reply_text(
        f"✅ Xona band qilindi!\n\n"
        f"🚪 Xona: {room['room_number']}\n"
        f"📅 {date_str} ⏰ {time_str}\n"
        f"💰 Narxi: {room['price']:,} so'm\n\n"
        f"To'lov va tafsilotlar uchun admin bilan bog'laning: @{ADMIN_USERNAME} 😊",
        reply_markup=main_menu_markup()
    )
    return ConversationHandler.END


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏥 *Klinika haqida ma'lumot*\n\n"
        "📅 Ish kunlari: har kuni\n"
        "🕘 Ish vaqti: 09:00 - 18:00\n\n"
        "🧪 *Laboratoriya analizlari:*\n"
        "Ertalab nonushta qilmasdan (och qoringa) kelishingiz kerak! 🙏\n\n"
        f"💬 Admin bilan bog'lanish: @{ADMIN_USERNAME}\n\n"
        "Savollaringiz bo'lsa, biz doim yordam berishga tayyormiz! 😊",
        parse_mode="Markdown"
    )


# ---------------- Avtomatik eslatmalar ----------------

async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()

    # 24 soat oldin eslatma
    window_start = (now + timedelta(hours=23)).strftime("%Y-%m-%d %H:%M")
    window_end = (now + timedelta(hours=25)).strftime("%Y-%m-%d %H:%M")
    for appt in db.get_upcoming_unreminded("reminded_24h", window_start, window_end):
        try:
            await context.bot.send_message(
                appt["patient_telegram_id"],
                f"🔔 Eslatma: ertaga navbatingiz bor!\n\n"
                f"👨‍⚕️ {appt['doctor_name']}\n"
                f"📅 {appt['appointment_date']} ⏰ {appt['appointment_time']}\n"
                f"🚪 Xona: {appt['room_number']}"
            )
        except Exception as e:
            logger.error(f"Eslatma yuborishda xato: {e}")
        db.mark_reminded(appt["id"], "reminded_24h")

    # 1 soat oldin eslatma
    window_start = (now + timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M")
    window_end = (now + timedelta(minutes=75)).strftime("%Y-%m-%d %H:%M")
    for appt in db.get_upcoming_unreminded("reminded_1h", window_start, window_end):
        try:
            await context.bot.send_message(
                appt["patient_telegram_id"],
                f"🔔 Eslatma: 1 soatdan so'ng navbatingiz bor!\n\n"
                f"👨‍⚕️ {appt['doctor_name']}\n"
                f"⏰ {appt['appointment_time']}\n"
                f"🚪 Xona: {appt['room_number']}"
            )
        except Exception as e:
            logger.error(f"Eslatma yuborishda xato: {e}")
        db.mark_reminded(appt["id"], "reminded_1h")


# ---------------- Admin panel ----------------

def is_admin(user_id):
    return user_id in ADMIN_IDS


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    keyboard = [
        [InlineKeyboardButton("➕ Shifokor qo'shish", callback_data="admin_add_doctor")],
        [InlineKeyboardButton("➖ Shifokorni o'chirish", callback_data="admin_remove_doctor")],
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
    ]
    await update.message.reply_text(
        "⚙️ *Admin panel*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return

    s = db.get_stats()
    text = (
        "📊 *Statistika*\n\n"
        f"👥 Jami bemorlar: {s['total_patients']}\n"
        f"🗓 Jami navbatlar: {s['total_appointments']}\n"
        f"✅ Tasdiqlangan: {s['confirmed_appointments']}\n"
        f"⏳ Kutilmoqda: {s['pending_appointments']}\n"
        f"💰 Jami tushum: {s['total_revenue']:,} so'm\n\n"
        "*Eng band shifokorlar:*\n"
    )
    for d in s["top_doctors"]:
        text += f"— {d['full_name']}: {d['cnt']} ta navbat\n"

    await query.edit_message_text(text, parse_mode="Markdown")


async def admin_remove_doctor_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return

    doctors = db.get_all_doctors()
    if not doctors:
        await query.edit_message_text("Shifokorlar mavjud emas.")
        return

    keyboard = [
        [InlineKeyboardButton(f"{d['full_name']} — {d['specialty']}", callback_data=f"admin_rmdoc_{d['id']}")]
        for d in doctors
    ]
    await query.edit_message_text("O'chiriladigan shifokorni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))


async def admin_remove_doctor_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    doctor_id = int(query.data.split("_")[2])
    db.deactivate_doctor(doctor_id)
    await query.edit_message_text("✅ Shifokor ro'yxatdan olib tashlandi.")


async def admin_add_doctor_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await query.edit_message_text("Shifokorning to'liq ismini kiriting:")
    return ADMIN_ADD_NAME


async def admin_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_doc_name"] = update.message.text
    await update.message.reply_text("Mutaxassisligini kiriting (masalan: Terapevt):")
    return ADMIN_ADD_SPECIALTY


async def admin_add_specialty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_doc_specialty"] = update.message.text
    await update.message.reply_text("Xona raqamini kiriting:")
    return ADMIN_ADD_ROOM


async def admin_add_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_doc_room"] = update.message.text
    await update.message.reply_text("Qabul narxini kiriting (faqat raqam, masalan: 50000):")
    return ADMIN_ADD_PRICE


async def admin_add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Iltimos, faqat raqam kiriting (masalan: 50000):")
        return ADMIN_ADD_PRICE

    db.add_doctor(
        context.user_data["new_doc_name"],
        context.user_data["new_doc_specialty"],
        context.user_data["new_doc_room"],
        price
    )
    await update.message.reply_text("✅ Yangi shifokor qo'shildi!", reply_markup=main_menu_markup())
    return ConversationHandler.END


# ---------------- Admin: to'lovni tasdiqlash ----------------

async def admin_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    text = update.message.text
    try:
        payment_id = int(text.replace("/confirm_", ""))
    except ValueError:
        await update.message.reply_text("Noto'g'ri buyruq.")
        return

    db.confirm_payment(payment_id)
    await update.message.reply_text(f"✅ To'lov #{payment_id} tasdiqlandi.")


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Buyruqni tushunmadim. Menyudan foydalaning.", reply_markup=main_menu_markup())


def main():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    register_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REGISTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)],
            REGISTER_PHONE: [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), register_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    booking_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🗓 Navbatga yozilish$"), booking_start)],
        states={
            CHOOSE_DOCTOR: [CallbackQueryHandler(choose_doctor, pattern="^doc_")],
            CHOOSE_DATE: [CallbackQueryHandler(choose_date, pattern="^date_")],
            CHOOSE_TIME: [CallbackQueryHandler(choose_time, pattern="^time_")],
            CONFIRM_BOOKING: [CallbackQueryHandler(confirm_booking, pattern="^confirm_")],
            WAITING_RECEIPT: [MessageHandler(filters.PHOTO, receive_receipt)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    reschedule_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(reschedule_start, pattern="^resch_")],
        states={
            RESCHEDULE_DATE: [CallbackQueryHandler(reschedule_choose_date, pattern="^rdate_")],
            RESCHEDULE_TIME: [CallbackQueryHandler(reschedule_choose_time, pattern="^rtime_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    admin_add_doctor_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_doctor_start, pattern="^admin_add_doctor$")],
        states={
            ADMIN_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_name)],
            ADMIN_ADD_SPECIALTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_specialty)],
            ADMIN_ADD_ROOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_room)],
            ADMIN_ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    room_booking_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🚪 Xona band qilish$"), room_booking_start)],
        states={
            ROOM_DATE: [CallbackQueryHandler(room_choose_date, pattern="^roomdate_")],
            CHOOSE_ROOM: [
                CallbackQueryHandler(room_choose, pattern="^roomsel_"),
                CallbackQueryHandler(room_noop, pattern="^noop$"),
            ],
            ROOM_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, room_enter_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(register_conv)
    app.add_handler(booking_conv)
    app.add_handler(reschedule_conv)
    app.add_handler(admin_add_doctor_conv)
    app.add_handler(room_booking_conv)
    app.add_handler(MessageHandler(filters.Regex("^📋 Mening navbatlarim$"), my_appointments))
    app.add_handler(MessageHandler(filters.Regex("^👨‍⚕️ Shifokorlar$"), show_doctors))
    app.add_handler(MessageHandler(filters.Regex("^💆 Xizmatlar$"), show_services))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Ma'lumot$"), info))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(cancel_appointment_button, pattern="^cancel_"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_remove_doctor_menu, pattern="^admin_remove_doctor$"))
    app.add_handler(CallbackQueryHandler(admin_remove_doctor_confirm, pattern="^admin_rmdoc_"))
    app.add_handler(MessageHandler(filters.Regex(r"^/confirm_\d+$"), admin_confirm))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # Eslatmalarni har 15 daqiqada tekshiradi
    app.job_queue.run_repeating(send_reminders, interval=900, first=10)

    logger.info("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
