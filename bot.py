import asyncio
import re
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8731746159:AAFB9EDKmxgQaKUaRP9yiDj7jJKjzuYPusQ"
ADMIN_ID = 7378071060

bot = Bot(token=TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    name = State()
    phone = State()
    group = State()
    waiting_file = State()
    contact = State()
    comment = State()

topics = [
    "Uy dizayni maketi",
    "Aqlli tog maketi",
    "Blum taksanomiyasi maketi",
    "STEAM yondashuv asosidagi dars ishlanma"
]

async def init_db():
    async with aiosqlite.connect("db.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            name TEXT,
            phone TEXT,
            group_name TEXT,
            submitted INTEGER DEFAULT 0
        )
        """)
        await db.commit()

def valid_name(name):
    return len(name.split()) >= 3

def valid_phone(phone):
    return re.match(r"^\+998\d{9}$", phone)

def get_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=topics[0])],
            [KeyboardButton(text=topics[1])],
            [KeyboardButton(text=topics[2])],
            [KeyboardButton(text=topics[3])],
            [KeyboardButton(text="📩 Ustozga yozish")]
        ],
        resize_keyboard=True
    )

@dp.message(F.text == "/start")
async def start(msg: types.Message, state: FSMContext):
    async with aiosqlite.connect("db.db") as db:
        user = await db.execute_fetchone("SELECT * FROM users WHERE id=?", (msg.from_user.id,))

    if user:
        await msg.answer("✅ Siz allaqachon ro‘yxatdan o‘tgansiz!", reply_markup=get_menu())
    else:
        await state.set_state(Form.name)
        await msg.answer("👤 F.I.Sh kiriting:")

@dp.message(Form.name)
async def get_name(msg: types.Message, state: FSMContext):
    if not valid_name(msg.text):
        await msg.answer("❗ To‘liq yozing!")
        return
    await state.update_data(name=msg.text)
    await state.set_state(Form.phone)
    await msg.answer("📱 Telefon (+998...):")

@dp.message(Form.phone)
async def get_phone(msg: types.Message, state: FSMContext):
    if not valid_phone(msg.text):
        await msg.answer("❗ Noto‘g‘ri format!")
        return
    await state.update_data(phone=msg.text)
    await state.set_state(Form.group)
    await msg.answer("🎓 Guruh:")

@dp.message(Form.group)
async def get_group(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect("db.db") as db:
        await db.execute("INSERT INTO users VALUES(?,?,?,?,?)",
                         (msg.from_user.id, data["name"], data["phone"], msg.text, 0))
        await db.commit()

    await state.clear()
    await msg.answer("📚 Mavzuni tanlang:", reply_markup=get_menu())

@dp.message(F.text == "📩 Ustozga yozish")
async def contact(msg: types.Message, state: FSMContext):
    await state.set_state(Form.contact)
    await msg.answer("✍️ Xabar yozing:")

@dp.message(Form.contact)
async def send_to_admin(msg: types.Message, state: FSMContext):
    await bot.send_message(ADMIN_ID, f"📩 Talabadan xabar:\n{msg.text}")
    await msg.answer("✅ Yuborildi!")
    await state.clear()

@dp.message(F.text.in_(topics))
async def choose_topic(msg: types.Message, state: FSMContext):
    await state.set_state(Form.waiting_file)
    await msg.answer("📎 Dalil yuboring (rasm/pdf/link):")

@dp.message(Form.waiting_file, F.photo | F.document | F.text)
async def file_handler(msg: types.Message, state: FSMContext):
    user_id = msg.from_user.id

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐2", callback_data=f"2|{user_id}")],
        [InlineKeyboardButton(text="⭐3", callback_data=f"3|{user_id}")],
        [InlineKeyboardButton(text="⭐4", callback_data=f"4|{user_id}")]
    ])

    await msg.forward(ADMIN_ID)
    await bot.send_message(ADMIN_ID, "👆 Baholang:", reply_markup=kb)

    async with aiosqlite.connect("db.db") as db:
        await db.execute("UPDATE users SET submitted=1 WHERE id=?", (user_id,))
        await db.commit()

    await msg.answer("✅ Yuborildi!")
    await state.clear()

temp = {}

@dp.callback_query()
async def score(call: types.CallbackQuery, state: FSMContext):
    score, user_id = call.data.split("|")
    temp[call.from_user.id] = (user_id, score)
    await state.set_state(Form.comment)
    await call.message.answer("✍️ Izoh yozing:")
    await call.answer()

@dp.message(Form.comment)
async def comment(msg: types.Message, state: FSMContext):
    if msg.from_user.id in temp:
        user_id, score = temp[msg.from_user.id]
        await bot.send_message(int(user_id), f"🎉 {score} ball qo‘yildi!\n📝 {msg.text}")
        await msg.answer("✅ Yuborildi")
        del temp[msg.from_user.id]
        await state.clear()

@dp.message(F.text == "/stat")
async def stat(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    async with aiosqlite.connect("db.db") as db:
        total = (await db.execute_fetchone("SELECT COUNT(*) FROM users"))[0]
        submitted = (await db.execute_fetchone("SELECT COUNT(*) FROM users WHERE submitted=1"))[0]
        not_sub = total - submitted
    await msg.answer(f"📊\n👥 {total}\n✅ {submitted}\n❌ {not_sub}")

async def reminder():
    while True:
        await asyncio.sleep(86400)
        async with aiosqlite.connect("db.db") as db:
            users = await db.execute_fetchall("SELECT id FROM users WHERE submitted=0")
            for u in users:
                try:
                    await bot.send_message(u[0], "⏰ Vazifani bajaring!")
                except:
                    pass

async def main():
    await init_db()
    asyncio.create_task(reminder())
    await dp.start_polling(bot)

asyncio.run(main())
