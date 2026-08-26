import telebot
import requests
import os
import threading
import time as time_module
from telebot import types
from datetime import datetime, timedelta

import database as db

# ---------------------------------------------------------
# SOZLAMALAR VA KALITLAR
# ---------------------------------------------------------
BOT_TOKEN = "7825789228:AAFWzdyZUNWDpC9xbwoVawMqzazwQ2xwDE0"
ADMIN_ID = 8007029227
GROQ_API_KEY = "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"

# Ish vaqti sozlamalari
WORK_START_HOUR = 8
WORK_END_HOUR = 18
LUNCH_START_HOUR = 12
LUNCH_END_HOUR = 13
MAIN_DOCTOR_END_HOUR = 13

# Xizmatlar bo'yicha ish vaqtlari (soat, 24 formatda)
SERVICE_HOURS = {
    "Massaj": (8, 13),
    "Xijama": (8, 17),
    "Stomatologiya": (13, 17),  # asosan 13-16, zarurat bo'lsa 17gacha
}
MAIN_DOCTORS = ["Nevropatolog", "Kardiolog"]
PAID_ON_SITE_SERVICES = ["Massaj", "Xijama", "Stomatologiya"]

# Telegram Mini App (GitHub Pages orqali joylashtiriladi)
WEBAPP_URL = "https://catspro31-beep.github.io/clinic/"

# So'kinish so'zlari (oddiy filtr, kerak bo'lsa kengaytiring)
BAD_WORDS = [
    "блять", "сука", "хуй", "пизда", "ебан", "гандон",
    "jalab", "qotoq", "kot", "loanat",
]
MAX_WARNINGS = 2

# ---------------------------------------------------------
# ERTANGI NAVBAT HAQIDA ESLATMA (fon jarayoni)
# ---------------------------------------------------------
def reminder_worker():
    last_run_hour = None
    while True:
        try:
            now = datetime.now()
            # Har kuni soat 19:00 da, ertangi kun uchun eslatmalarni yuboramiz
            if now.hour == 19 and last_run_hour != now.hour:
                tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
                appointments = db.get_appointments_for_date_unreminded(tomorrow_str)
                for appt in appointments:
                    try:
                        time_info = f" soat {appt['appointment_time']}" if appt['appointment_time'] else ""
                        bot.send_message(
                            appt['telegram_id'],
                            f"🔔 Eslatma!\n\n"
                            f"Ertaga sizda **{appt['service_name']}** bo'yicha navbat bor{time_info}.\n"
                            f"Iltimos, o'z vaqtida keling! 😊",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        print(f"Eslatma yuborishda xato: {e}")
                    db.mark_reminded(appt['id'])
                last_run_hour = now.hour
            elif now.hour != 19:
                last_run_hour = None
        except Exception as e:
            print(f"Reminder worker xatosi: {e}")
        time_module.sleep(300)  # har 5 daqiqada tekshiradi


bot = telebot.TeleBot(BOT_TOKEN)
db.init_db()

# ---------------------------------------------------------
# AI UCHUN TAYYOR PROMPT (ASR SHIFO TIBBIYOT MARKAZI)
# ---------------------------------------------------------
ASR_SHIFO_MALUMOTI = """
Siz "Asr Shifo" tibbiyot markazining aqlli, zamonaviy, xushmuomala va tajribali virtual administratorisiz.

⚠️ ASOSIY QOIDALAR:
1. Foydalanuvchi qaysi tilda yozsa (o'zbek, rus yoki ingliz), albatta o'sha tilda javob bering.
2. Botga so'kinish va haqoratli so'zlar bilan yozish qat'iyan taqiqlanadi! Agar foydalanuvchi so'kinsa yoki qo'pol muomala qilsa, uni xushmuomalalik bilan ogohlantiring.
3. Agar bemorda jiddiy shikoyat yoki e'tiroz bo'lsa, uni adminga murojaat qilishini so'rang.

🏥 XIZMATLAR VA YO'NALISHLAR:
- Asosiy shifokorlar: Nevropatolog va Kardiolog ko'rigi (soat 13:00 gacha, keyin navbatchi shifokorlar)
- Massaj — soat 08:00 dan 13:00 gacha, to'lov klinikada amalga oshiriladi
- Xijama — soat 08:00 dan 17:00 gacha (bemalol kelish mumkin), to'lov klinikada amalga oshiriladi
- Stomatologiya — asosan 13:00 dan 16:00 gacha, zarurat bo'lsa 17:00 gacha, to'lov klinikada amalga oshiriladi
- Zamonaviy tibbiy tahlillar va diagnostika

🕐 ISH VAQTI:
Markaz har kuni 08:00 - 18:00 gacha ishlaydi.
Tushlik tanaffusi: 12:00 - 13:00.
Asosiy shifokor 13:00 gacha ishlaydi, shundan keyin navbatchi shifokorlar qabul qiladi.

📞 BOG'LANISH:
Murojaat uchun admin bilan bog'laning.

💳 TO'LOV TIZIMI:
To'lovni naqd pul, Click, Payme yoki 5614 6819 1008 1540 (Shodmanov A) kartasiga o'tkazma orqali amalga oshirish mumkin. To'lov qilingach, skrinshot (chek) botga tashlanadi va u adminga yuboriladi.
"""


def get_groq_response(user_text, language="uz"):
    lang_names = {"uz": "o'zbek", "ru": "рус", "en": "English"}
    lang_name = lang_names.get(language, "o'zbek")
    lang_instruction = f"Foydalanuvchi {lang_name} tilini tanladi. Albatta shu tilda javob ber."
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": f"{ASR_SHIFO_MALUMOTI}\n{lang_instruction}\nVirtual admin sifatida bemorlarga qisqa, juda xushmuomala va aniq javob ber."},
            {"role": "user", "content": user_text}
        ],
        "temperature": 0.5
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=8)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return "Kechirasiz, batafsil ma'lumot olish uchun adminimiz bilan bog'laning."
    except Exception:
        return "Savol va murojaatlar uchun adminimiz bilan bog'laning."


def transcribe_voice(file_path_local):
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    try:
        with open(file_path_local, "rb") as f:
            files = {"file": f}
            data = {"model": "whisper-large-v3"}
            response = requests.post(url, headers=headers, files=files, data=data, timeout=20)
        if response.status_code == 200:
            return response.json().get("text", "")
        return None
    except Exception:
        return None


def get_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Xayrli tong"
    elif 12 <= hour < 17:
        return "Xayrli kun"
    elif 17 <= hour < 23:
        return "Xayrli kech"
    else:
        return "Assalomu alaykum"


def is_working_hours():
    hour = datetime.now().hour
    return WORK_START_HOUR <= hour < WORK_END_HOUR


def is_lunch_time():
    hour = datetime.now().hour
    return LUNCH_START_HOUR <= hour < LUNCH_END_HOUR


def contains_bad_words(text):
    lowered = text.lower()
    return any(bad in lowered for bad in BAD_WORDS)


# ---------------------------------------------------------
# MENYU TUGMALARI
# ---------------------------------------------------------
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton(
        "🌐 Onlayn ariza",
        web_app=types.WebAppInfo(url=WEBAPP_URL)
    ))
    markup.add(types.KeyboardButton("🩺 Qabulga yozilish"), types.KeyboardButton("💊 Xizmatlar va Narxlar"))
    markup.add(types.KeyboardButton("💳 To'lov"), types.KeyboardButton("📍 Manzil"))
    markup.add(types.KeyboardButton("🗑 Navbatni bekor qilish"), types.KeyboardButton("❓ FAQ"))
    markup.add(types.KeyboardButton("🏥 Markaz haqida"), types.KeyboardButton("📜 Qoidalar"))
    markup.add(types.KeyboardButton("🌐 Til"), types.KeyboardButton("👨‍💼 Admin"))
    return markup


# ---------------------------------------------------------
# YORDAMCHI: BLOKLANGAN FOYDALANUVCHINI TEKSHIRISH
# ---------------------------------------------------------
def check_blocked(message):
    if message.chat.id == ADMIN_ID:
        return False
    if db.is_blocked(message.chat.id):
        bot.reply_to(message, "🚫 Siz botdan foydalanish huquqidan mahrum qilindingiz. Savol bo'lsa, klinikaga to'g'ridan-to'g'ri qo'ng'iroq qiling.")
        return True
    return False


# ---------------------------------------------------------
# BOT BUYRUQLARI VA TUGMALAR ISHLOVI
# ---------------------------------------------------------
@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    if check_blocked(message):
        return
    patient = db.get_or_create_patient(message.chat.id, message.from_user.username)
    db.set_chat_mode(message.chat.id, None)
    greeting = get_greeting()

    if patient.get("full_name"):
        text = (
            f"{greeting}, {patient['full_name']}! 🏥✨\n\n"
            "Sizga qanday yordam bera olaman?"
        )
    else:
        text = (
            f"{greeting}! **'Asr Shifo'** tibbiyot markazining rasmiy virtual yordamchisiga xush kelibsiz! 🏥✨\n\n"
            "Sizga qanday yordam bera olaman? Pastdagi menyudan kerakli bo'limni tanlang yoki savolingizni to'g'ridan-to'g'ri yozing:"
        )

    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as photo:
            bot.send_photo(message.chat.id, photo, caption=text, reply_markup=get_main_menu(), parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, text, reply_markup=get_main_menu(), parse_mode="Markdown")


@bot.message_handler(func=lambda message: message.text == "🗑 Navbatni bekor qilish")
def show_my_appointments(message):
    if check_blocked(message):
        return
    appointments = db.get_active_appointments_for_patient(message.chat.id)
    if not appointments:
        bot.reply_to(message, "Sizda hozircha faol navbatlar yo'q.", reply_markup=get_main_menu())
        return

    for appt in appointments:
        time_info = f" — soat {appt['appointment_time']}" if appt['appointment_time'] else ""
        text = f"🩺 {appt['service_name']}{time_info}\n📅 {appt['appointment_date']}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_{appt['id']}"))
        bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_"))
def handle_cancel_appointment(call):
    appointment_id = int(call.data.split("_")[1])
    success = db.cancel_appointment_by_patient(call.message.chat.id, appointment_id)
    if success:
        bot.answer_callback_query(call.id, "Navbat bekor qilindi.")
        bot.edit_message_text("❌ Navbat bekor qilindi.", call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "Xatolik yuz berdi.")


@bot.message_handler(func=lambda message: message.text == "🌐 Til")
def choose_language(message):
    if check_blocked(message):
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang_uz"),
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
    )
    bot.send_message(message.chat.id, "Tilni tanlang / Выберите язык / Choose language:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def handle_language_choice(call):
    lang = call.data.split("_")[1]
    db.set_language(call.message.chat.id, lang)
    confirm = {"uz": "✅ Til o'zbekcha qilib o'rnatildi.", "ru": "✅ Язык установлен на русский.", "en": "✅ Language set to English."}
    bot.answer_callback_query(call.id, "OK")
    bot.send_message(call.message.chat.id, confirm.get(lang, confirm["uz"]))


@bot.message_handler(commands=['bugun'])
def show_today_appointments(message):
    if message.chat.id != ADMIN_ID:
        return
    today_str = datetime.now().strftime("%Y-%m-%d")
    appointments = db.get_appointments_for_date(today_str)
    if not appointments:
        bot.reply_to(message, "Bugun uchun navbatlar mavjud emas.")
        return

    text = f"📅 **Bugungi navbatlar ({today_str}):**\n\n"
    for i, appt in enumerate(appointments, 1):
        time_info = f" — soat {appt['appointment_time']}" if appt['appointment_time'] else ""
        text += f"{i}. {appt['patient_name']} — {appt['service_name']}{time_info}\n📞 {appt.get('phone_number', 'N/A')}\n\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(commands=['eksport'])
def export_appointments(message):
    if message.chat.id != ADMIN_ID:
        return
    import csv
    import io

    rows = db.get_all_appointments_export()
    if not rows:
        bot.reply_to(message, "Eksport qilish uchun ma'lumot yo'q.")
        return

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

    csv_bytes = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    csv_bytes.name = "navbatlar.csv"
    bot.send_document(message.chat.id, csv_bytes, caption="📊 Barcha navbatlar ro'yxati")


@bot.message_handler(commands=['statistika'])
def show_stats(message):
    if message.chat.id != ADMIN_ID:
        return
    s = db.get_stats()
    text = (
        "📊 **ASR SHIFO STATISTIKASI**\n\n"
        f"👥 Jami bemorlar: {s['total_patients']}\n"
        f"🚫 Bloklangan: {s['blocked']}\n"
        f"🗓 Jami murojaatlar: {s['total_appointments']}\n"
        f"📅 Bugungi murojaatlar: {s['today_appointments']}\n\n"
    )
    if s["today_by_service"]:
        text += "*Bugun bo'yicha taqsimot:*\n"
        for row in s["today_by_service"]:
            text += f"— {row['service_name']}: {row['cnt']} ta\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(commands=['elon'])
def broadcast_start(message):
    if message.chat.id != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id, "📢 Barcha bemorlarga yubormoqchi bo'lgan e'lon matnini yozing:")
    bot.register_next_step_handler(msg, broadcast_send)


def broadcast_send(message):
    text = message.text
    patient_ids = db.get_all_patient_ids()
    sent = 0
    for pid in patient_ids:
        try:
            bot.send_message(pid, f"📢 E'lon:\n\n{text}")
            sent += 1
        except Exception:
            pass
    bot.reply_to(message, f"✅ E'lon {sent} ta bemorga yuborildi.")


@bot.message_handler(func=lambda message: message.text == "📜 Qoidalar")
def rules_info(message):
    if check_blocked(message):
        return
    text = (
        "📜 **'ASR SHIFO' BOT QOIDALARI:**\n\n"
        "1️⃣ **Madaniyat:** Botga so'kinish, haqoratli yoki qo'pol so'zlar bilan yozish qat'iyan taqiqlanadi.\n"
        "2️⃣ **Murojaat:** Shikoyat yoki takliflar bo'yicha darhol **'📞 Admin bilan bog'lanish'** tugmasidan foydalaning.\n"
        "3️⃣ **To'lovlar:** Xizmatlar uchun to'lov qilingach, chek yoki skrinshotni shu botga yuborishingiz shart."
    )
    bot.reply_to(message, text, reply_markup=get_main_menu(), parse_mode="Markdown")


@bot.message_handler(func=lambda message: message.text == "💊 Xizmatlar va Narxlar")
def services_info(message):
    if check_blocked(message):
        return
    text = (
        "🏥 **BIZNING XIZMATLARIMIZ:**\n\n"
        "👨‍⚕️ **Nevropatolog** va **Kardiolog** — asosiy shifokorlar ko'rigi (13:00 gacha)\n"
        "💆 **Massaj** — 08:00 - 13:00\n"
        "🩸 **Xijama** — 08:00 - 17:00 (bemalol kelishingiz mumkin)\n"
        "🦷 **Stomatologiya** — 13:00 - 16:00 (zarurat bo'lsa 17:00 gacha)\n\n"
        "💰 Massaj, Xijama va Stomatologiya uchun to'lov klinikaga borganda amalga oshiriladi.\n\n"
        "Aniq narxlar haqida bilish uchun adminga murojaat qiling."
    )
    bot.reply_to(message, text, reply_markup=get_main_menu(), parse_mode="Markdown")


@bot.message_handler(func=lambda message: message.text == "💳 To'lov")
def payment_info(message):
    if check_blocked(message):
        return
    text = (
        "💳 **TO'LOV TIZIMI VA REKVIZITLAR:**\n\n"
        "Xizmatlar uchun to'lovni quyidagi usullardan biri bilan amalga oshirishingiz mumkin:\n\n"
        "🔹 **Naqd pul** — klinikada to'lov kassasida\n"
        "🔹 **Click** orqali\n"
        "🔹 **Payme** orqali\n"
        "🔹 **Karta orqali o'tkazma:** `5614 6819 1008 1540`\n"
        "🔹 **Karta egasi:** Shodmanov A\n\n"
        "⚠️ **DIQQAT:** Karta orqali to'lov qilgach, iltimos, **to'lov skrinshotini (chekni) shu botga rasm ko'rinishida yuboring**."
    )
    bot.reply_to(message, text, reply_markup=get_main_menu(), parse_mode="Markdown")


@bot.message_handler(func=lambda message: message.text == "📍 Manzil")
def send_location(message):
    if check_blocked(message):
        return
    bot.send_message(
        message.chat.id,
        "📍 **'Asr Shifo' tibbiyot markazi manzili:**\nNamangan viloyati, Chortoq tumani, R-118 yo'li.",
        parse_mode="Markdown"
    )
    bot.send_location(message.chat.id, latitude=41.089413, longitude=71.796775)


@bot.message_handler(func=lambda message: message.text == "❓ FAQ")
def faq_menu(message):
    if check_blocked(message):
        return
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(
        "🕒 Ish vaqtlari qanday?",
        "🩺 Shifokor qabuliga qanday yozilish mumkin?",
        "⬅️ Orqaga (Asosiy menyu)"
    )
    bot.send_message(message.chat.id, "❓ **Ko'p beriladigan savollar:**\nKerakli savolni tanlang:", reply_markup=markup, parse_mode="Markdown")


@bot.message_handler(func=lambda message: message.text == "🕒 Ish vaqtlari qanday?")
def faq_1(message):
    bot.reply_to(
        message,
        "🕒 Markazimiz har kuni soat 08:00 dan 18:00 gacha ishlaydi.\n"
        "🍽 Tushlik tanaffusi: 12:00 - 13:00.\n"
        "👨‍⚕️ Asosiy shifokor 13:00 gacha qabul qiladi, keyin navbatchi shifokorlar ishlaydi."
    )


@bot.message_handler(func=lambda message: message.text == "🩺 Shifokor qabuliga qanday yozilish mumkin?")
def faq_2(message):
    bot.reply_to(message, "🩺 Buning uchun asosiy menyudagi '🩺 Qabulga yozilish' tugmasini bosib, ma'lumotlaringizni qoldirishingiz kifoya.")


@bot.message_handler(func=lambda message: message.text == "⬅️ Orqaga (Asosiy menyu)")
def back_to_main(message):
    db.set_chat_mode(message.chat.id, None)
    bot.send_message(message.chat.id, "Asosiy menyuga qaytdingiz:", reply_markup=get_main_menu())


@bot.message_handler(func=lambda message: message.text == "🏥 Markaz haqida")
def clinic_info(message):
    if check_blocked(message):
        return
    text = (
        "🏥 **'Asr Shifo' tibbiyot markazi**\n\n"
        "Siz va oilangiz salomatligi — bizning bosh maqsadimiz!\n"
        "Malakali mutaxassislar va zamonaviy tibbiy xizmatlar."
    )
    bot.reply_to(message, text, reply_markup=get_main_menu(), parse_mode="Markdown")


# ---------------------------------------------------------
# ADMIN BILAN BOG'LANISH REJIMI
# ---------------------------------------------------------
@bot.message_handler(func=lambda message: message.text == "👨‍💼 Admin")
def contact_admin_mode(message):
    if check_blocked(message):
        return
    db.set_chat_mode(message.chat.id, "chat_with_admin")
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add("⬅️ Orqaga (Asosiy menyu)")
    bot.send_message(
        message.chat.id,
        "📞 **Admin bilan to'g'ridan-to'g'ri muloqot rejimiga o'tdingiz.**\n\n"
        "Savolingiz yoki murojaatingizni yozib yuboring, u darhol adminga yetkaziladi va admin javobi sizga shu yerga keladi.",
        reply_markup=markup, parse_mode="Markdown"
    )


# ---------------------------------------------------------
# QABULGA YOZILISH TIZIMI
# ---------------------------------------------------------
@bot.message_handler(func=lambda message: message.text == "🩺 Qabulga yozilish")
def start_registration(message):
    if check_blocked(message):
        return
    msg = bot.send_message(message.chat.id, "Iltimos, ism va familiyangizni kiriting:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_name_step)


def process_name_step(message):
    db.update_patient(message.chat.id, temp_name=message.text, full_name=message.text)
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("Nevropatolog", "Kardiolog")
    markup.add("💆 Massaj", "🩸 Xijama", "🦷 Stomatologiya")
    msg = bot.send_message(message.chat.id, "Qaysi shifokor yoki xizmatga yozilmoqchisiz? Tanlang:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_doctor_step)


def process_doctor_step(message):
    choice = message.text.replace("💆 ", "").replace("🩸 ", "").replace("🦷 ", "")
    db.update_patient(message.chat.id, temp_doctor=choice)

    if choice in PAID_ON_SITE_SERVICES:
        start, end = SERVICE_HOURS[choice]
        msg = bot.send_message(
            message.chat.id,
            f"🕐 **{choice}** xizmati soat {start}:00 dan {end}:00 gacha ishlaydi.\n\n"
            f"Nechchi soatga kelmoqchisiz? (masalan: {start}:30)",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_service_time_step, choice)
        return

    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    btn_contact = types.KeyboardButton("📲 Telefon raqamimni yuborish", request_contact=True)
    markup.add(btn_contact)
    msg = bot.send_message(message.chat.id, "Siz bilan bog'lanishimiz uchun pastdagi **'📲 Telefon raqamimni yuborish'** tugmasini bosing:", reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_phone_step)


def process_service_time_step(message, service_name):
    start, end = SERVICE_HOURS[service_name]
    time_text = message.text.strip()

    try:
        hour = int(time_text.split(":")[0])
    except (ValueError, IndexError):
        msg = bot.send_message(message.chat.id, f"Iltimos, vaqtni to'g'ri kiriting (masalan: {start}:30):")
        bot.register_next_step_handler(msg, process_service_time_step, service_name)
        return

    if not (start <= hour <= end):
        msg = bot.send_message(
            message.chat.id,
            f"⚠️ {service_name} xizmati faqat soat {start}:00 - {end}:00 oralig'ida ishlaydi. Iltimos, shu oraliqdan vaqt tanlang:"
        )
        bot.register_next_step_handler(msg, process_service_time_step, service_name)
        return

    db.update_patient(message.chat.id, temp_appointment_time=time_text)
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    btn_contact = types.KeyboardButton("📲 Telefon raqamimni yuborish", request_contact=True)
    markup.add(btn_contact)
    msg = bot.send_message(message.chat.id, "Siz bilan bog'lanishimiz uchun pastdagi **'📲 Telefon raqamimni yuborish'** tugmasini bosing:", reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_phone_step)


def process_phone_step(message):
    phone = message.contact.phone_number if message.contact else message.text
    db.update_patient(message.chat.id, phone_number=phone)
    patient = db.get_patient(message.chat.id)

    service_name = patient.get('temp_doctor')
    appointment_time = patient.get('temp_appointment_time')
    today_str = datetime.now().strftime("%Y-%m-%d")

    appointment_id = db.create_appointment(
        message.chat.id, patient['temp_name'], service_name, today_str, appointment_time
    )
    queue_position = db.get_queue_position(service_name, today_str, appointment_id)
    previous_patient = db.get_previous_patient(service_name, today_str, appointment_id)

    queue_info = f"\n🔢 Navbat raqamingiz: **{queue_position}**"
    if previous_patient:
        queue_info += f"\n👤 Sizdan oldingi navbatda: **{previous_patient}**"
    else:
        queue_info += "\n🎉 Siz bu xizmat bo'yicha bugungi birinchi navbatdasiz!"

    if service_name in PAID_ON_SITE_SERVICES and appointment_time:
        confirm_text = (
            f"✅ **Rahmat! Navbatingiz qabul qilindi.**\n\n"
            f"🩺 Xizmat: {service_name}\n"
            f"🕐 Kelish vaqti: soat {appointment_time}"
            f"{queue_info}\n\n"
            f"💰 To'lov klinikaga borganingizda amalga oshiriladi (naqd yoki karta).\n"
            f"Iltimos, belgilangan vaqtda keling!"
        )
    else:
        confirm_text = (
            f"✅ **Rahmat! Qabulga yozilish uchun arizangiz qabul qilindi.**"
            f"{queue_info}\n\n"
            "Tez orada adminlarimiz siz bilan bog'lanishadi."
        )

    bot.send_message(message.chat.id, confirm_text, reply_markup=get_main_menu(), parse_mode="Markdown")

    username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"
    admin_text = (
        "🆕 'ASR SHIFO'GA YANGI MUROJAAT (QABULGA YOZILISH):\n\n"
        f"👤 F.I.Sh: {patient['temp_name']}\n"
        f"🩺 Mutaxassis/Xizmat: {service_name}\n"
        f"🔢 Navbat raqami: {queue_position}\n"
    )
    if appointment_time:
        admin_text += f"🕐 Kelish vaqti: {appointment_time}\n"
        admin_text += "💰 To'lov: klinikada (naqd/karta)\n"
    admin_text += (
        f"📞 Tel: {phone}\n"
        f"💬 Telegram: {username}"
    )
    try:
        bot.send_message(ADMIN_ID, admin_text)
    except Exception as e:
        print(f"Adminga yuborishda xato: {e}")


# ---------------------------------------------------------
# MINI APP (ONLAYN ARIZA) DAN KELGAN MA'LUMOT
# ---------------------------------------------------------
@bot.message_handler(content_types=['web_app_data'])
def handle_webapp_data(message):
    if check_blocked(message):
        return
    import json
    try:
        data = json.loads(message.web_app_data.data)
    except Exception:
        bot.reply_to(message, "Xatolik yuz berdi, iltimos qaytadan urinib ko'ring.")
        return

    full_name = data.get("full_name", "").strip()
    phone = data.get("phone", "").strip()
    service_name = data.get("service", "")
    appointment_time = data.get("appointment_time")

    db.update_patient(message.chat.id, full_name=full_name, phone_number=phone, username=message.from_user.username)
    today_str = datetime.now().strftime("%Y-%m-%d")

    appointment_id = db.create_appointment(message.chat.id, full_name, service_name, today_str, appointment_time)
    queue_position = db.get_queue_position(service_name, today_str, appointment_id)
    previous_patient = db.get_previous_patient(service_name, today_str, appointment_id)

    queue_info = f"\n🔢 Navbat raqamingiz: **{queue_position}**"
    if previous_patient:
        queue_info += f"\n👤 Sizdan oldingi navbatda: **{previous_patient}**"
    else:
        queue_info += "\n🎉 Siz bu xizmat bo'yicha bugungi birinchi navbatdasiz!"

    if service_name in PAID_ON_SITE_SERVICES and appointment_time:
        confirm_text = (
            f"✅ **Rahmat! Onlayn arizangiz qabul qilindi.**\n\n"
            f"🩺 Xizmat: {service_name}\n"
            f"🕐 Kelish vaqti: soat {appointment_time}"
            f"{queue_info}\n\n"
            f"💰 To'lov klinikaga borganingizda amalga oshiriladi.\n"
            f"Iltimos, belgilangan vaqtda keling!"
        )
    else:
        confirm_text = (
            f"✅ **Rahmat! Onlayn arizangiz qabul qilindi.**"
            f"{queue_info}\n\n"
            "Tez orada adminlarimiz siz bilan bog'lanishadi."
        )

    bot.send_message(message.chat.id, confirm_text, reply_markup=get_main_menu(), parse_mode="Markdown")

    username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"
    admin_text = (
        "🌐 YANGI ONLAYN ARIZA (Mini App):\n\n"
        f"👤 F.I.Sh: {full_name}\n"
        f"🩺 Mutaxassis/Xizmat: {service_name}\n"
        f"🔢 Navbat raqami: {queue_position}\n"
    )
    if appointment_time:
        admin_text += f"🕐 Kelish vaqti: {appointment_time}\n"
        admin_text += "💰 To'lov: klinikada\n"
    admin_text += (
        f"📞 Tel: {phone}\n"
        f"💬 Telegram: {username}"
    )
    try:
        bot.send_message(ADMIN_ID, admin_text)
    except Exception as e:
        print(f"Adminga yuborishda xato: {e}")


# ---------------------------------------------------------
# SKRINSHOT
# ---------------------------------------------------------
@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    if check_blocked(message):
        return
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "✅ **To'lov skrinshoti qabul qilindi!** Uni tekshirish uchun adminga yubordik.", parse_mode="Markdown")

        username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"
        caption = (
            "💳 ASR SHIFO - YANGI TO'LOV SKRINSHOTI!\n\n"
            f"👤 Foydalanuvchi: {message.from_user.first_name}\n"
            f"🆔 ID: {message.chat.id}\n"
            f"💬 Username: {username}"
        )
        try:
            bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption)
        except Exception as e:
            print(f"Rasm yuborishda xato: {e}")


# ---------------------------------------------------------
# OVOZLI XABARLAR
# ---------------------------------------------------------
@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    if check_blocked(message):
        return
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded = bot.download_file(file_info.file_path)
        local_path = f"/tmp/voice_{message.chat.id}.ogg"
        with open(local_path, "wb") as f:
            f.write(downloaded)

        text = transcribe_voice(local_path)
        if not text:
            bot.reply_to(message, "Kechirasiz, ovozli xabarni tushunolmadim. Iltimos, matn bilan yozing.")
            return

        db.log_history(message.chat.id, f"[OVOZLI] {text}")
        ai_javob = get_groq_response(text)
        bot.reply_to(message, ai_javob)
    except Exception as e:
        print(f"Ovozli xabar xatosi: {e}")
        bot.reply_to(message, "Kechirasiz, ovozli xabarni qayta ishlashda xatolik yuz berdi.")


# ---------------------------------------------------------
# ASOSIY MATNLI XABARLAR
# ---------------------------------------------------------
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    # Admin javob yozganda
    if message.chat.id == ADMIN_ID and message.reply_to_message:
        reply_msg = message.reply_to_message.caption or message.reply_to_message.text
        if reply_msg and "ID:" in reply_msg:
            try:
                lines = reply_msg.split("\n")
                user_id_line = [l for l in lines if "ID:" in l][0]
                target_user_id = int(''.join(ch for ch in user_id_line.split("ID:")[1] if ch.isdigit()))
                bot.send_message(target_user_id, f"👨‍💼 Admin javobi:\n\n{message.text}")
                bot.reply_to(message, "✅ Xabar foydalanuvchiga yuborildi!")
                return
            except Exception as e:
                bot.reply_to(message, f"Xatolik yuz berdi: {e}")
                return

    if check_blocked(message):
        return

    db.get_or_create_patient(message.chat.id, message.from_user.username)
    db.log_history(message.chat.id, message.text or "")

    # So'kinish nazorati
    if message.text and contains_bad_words(message.text):
        count = db.add_warning(message.chat.id)
        if count >= MAX_WARNINGS:
            db.block_patient(message.chat.id)
            bot.reply_to(message, "🚫 Siz bir necha marta qoidabuzarlik qildingiz. Botdan foydalanish huquqingiz cheklandi.")
        else:
            bot.reply_to(message, f"⚠️ Iltimos, xushmuomala bo'ling! Botga haqoratli so'zlar bilan murojaat qilish taqiqlangan. ({count}/{MAX_WARNINGS} ogohlantirish)")
        return

    if db.get_chat_mode(message.chat.id) == "chat_with_admin":
        bot.reply_to(message, "📩 Xabaringiz adminga yuborildi. Tez orada javob qaytaramiz!")

        username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"
        admin_header = (
            "💬 ASR SHIFO ADMINGA MUROJAAT:\n\n"
            f"👤 Ism: {message.from_user.first_name}\n"
            f"🆔 ID: {message.chat.id}\n"
            f"💬 Username: {username}\n\n"
            f"✉️ Xabar: {message.text}\n\n"
            "👉 Javob berish uchun shu xabarga Reply (Javob berish) qilib yozing!"
        )
        try:
            bot.send_message(ADMIN_ID, admin_header)
        except Exception as e:
            print(f"Adminga yuborishda xato: {e}")
        return

    # Ish vaqti tekshiruvi
    if is_lunch_time():
        bot.send_message(message.chat.id, "🍽 Hozir tushlik tanaffusi (12:00 - 13:00). Xabaringizni qoldiring, tanaffusdan keyin javob beramiz.")
        return

    if not is_working_hours():
        bot.send_message(
            message.chat.id,
            "🌙 Hozir ish vaqtimiz tugagan. Markazimiz har kuni 08:00 - 18:00 oralig'ida ishlaydi.\n"
            "Murojaatingizni qoldiring, ertalab birinchi bo'lib javob beramiz."
        )
        return

    bot.send_chat_action(message.chat.id, 'typing')
    lang = db.get_language(message.chat.id)
    ai_javob = get_groq_response(message.text, lang)
    bot.reply_to(message, ai_javob)


reminder_thread = threading.Thread(target=reminder_worker, daemon=True)
reminder_thread.start()

bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
