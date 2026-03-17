import logging
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

API_TOKEN = "8731746159:AAFB9EDKmxgQaKUaRP9yiDj7jJKjzuYPusQ"  # O'z tokeningizni qo'ying
ADMIN_IDS = [7378071060]  # Ustozlar Telegram ID sini qo'ying

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ================== DATABASE ==================
conn = sqlite3.connect("students.db")
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS students(
    id INTEGER PRIMARY KEY,
    full_name TEXT,
    phone TEXT,
    group_name TEXT,
    topic TEXT,
    submitted_file TEXT,
    submitted_type TEXT,
    score INTEGER,
    comment TEXT
)
''')
conn.commit()

# ================== FSM ==================
class Registration(StatesGroup):
    full_name = State()
    phone = State()
    group = State()
    topic = State()
    submission = State()

# ================== Keyboards ==================
def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📂 Vazifalar"), KeyboardButton("📩 Ustozga xabar"))
    return kb

def topic_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Uy dizayni maketi", "Aqlli tog maketi")
    kb.add("Blum taksanomiyasi maketi", "STEAM yondashuv asosidagi dars ishlanma")
    kb.add(KeyboardButton("🔙 Orqaga"))
    return kb

def score_keyboard(student_id):
    kb = InlineKeyboardMarkup()
    for s in range(2,5):
        kb.add(InlineKeyboardButton(text=f"{s} ball", callback_data=f"{student_id}_{s}"))
    kb.add(InlineKeyboardButton(text="Izoh qoldirish", callback_data=f"comment_{student_id}"))
    return kb

# ================== Handlers ==================
@dp.message_handler(commands=['start'])
async def start(message: types.Message, state: FSMContext):
    cursor.execute("SELECT * FROM students WHERE id=?", (message.from_user.id,))
    student = cursor.fetchone()
    if student:
        await message.answer("Botga xush kelibsiz!", reply_markup=main_menu())
        await Registration.submission.set()
    else:
        await message.answer("Ro'yxatdan o'ting. To'liq ism, familiya va sharifingizni kiriting:")
        await Registration.full_name.set()

# ---- Registration ----
@dp.message_handler(state=Registration.full_name)
async def reg_fullname(message: types.Message, state: FSMContext):
    if len(message.text.split()) < 3:
        await message.answer("Iltimos, to'liq ism, familiya va sharifni yozing!")
        return
    await state.update_data(full_name=message.text)
    await message.answer("Telefon raqamingizni kiriting (+998...)")
    await Registration.phone.set()

@dp.message_handler(state=Registration.phone)
async def reg_phone(message: types.Message, state: FSMContext):
    if not message.text.startswith("+998"):
        await message.answer("Telefon raqamingiz +998 bilan boshlanishi kerak!")
        return
    await state.update_data(phone=message.text)
    await message.answer("Hozirgi o'qiyotgan guruhingizni kiriting:")
    await Registration.group.set()

@dp.message_handler(state=Registration.group)
async def reg_group(message: types.Message, state: FSMContext):
    await state.update_data(group=message.text)
    await message.answer("Mavzuni tanlang:", reply_markup=topic_menu())
    await Registration.topic.set()

@dp.message_handler(lambda message: message.text in ["Uy dizayni maketi","Aqlli tog maketi",
                                                    "Blum taksanomiyasi maketi","STEAM yondashuv asosidagi dars ishlanma",
                                                    "🔙 Orqaga"], state=Registration.topic)
async def reg_topic(message: types.Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await message.answer("Guruhni qayta kiriting:")
        await Registration.group.set()
        return
    await state.update_data(topic=message.text)
    data = await state.get_data()
    cursor.execute("INSERT INTO students(id, full_name, phone, group_name, topic) VALUES (?, ?, ?, ?, ?)",
                   (message.from_user.id, data['full_name'], data['phone'], data['group'], data['topic']))
    conn.commit()
    await message.answer("Ro'yxatdan muvaffaqiyatli o'tdingiz! 📎 Endi dalilni yuboring: 🖼 / 📄 / 🔗", reply_markup=main_menu())
    await Registration.submission.set()

# ---- Show tasks ----
@dp.message_handler(lambda message: message.text == "📂 Vazifalar", state=Registration.submission)
async def show_task(message: types.Message):
    cursor.execute("SELECT topic FROM students WHERE id=?", (message.from_user.id,))
    topic = cursor.fetchone()[0]
    await message.answer(f"Siz tanlagan mavzu: {topic}\nEndi fayl yuboring: 🖼 / 📄 / 🔗")

# ---- Submission ----
@dp.message_handler(lambda message: message.content_type in ['photo','document','text'], state=Registration.submission)
async def receive_submission(message: types.Message):
    if message.content_type == 'photo':
        file_id = message.photo[-1].file_id
    elif message.content_type == 'document':
        file_id = message.document.file_id
    else:
        file_id = message.text
    cursor.execute("UPDATE students SET submitted_file=?, submitted_type=? WHERE id=?",
                   (file_id, message.content_type, message.from_user.id))
    conn.commit()
    await message.answer("Faylingiz qabul qilindi. Ustoz ko'rib chiqadi!")

# ---- Talaba ustozga habar ----
@dp.message_handler(lambda message: message.text == "📩 Ustozga xabar")
async def student_message(message: types.Message):
    cursor.execute("SELECT full_name FROM students WHERE id=?", (message.from_user.id,))
    full_name = cursor.fetchone()[0]
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"Talaba {full_name} yozdi:\n{message.text}")
    await message.answer("Xabaringiz ustozga yuborildi!")

# ---- Admin paneli ----
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Siz admin emassiz!")
        return
    cursor.execute("SELECT COUNT(*) FROM students")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM students WHERE submitted_file IS NOT NULL")
    submitted = cursor.fetchone()[0]
    not_submitted = total - submitted
    await message.answer(f"📊 Statistika:\nUmumiy: {total}\nTopshirganlar: {submitted}\nTopshirmaganlar: {not_submitted}")
    cursor.execute("SELECT id, full_name FROM students WHERE submitted_file IS NOT NULL")
    for s in cursor.fetchall():
        await message.answer(f"Talaba: {s[1]}", reply_markup=score_keyboard(s[0]))

# ---- Ball qo'yish va izoh ----
@dp.callback_query_handler(lambda c: "_" in c.data or "comment_" in c.data)
async def handle_score(callback: types.CallbackQuery):
    data = callback.data
    student_id = None
    if data.startswith("comment_"):
        student_id = int(data.split("_")[1])
        await bot.send_message(callback.from_user.id, "Talaba uchun izoh yozing:")
        @dp.message_handler()
        async def add_comment(msg: types.Message):
            cursor.execute("UPDATE students SET comment=? WHERE id=?", (msg.text, student_id))
            conn.commit()
            await msg.answer("Izoh qo‘yildi!")
            await bot.send_message(student_id, f"Ustoz sizning topshirig'ingizga izoh qoldirdi:\n{msg.text}")
    else:
        student_id, score = data.split("_")
        cursor.execute("UPDATE students SET score=? WHERE id=?", (int(score), int(student_id)))
        conn.commit()
        await bot.answer_callback_query(callback.id, text=f"{score} ball qo'yildi")
        await bot.send_message(student_id, f"Sizning topshirig'ingizga {score} ball qo'yildi!")

# ---- 24 soatda ogohlantirish ----
async def daily_reminder():
    while True:
        cursor.execute("SELECT id FROM students WHERE submitted_file IS NULL")
        for s in cursor.fetchall():
            await bot.send_message(s[0], "Iltimos, topshiriqni bajarishingizni unutmang!")
        await asyncio.sleep(86400)  # 24 soat

# ================== Start ==================
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(daily_reminder())
    executor.start_polling(dp, skip_updates=True)
