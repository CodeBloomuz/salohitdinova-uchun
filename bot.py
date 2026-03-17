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

@dp.message(F.text == "/start")
async def start(msg: types.Message, state: FSMContext):
    await state.set_state(Form.name)
    await msg.answer("F.I.Sh kiriting:")

@dp.message(Form.name)
async def get_name(msg: types.Message, state: FSMContext):
    if not valid_name(msg.text):
        await msg.answer("To‘liq yozing!")
        return
    await state.update_data(name=msg.text)
    await state.set_state(Form.phone)
    await msg.answer("Telefon:")

@dp.message(Form.phone)
async def get_phone(msg: types.Message, state: FSMContext):
    if not valid_phone(msg.text):
        await msg.answer("Noto‘g‘ri!")
        return
    await state.update_data(phone=msg.text)
    await state.set_state(Form.group)
    await msg.answer("Guruh:")

@dp.message(Form.group)
async def get_group(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect("db.db") as db:
        await db.execute("INSERT OR REPLACE INTO users VALUES(?,?,?,?,?)",
                         (msg.from_user.id, data["name"], data["phone"], msg.text, 0))
        await db.commit()
    await state.clear()
    await msg.answer("Ro‘yxatdan o‘tdingiz!")

async def main():
    await init_db()
    await dp.start_polling(bot)

asyncio.run(main())
