import os

# Telegram bot tokenini @BotFather dan oling va shu yerga qo'ying
# Xavfsizlik uchun uni muhit o'zgaruvchisi (environment variable) sifatida saqlash tavsiya etiladi
BOT_TOKEN = os.getenv("BOT_TOKEN", "7825789228:AAFWzdyZUNWDpC9xbwoVawMqzazwQ2xwDE0")

# Klinika administratorlarining Telegram ID raqamlari (navbat/to'lovlarni tasdiqlash uchun)
# ID ni bilish uchun @userinfobot ga /start yozing
ADMIN_IDS = [
    8007029227,
]

# Klinika ish vaqti (soat, 24 formatda)
WORK_START_HOUR = 9
WORK_END_HOUR = 18

# Har bir qabul davomiyligi (daqiqada)
SLOT_DURATION_MINUTES = 30

# Ma'lumotlar bazasi fayli
DB_PATH = os.path.join(os.path.dirname(__file__), "clinic.db")

# To'lov rekvizitlari (bemorlarga ko'rsatiladi)
PAYMENT_CARD_NUMBER = "5614 6819 1008 1540"
PAYMENT_CARD_OWNER = "Shodmanov A."

# Admin bilan bog'lanish uchun Telegram username (@ belgisisiz)
ADMIN_USERNAME = "vanzs_2"

# Xonalar soni va narx oralig'i
TOTAL_ROOMS = 33
ROOM_MIN_PRICE = 80000
ROOM_MAX_PRICE = 150000
