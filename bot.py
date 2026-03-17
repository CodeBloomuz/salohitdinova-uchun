import logging
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

API_TOKEN = "8731746159:AAFB9EDKmxgQaKUaRP9yiDj7jJKjzuYPusQ"
ADMIN_IDS = [7378071060]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ========== DATABASE ==========
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

# ========== FSM ==========
class Registration(StatesGroup):
    full_name = State()
    phone = State()
    group = State()
    topic = State()
    submission = State()

# ========== Keyboards ==========
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
    kb_builder = InlineKeyboardBuilder()
    for s in range(2,5):
        kb_builder.button(text=f"{s} ball", callback_data=f"{student_id}_{s}")
    kb_builder.button(text="Izoh qoldirish", callback_data=f"comment_{student_id}")
    kb_builder.adjust(1)
    return kb_builder.as_markup()

# ========== Handlers ==========
@dp.message(commands=["start"])
async def start(message: types.Message, state: FSMContext):
    cursor.execute("SELECT * FROM students WHERE id=?", (message.from_user.id,))
    student = cursor.fetchone()
    if student:
        await message.answer("Botga xush kelibsiz!", reply_markup=main_menu())
        await state.set_state(Registration.submission)
    else:
        await message.answer("Ro'yxatdan o'ting. To'liq ism, familiya va sharifingizni kiriting:")
        await state.set_state(Registration.full_name)

@dp.message(Registration.full_name)
async def reg_fullname(message: types.Message, state: FSMContext):
    if len(message.text.split()) < 3:
        await message.answer("Iltimos, to'liq ism, familiya va sharifni yozing!")
        return
    await state.update_data(full_name=message.text)
    await message.answer("Telefon raqamingizni kiriting (+998...)")
    await state.set_state(Registration.phone)

@dp.message(Registration.phone)
async def reg_phone(message: types.Message, state: FSMContext):
    if not message.text.startswith("+998"):
        await message.answer("Telefon raqamingiz +998 bilan boshlanishi kerak!")
        return
    await state.update_data(phone=message.text)
    await message.answer("Hozirgi o'qiyotgan guruhingizni kiriting:")
    await state.set_state(Registration.group)

@dp.message(Registration.group)
async def reg_group(message: types.Message, state: FSMContext):
    await state.update_data(group=message.text)
    await message.answer("Mavzuni tanlang:", reply_markup=topic_menu())
    await state.set_state(Registration.topic)

@dp.message(Registration.topic)
async def reg_topic(message: types.Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await message.answer("Guruhni qayta kiriting:")
        await state.set_state(Registration.group)
        return
    await state.update_data(topic=message.text)
    data = await state.get_data()
    cursor.execute("INSERT INTO students(id, full_name, phone, group_name, topic) VALUES (?, ?, ?, ?, ?)",
                   (message.from_user.id, data['full_name'], data['phone'], data['group'], data['topic']))
    conn.commit()
    await message.answer("Ro'yxatdan muvaffaqiyatli o'tdingiz! 📎 Endi dalilni yuboring: 🖼 / 📄 / 🔗", reply_markup=main_menu())
    await state.set_state(Registration.submission)

# Talaba fayl yuborishi
@dp.message(Registration.submission, content_types=types.ContentTypes.ANY)
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

# Admin panel va ball qo'yish
@dp.message(commands=["admin"])
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

# Callback handler ball va izoh
@dp.callback_query()
async def handle_score(callback: types.CallbackQuery):
    data = callback.data
    if data.startswith("comment_"):
        student_id = int(data.split("_")[1])
        await callback.message.answer("Talaba uchun izoh yozing:")
        @dp.message()
        async def add_comment(msg: types.Message):
            cursor.execute("UPDATE students SET comment=? WHERE id=?", (msg.text, student_id))
            conn.commit()
            await msg.answer("Izoh qo‘yildi!")
            await bot.send_message(student_id, f"Ustoz sizning topshirig'ingizga izoh qoldirdi:\n{msg.text}")
    else:
        student_id, score = data.split("_")
        cursor.execute("UPDATE students SET score=? WHERE id=?", (int(score), int(student_id)))
        conn.commit()
        await callback.answer(f"{score} ball qo'yildi")
        await bot.send_message(student_id, f"Sizning topshirig'ingizga {score} ball qo'yildi!")

# 24 soatda ogohlantirish
async def daily_reminder():
    while True:
        cursor.execute("SELECT id FROM students WHERE submitted_file IS NULL")
        for s in cursor.fetchall():
            await bot.send_message(s[0], "Iltimos, topshiriqni bajarishingizni unutmang!")
        await asyncio.sleep(86400)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(daily_reminder())
    dp.run_polling(bot)
