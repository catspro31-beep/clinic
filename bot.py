import telebot
import requests
from telebot import types

# ---------------------------------------------------------
# SOZLAMALAR VA KALITLAR
# ---------------------------------------------------------
BOT_TOKEN = "7825789228:AAFWzdyZUNWDpC9xbwoVawMqzazwQ2xwDE0"
ADMIN_ID = 8007029227
GROQ_API_KEY = "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"

bot = telebot.TeleBot(BOT_TOKEN)
user_data = {}
chat_modes = {}

# ---------------------------------------------------------
# AI UCHUN TAYYOR PROMPT (ASR SHIFO TIBBIYOT MARKAZI)
# ---------------------------------------------------------
ASR_SHIFO_MALUMOTI = """
Siz "Asr Shifo" tibbiyot markazining aqlli, zamonaviy, xushmuomala va tajribali virtual administratorisiz.

⚠️ ASOSIY QOIDALAR:
1. Botga so'kinish va haqoratli so'zlar bilan yozish qat'iyan taqiqlanadi! Agar foydalanuvchi so'kinsa yoki qo'pol muomala qilsa, uni xushmuomalalik bilan ogohlantiring.
2. Sun'iy intellekt (AI) bilan to'g'ri va madaniyatli muloqot qiling.
3. Agar bemorda jiddiy shikoyat yoki e'tiroz bo'lsa, uni adminga murojaat qilishini so'rang.

🏥 XIZMATLAR VA YO'NALISHLAR:
- Malakali shifokorlar ko'rigi
- Zamonaviy tibbiy tahlillar va diagnostika
- Tor doiradagi mutaxassislar konsultatsiyasi

📞 BOG'LANISH:
Murojaat uchun admin bilan bog'laning.

💳 TO'LOV TIZIMI:
Karta raqami: 5614 6819 1008 1540 (Shodmanov A). To'lov qilingach, skrinshot (chek) botga tashlanadi va u adminga yuboriladi.
"""

def get_groq_response(user_text):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": f"{ASR_SHIFO_MALUMOTI}\nVirtual admin sifatida bemorlarga o'zbek tilida qisqa, juda xushmuomala va aniq javob ber."},
            {"role": "user", "content": user_text}
        ],
        "temperature": 0.5
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=6)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return "Kechirasiz, batafsil ma'lumot olish uchun adminimiz bilan bog'laning."
    except Exception:
        return "Savol va murojaatlar uchun adminimiz bilan bog'laning."

# ---------------------------------------------------------
# MENYU TUGMALARI
# ---------------------------------------------------------
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton("🩺 Qabulga yozilish")
    btn2 = types.KeyboardButton("🏥 Xizmatlar va Narxlar")
    btn3 = types.KeyboardButton("💳 To'lov qilish")
    btn4 = types.KeyboardButton("📍 Manzilimiz")
    btn5 = types.KeyboardButton("❓ Ko'p beriladigan savollar")
    btn6 = types.KeyboardButton("⚠️ Bot qoidalari")
    btn7 = types.KeyboardButton("ℹ️ Markaz haqida")
    btn8 = types.KeyboardButton("📞 Admin bilan bog'lanish")

    markup.add(btn1)
    markup.add(btn2, btn3)
    markup.add(btn4, btn5)
    markup.add(btn6, btn7)
    markup.add(btn8)
    return markup

# ---------------------------------------------------------
# BOT BUYRUQLARI VA TUGMALAR ISHLOVI
# ---------------------------------------------------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_modes.pop(message.chat.id, None)
    text = (
        "Assalomu alaykum! **'Asr Shifo'** tibbiyot markazining rasmiy virtual yordamchisiga xush kelibsiz! 🏥✨\n\n"
        "Sizga qanday yordam bera olaman? Pastdagi menyudan kerakli bo'limni tanlang yoki savolingizni to'g'ridan-to'g'ri yozing:"
    )
    bot.send_message(message.chat.id, text, reply_markup=get_main_menu(), parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "⚠️ Bot qoidalari")
def rules_info(message):
    text = (
        "📜 **'ASR SHIFO' BOT QOIDALARI:**\n\n"
        "1️⃣ **Madaniyat:** Botga so'kinish, haqoratli yoki qo'pol so'zlar bilan yozish qat'iyan taqiqlanadi.\n"
        "2️⃣ **Murojaat:** Shikoyat yoki takliflar bo'yicha darhol **'📞 Admin bilan bog'lanish'** tugmasidan foydalaning.\n"
        "3️⃣ **To'lovlar:** Xizmatlar uchun to'lov qilingach, chek yoki skrinshotni shu botga yuborishingiz shart."
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🏥 Xizmatlar va Narxlar")
def services_info(message):
    text = (
        "🏥 **BIZNING XIZMATLARIMIZ:**\n\n"
        "• Malakali shifokorlar ko'rigi\n"
        "• Zamonaviy labaratoriya tahlillari\n"
        "• Tor doiradagi mutaxassislar konsultatsiyasi\n\n"
        "Aniq narxlar va qabul vaqtlari haqida bilish uchun adminga murojaat qiling."
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "💳 To'lov qilish")
def payment_info(message):
    text = (
        "💳 **TO'LOV TIZIMI VA REKVIZITLAR:**\n\n"
        "Xizmatlar uchun to'lovni quyidagi karta raqamiga o'tkazishingiz mumkin:\n\n"
        "🔹 **Karta raqami:** `5614 6819 1008 1540`\n"
        "🔹 **Karta egasi:** Shodmanov A\n"
        "🔹 **Ilovalar:** Click, Payme, Uzcard, Humo\n\n"
        "⚠️ **DIQQAT:** To'lovni amalga oshirgach, iltimos, **to'lov skrinshotini (chekni) shu botga rasm ko'rinishida yuboring**."
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "📍 Manzilimiz")
def send_location(message):
    bot.send_message(
        message.chat.id,
        "📍 **'Asr Shifo' tibbiyot markazi manzili:**\nNamangan viloyati, Chortoq tumani, R-118 yo'li.",
        parse_mode="Markdown"
    )
    bot.send_location(message.chat.id, latitude=41.089413, longitude=71.796775)

@bot.message_handler(func=lambda message: message.text == "❓ Ko'p beriladigan savollar")
def faq_menu(message):
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(
        "🕒 Ish vaqtlari qanday?",
        "🩺 Shifokor qabuliga qanday yozilish mumkin?",
        "⬅️ Orqaga (Asosiy menyu)"
    )
    bot.send_message(message.chat.id, "❓ **Ko'p beriladigan savollar:**\nKerakli savolni tanlang:", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🕒 Ish vaqtlari qanday?")
def faq_1(message):
    bot.reply_to(message, "🕒 Markazimiz har kuni soat 08:00 dan 18:00 gacha ishlaydi.")

@bot.message_handler(func=lambda message: message.text == "🩺 Shifokor qabuliga qanday yozilish mumkin?")
def faq_2(message):
    bot.reply_to(message, "🩺 Buning uchun asosiy menyudagi '🩺 Qabulga yozilish' tugmasini bosib, ma'lumotlaringizni qoldirishingiz kifoya.")

@bot.message_handler(func=lambda message: message.text == "⬅️ Orqaga (Asosiy menyu)")
def back_to_main(message):
    chat_modes.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "Asosiy menyuga qaytdingiz:", reply_markup=get_main_menu())

@bot.message_handler(func=lambda message: message.text == "ℹ️ Markaz haqida")
def clinic_info(message):
    text = (
        "🏥 **'Asr Shifo' tibbiyot markazi**\n\n"
        "Siz va oilangiz salomatligi — bizning bosh maqsadimiz!\n"
        "Malakali mutaxassislar va zamonaviy tibbiy xizmatlar."
    )
    bot.reply_to(message, text, parse_mode="Markdown")

# ---------------------------------------------------------
# ADMIN BILAN BOG'LANISH REJIMI
# ---------------------------------------------------------
@bot.message_handler(func=lambda message: message.text == "📞 Admin bilan bog'lanish")
def contact_admin_mode(message):
    chat_modes[message.chat.id] = "chat_with_admin"
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
    user_data[message.chat.id] = {}
    msg = bot.send_message(message.chat.id, "Iltimos, ism va familiyangizni kiriting:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_name_step)

def process_name_step(message):
    user_data[message.chat.id]['name'] = message.text
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("Terapevt", "Pediatr", "Nevropatolog", "Kardiolog", "Boshqa mutaxassis")
    msg = bot.send_message(message.chat.id, "Qaysi shifokor ko'rigiga yozilmoqchisiz? Tanlang:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_doctor_step)

def process_doctor_step(message):
    user_data[message.chat.id]['doctor'] = message.text
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    btn_contact = types.KeyboardButton("📲 Telefon raqamimni yuborish", request_contact=True)
    markup.add(btn_contact)
    msg = bot.send_message(message.chat.id, "Siz bilan bog'lanishimiz uchun pastdagi **'📲 Telefon raqamimni yuborish'** tugmasini bosing:", reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_phone_step)

def process_phone_step(message):
    phone = message.contact.phone_number if message.contact else message.text
    user_data[message.chat.id]['phone'] = phone

    bot.send_message(message.chat.id, "✅ **Rahmat! Qabulga yozilish uchun arizangiz qabul qilindi.**\n\nTez orada adminlarimiz siz bilan bog'lanishadi.", reply_markup=get_main_menu(), parse_mode="Markdown")

    username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"
    admin_text = (
        "🆕 'ASR SHIFO'GA YANGI MUROJAAT (QABULGA YAZILISH):\n\n"
        f"👤 F.I.Sh: {user_data[message.chat.id]['name']}\n"
        f"🩺 Mutaxassis: {user_data[message.chat.id]['doctor']}\n"
        f"📞 Tel: {phone}\n"
        f"💬 Telegram: {username}"
    )
    try:
        bot.send_message(ADMIN_ID, admin_text)
    except Exception:
        pass

# ---------------------------------------------------------
# SKRINSHOT VA ADMIN BILAN CHAT
# ---------------------------------------------------------
@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "✅ **To'lov skrinshoti qabul qilindi!** Uni tekshirish uchun adminga yubordik.", parse_mode="Markdown")

        username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"
        caption = (
            "💳 **ASR SHIFO - YANGI TO'LOV SKRINSHOTI!**\n\n"
            f"👤 Foydalanuvchi: {message.from_user.first_name}\n"
            f"🆔 ID: `{message.chat.id}`\n"
            f"💬 Username: {username}"
        )
        try:
            bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, parse_mode="Markdown")
        except Exception:
            pass

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    if message.chat.id == ADMIN_ID and message.reply_to_message:
        reply_msg = message.reply_to_message.caption or message.reply_to_message.text
        if reply_msg and "ID:" in reply_msg:
            try:
                lines = reply_msg.split("\n")
                user_id_line = [l for l in lines if "ID:" in l][0]
                target_user_id = int(user_id_line.split("`")[1])

                bot.send_message(target_user_id, f"👨‍💼 **Admin javobi:**\n\n{message.text}")
                bot.reply_to(message, f"✅ Xabar foydalanuvchiga yuborildi!")
                return
            except Exception as e:
                bot.reply_to(message, f"Xatolik yuz berdi: {e}")
                return

    if chat_modes.get(message.chat.id) == "chat_with_admin":
        bot.reply_to(message, "📩 Xabaringiz adminga yuborildi. Tez orada javob qaytaramiz!")

        username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"
        admin_text = (
            "💬 **ASR SHIFO ADMINGA MUROJAAT:**\n\n"
            f"👤 Ism: {message.from_user.first_name}\n"
            f"🆔 ID: `{message.chat.id}`\n"
            f"💬 Username: {username}\n\n"
            f"✉️ Xabar: {message.text}\n\n"
            "👉 *Javob berish uchun shu xabarga Reply (Javob berish) qilib yozing!*"
        )
        try:
            bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown")
        except Exception:
            pass
        return

    bot.send_chat_action(message.chat.id, 'typing')
    ai_javob = get_groq_response(message.text)
    bot.reply_to(message, ai_javob)

bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
