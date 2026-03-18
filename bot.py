import logging
import re
import sqlite3
from datetime import datetime

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)

# ─── CONFIG ──────────────────────────────────────────────────────────────────
BOT_TOKEN  = "YOUR_BOT_TOKEN_HERE"          # @BotFather dan olingan token
ADMIN_IDS  = [123456789]                    # Ustoz(lar)ning Telegram ID si

# ─── CONVERSATION STATES ─────────────────────────────────────────────────────
NAME, PHONE, GROUP, TOPIC, PROOF = range(5)
AWAIT_COMMENT = 10

# ─── TOPICS ──────────────────────────────────────────────────────────────────
TOPICS = {
    "1": "1️⃣ Uy dizayni maketi",
    "2": "2️⃣ Aqlli tog' maketi",
    "3": "3️⃣ Blum taksanomiyasi maketi",
    "4": "4️⃣ STEAM yondashuv asosidagi dars ishlanma",
}

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════════════════════
def db():
    return sqlite3.connect("mustaqil.db", check_same_thread=False)

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            user_id     INTEGER PRIMARY KEY,
            full_name   TEXT NOT NULL,
            phone       TEXT NOT NULL,
            group_name  TEXT NOT NULL,
            registered  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            topic       TEXT NOT NULL,
            file_id     TEXT NOT NULL,
            file_type   TEXT NOT NULL,
            submitted   DATETIME DEFAULT CURRENT_TIMESTAMP,
            grade       INTEGER,
            comment     TEXT,
            graded_at   DATETIME,
            FOREIGN KEY (user_id) REFERENCES students(user_id)
        );
        """)

def get_student(user_id: int):
    with db() as con:
        return con.execute(
            "SELECT user_id, full_name, phone, group_name FROM students WHERE user_id=?",
            (user_id,)
        ).fetchone()

def save_student(user_id, full_name, phone, group_name):
    with db() as con:
        con.execute(
            "INSERT INTO students (user_id, full_name, phone, group_name) VALUES (?,?,?,?)",
            (user_id, full_name, phone, group_name)
        )

def save_submission(user_id, topic, file_id, file_type) -> int:
    with db() as con:
        cur = con.execute(
            "INSERT INTO submissions (user_id, topic, file_id, file_type) VALUES (?,?,?,?)",
            (user_id, topic, file_id, file_type)
        )
        return cur.lastrowid

def get_submission(sub_id: int):
    with db() as con:
        return con.execute(
            "SELECT id, user_id, topic, file_id, file_type, submitted, grade, comment FROM submissions WHERE id=?",
            (sub_id,)
        ).fetchone()

def apply_grade(sub_id, grade, comment):
    with db() as con:
        con.execute(
            "UPDATE submissions SET grade=?, comment=?, graded_at=? WHERE id=?",
            (grade, comment, datetime.now().strftime("%Y-%m-%d %H:%M"), sub_id)
        )

def pending_submissions():
    with db() as con:
        return con.execute("""
            SELECT s.id, s.user_id, st.full_name, st.group_name,
                   s.topic, s.file_id, s.file_type, s.submitted
            FROM submissions s
            JOIN students st ON s.user_id = st.user_id
            WHERE s.grade IS NULL
            ORDER BY s.submitted
        """).fetchall()

def statistics():
    with db() as con:
        total  = con.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        sent   = con.execute("SELECT COUNT(DISTINCT user_id) FROM submissions").fetchone()[0]
        graded = con.execute("SELECT COUNT(*) FROM submissions WHERE grade IS NOT NULL").fetchone()[0]
    return total, sent, total - sent, graded

def students_without_submission():
    with db() as con:
        rows = con.execute("""
            SELECT user_id FROM students
            WHERE user_id NOT IN (SELECT DISTINCT user_id FROM submissions)
        """).fetchall()
    return [r[0] for r in rows]

# ═══════════════════════════════════════════════════════════════════════════════
#  KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════════
def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

def topics_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(TOPICS["1"], callback_data="topic_1")],
        [InlineKeyboardButton(TOPICS["2"], callback_data="topic_2")],
        [InlineKeyboardButton(TOPICS["3"], callback_data="topic_3")],
        [InlineKeyboardButton(TOPICS["4"], callback_data="topic_4")],
        [InlineKeyboardButton("◀️ Orqaga", callback_data="back_main")],
    ])

def proof_back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Orqaga (mavzu tanlash)", callback_data="back_topics")]
    ])

def student_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Mavzu tanlash / Topshiriq yuborish", callback_data="show_topics")],
        [InlineKeyboardButton("✉️ Ustoga xabar yuborish", callback_data="msg_teacher")],
    ])

def cancel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Orqaga", callback_data="back_main")]
    ])

def grade_keyboard(sub_id: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("2️⃣", callback_data=f"g_{sub_id}_2"),
        InlineKeyboardButton("3️⃣", callback_data=f"g_{sub_id}_3"),
        InlineKeyboardButton("4️⃣", callback_data=f"g_{sub_id}_4"),
    ]])

def admin_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Kutayotgan topshiriqlar", callback_data="adm_pending")],
        [InlineKeyboardButton("📊 Statistika",              callback_data="adm_stats")],
        [InlineKeyboardButton("🔔 Eslatma yuborish",        callback_data="adm_remind")],
    ])

def admin_back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Orqaga", callback_data="adm_back")]
    ])

# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
async def show_student_main(target, name: str):
    await target.reply_text(
        f"👋 Xush kelibsiz, *{name}*!\n\nQuyidagi bo'limlardan birini tanlang:",
        parse_mode="Markdown",
        reply_markup=student_main_keyboard()
    )

async def send_to_admins(bot, sub_id, full_name, group, topic, file_id, ftype, submitted):
    caption = (
        f"📥 *Yangi topshiriq* #{sub_id}\n\n"
        f"👤 {full_name}\n"
        f"👥 {group}\n"
        f"📚 {topic}\n"
        f"🕐 {submitted[:16]}"
    )
    kb = grade_keyboard(sub_id)
    for admin_id in ADMIN_IDS:
        try:
            if ftype == "photo":
                await bot.send_photo(admin_id, file_id, caption=caption, parse_mode="Markdown", reply_markup=kb)
            elif ftype == "document":
                await bot.send_document(admin_id, file_id, caption=caption, parse_mode="Markdown", reply_markup=kb)
            else:
                await bot.send_message(admin_id, f"{caption}\n\n🔗 {file_id}", parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            logger.error(f"Admin notify error {admin_id}: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
#  /start
# ═══════════════════════════════════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ctx.user_data.clear()

    if is_admin(uid):
        total, sent, not_sent, graded = statistics()
        await update.message.reply_text(
            f"👨‍🏫 *Ustoz paneli*\n\n"
            f"👥 Ro'yxatdan o'tganlar: *{total}*\n"
            f"📤 Topshiriq yubordilar: *{sent}*\n"
            f"⏳ Hali yuklamadilar: *{not_sent}*\n"
            f"✅ Baholandi: *{graded}*",
            parse_mode="Markdown",
            reply_markup=admin_main_keyboard()
        )
        return ConversationHandler.END

    student = get_student(uid)
    if student:
        # ✅ Allaqachon ro'yxatdan o'tgan — registration conversation ga kirmaydi
        await show_student_main(update.message, student[1])
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 *Mustaqil ta'lim tekshiruv botiga xush kelibsiz!*\n\n"
        "Ro'yxatdan o'tish uchun to'liq *ism, familiya va sharifingizni* kiriting.\n\n"
        "📝 Namuna: `Karimov Alibek Bahodir o'g'li`",
        parse_mode="Markdown"
    )
    return NAME

# ─── 1. Ism ──────────────────────────────────────────────────────────────────
async def state_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if get_student(uid):                            # xavfsizlik tekshiruvi
        await show_student_main(update.message, get_student(uid)[1])
        return ConversationHandler.END

    text = update.message.text.strip()
    if len(text.split()) < 3:
        await update.message.reply_text(
            "❌ *To'liq* ism, familiya va sharifingizni kiriting!\n\n"
            "📝 Namuna: `Karimov Alibek Bahodir o'g'li`",
            parse_mode="Markdown"
        )
        return NAME

    ctx.user_data["full_name"] = text
    kb = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Raqamni ulashish", request_contact=True)]],
        one_time_keyboard=True, resize_keyboard=True
    )
    await update.message.reply_text(
        f"✅ Rahmat, *{text}*!\n\n📱 Telefon raqamingizni yuboring:",
        parse_mode="Markdown", reply_markup=kb
    )
    return PHONE

# ─── 2. Telefon ──────────────────────────────────────────────────────────────
async def state_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text.strip().replace(" ", "")
        if not re.match(r"^\+?[0-9]{9,13}$", phone):
            await update.message.reply_text(
                "❌ Noto'g'ri format. Qayta kiriting:\n`+998901234567`",
                parse_mode="Markdown"
            )
            return PHONE

    ctx.user_data["phone"] = phone
    await update.message.reply_text(
        "✅ Qabul qilindi!\n\n"
        "🎓 Hozir o'qiyotgan *guruhingizni* kiriting:\n"
        "Masalan: `22-guruh` yoki `MT-301`",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return GROUP

# ─── 3. Guruh ────────────────────────────────────────────────────────────────
async def state_group(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if get_student(uid):                            # ikki marta jo'natish himoyasi
        await show_student_main(update.message, get_student(uid)[1])
        return ConversationHandler.END

    group = update.message.text.strip()
    if len(group) < 2:
        await update.message.reply_text("❌ Guruh nomini to'g'ri kiriting:")
        return GROUP

    save_student(uid, ctx.user_data["full_name"], ctx.user_data["phone"], group)

    await update.message.reply_text(
        f"🎉 *Ro'yxatdan o'tdingiz!*\n\n"
        f"👤 {ctx.user_data['full_name']}\n"
        f"👥 {group}\n\n"
        f"Endi mavzuni tanlang:",
        parse_mode="Markdown",
        reply_markup=topics_keyboard()
    )
    return TOPIC

# ─── 4. Mavzu (conversation ichida) ──────────────────────────────────────────
async def state_topic_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    num   = query.data.split("_")[1]
    topic = TOPICS.get(num)
    if not topic:
        return TOPIC

    ctx.user_data["topic"] = topic
    await query.message.reply_text(
        f"✅ Tanlandi: *{topic}*\n\n"
        "📎 *Endi dalilni yuboring:*\n"
        "• 🖼 Rasm (sertifikat, guvohnoma)\n"
        "• 📄 PDF hujjat\n"
        "• 🔗 Havola (link)\n\n"
        "_Ustoz ko'rib chiqqandan so'ng ball qo'shiladi._",
        parse_mode="Markdown",
        reply_markup=proof_back_keyboard()
    )
    return PROOF

# ─── "Orqaga" conversation ichida ────────────────────────────────────────────
async def conv_back_topics(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("📚 Mavzuni tanlang:", reply_markup=topics_keyboard())
    return TOPIC

async def conv_back_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    student = get_student(uid)
    if student:
        await show_student_main(query.message, student[1])
    return ConversationHandler.END

# ─── 5. Dalil (conversation ichida) ──────────────────────────────────────────
async def state_proof(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    topic = ctx.user_data.get("topic", "Noma'lum")
    msg   = update.message

    if msg.photo:
        file_id, ftype = msg.photo[-1].file_id, "photo"
    elif msg.document:
        file_id, ftype = msg.document.file_id, "document"
    elif msg.text and (msg.text.startswith("http") or msg.text.startswith("www")):
        file_id, ftype = msg.text.strip(), "link"
    else:
        await msg.reply_text(
            "❌ *Rasm*, *PDF hujjat* yoki *havola* yuboring!",
            parse_mode="Markdown",
            reply_markup=proof_back_keyboard()
        )
        return PROOF

    sub_id  = save_submission(uid, topic, file_id, ftype)
    student = get_student(uid)
    now     = datetime.now().strftime("%Y-%m-%d %H:%M")
    await send_to_admins(ctx.bot, sub_id, student[1], student[3], topic, file_id, ftype, now)

    await msg.reply_text(
        "✅ *Topshirig'ingiz qabul qilindi!*\n\n"
        "Ustoz ko'rib chiqqanidan so'ng sizga ball qo'yiladi va xabar yuboriladi. ⏳",
        parse_mode="Markdown",
        reply_markup=student_main_keyboard()
    )
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════════
#  GRADING (admin)
# ═══════════════════════════════════════════════════════════════════════════════
async def cb_grade_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return

    _, sub_id_str, grade_str = query.data.split("_")
    ctx.user_data["grading_sub_id"] = int(sub_id_str)
    ctx.user_data["grading_grade"]  = int(grade_str)

    skip_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Izohlarsiz saqlash", callback_data="grade_skip")]
    ])
    await query.message.reply_text(
        f"📝 Topshiriq #{sub_id_str} → Ball: *{grade_str}*\n\n"
        "💬 Izoh yozing yoki pastdagi tugmani bosing:",
        parse_mode="Markdown",
        reply_markup=skip_kb
    )
    return AWAIT_COMMENT

async def cb_grade_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _finalize_grade(ctx, query.message, comment=None)
    return ConversationHandler.END

async def receive_comment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await _finalize_grade(ctx, update.message, comment=update.message.text.strip())
    return ConversationHandler.END

async def _finalize_grade(ctx, reply_target, comment):
    sub_id = ctx.user_data.get("grading_sub_id")
    grade  = ctx.user_data.get("grading_grade")
    if not sub_id or not grade:
        await reply_target.reply_text("❌ Xatolik. Qaytadan urinib ko'ring.")
        return

    apply_grade(sub_id, grade, comment)
    sub        = get_submission(sub_id)
    student_id = sub[1]
    topic      = sub[2]

    note = (
        f"🎉 *Topshirig'ingiz baholandi!*\n\n"
        f"📚 Mavzu: {topic}\n"
        f"⭐ Ball: *{grade}*"
    )
    if comment:
        note += f"\n💬 Ustoz izohi: _{comment}_"

    try:
        await ctx.bot.send_message(student_id, note, parse_mode="Markdown", reply_markup=student_main_keyboard())
    except Exception as e:
        logger.error(f"Student notify error: {e}")

    await reply_target.reply_text(
        f"✅ Ball *{grade}* qo'yildi. Talabaga xabar yuborildi!",
        parse_mode="Markdown",
        reply_markup=admin_main_keyboard()
    )

# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN PANEL CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════════
async def admin_callbacks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    if not is_admin(uid):
        return

    data = query.data

    if data == "adm_back":
        total, sent, not_sent, graded = statistics()
        await query.message.reply_text(
            f"👨‍🏫 *Ustoz paneli*\n\n"
            f"👥 Ro'yxatdan o'tganlar: *{total}*\n"
            f"📤 Topshiriq yubordilar: *{sent}*\n"
            f"⏳ Hali yuklamadilar: *{not_sent}*\n"
            f"✅ Baholandi: *{graded}*",
            parse_mode="Markdown",
            reply_markup=admin_main_keyboard()
        )

    elif data == "adm_stats":
        total, sent, not_sent, graded = statistics()
        await query.message.reply_text(
            f"📊 *Statistika*\n\n"
            f"👥 Ro'yxatdan o'tganlar: *{total}*\n"
            f"📤 Topshiriq yubordilar: *{sent}*\n"
            f"⏳ Hali yuklamadilar: *{not_sent}*\n"
            f"✅ Baholangan: *{graded}*",
            parse_mode="Markdown",
            reply_markup=admin_back_keyboard()
        )

    elif data == "adm_pending":
        subs = pending_submissions()
        if not subs:
            await query.message.reply_text(
                "✅ Hozircha kutayotgan topshiriqlar yo'q.",
                reply_markup=admin_back_keyboard()
            )
            return
        await query.message.reply_text(
            f"📋 Kutayotgan topshiriqlar: *{len(subs)}*",
            parse_mode="Markdown",
            reply_markup=admin_back_keyboard()
        )
        for sub in subs[:15]:
            sub_id, user_id, full_name, group, topic, file_id, ftype, submitted = sub
            caption = (
                f"📥 *Topshiriq* #{sub_id}\n\n"
                f"👤 {full_name}\n👥 {group}\n📚 {topic}\n🕐 {submitted[:16]}"
            )
            kb = grade_keyboard(sub_id)
            try:
                if ftype == "photo":
                    await ctx.bot.send_photo(uid, file_id, caption=caption, parse_mode="Markdown", reply_markup=kb)
                elif ftype == "document":
                    await ctx.bot.send_document(uid, file_id, caption=caption, parse_mode="Markdown", reply_markup=kb)
                else:
                    await ctx.bot.send_message(uid, f"{caption}\n\n🔗 {file_id}", parse_mode="Markdown", reply_markup=kb)
            except Exception as e:
                logger.error(e)

    elif data == "adm_remind":
        ids   = students_without_submission()
        count = 0
        for sid in ids:
            try:
                await ctx.bot.send_message(
                    sid,
                    "⚠️ *Eslatma!*\n\n"
                    "Siz hali mustaqil ta'lim topshirig'ingizni yuklamagansiz.\n"
                    "Iltimos, mavzuni tanlang va dalilni yuboring. 📚",
                    parse_mode="Markdown",
                    reply_markup=student_main_keyboard()
                )
                count += 1
            except Exception as e:
                logger.warning(f"Remind failed for {sid}: {e}")
        await query.message.reply_text(
            f"✅ *{count}* ta talabaga eslatma yuborildi.",
            parse_mode="Markdown",
            reply_markup=admin_back_keyboard()
        )

# ═══════════════════════════════════════════════════════════════════════════════
#  STUDENT PANEL CALLBACKS (conversation tashqarisida)
# ═══════════════════════════════════════════════════════════════════════════════
async def student_callbacks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id

    if is_admin(uid):
        return

    student = get_student(uid)
    if not student:
        await query.message.reply_text("⚠️ Avval ro'yxatdan o'ting: /start")
        return

    data = query.data

    if data == "show_topics":
        ctx.user_data.pop("topic_outside", None)
        await query.message.reply_text("📚 Mavzuni tanlang:", reply_markup=topics_keyboard())

    elif data == "back_main":
        ctx.user_data.pop("await_teacher_msg", None)
        ctx.user_data.pop("topic_outside", None)
        await show_student_main(query.message, student[1])

    elif data == "back_topics":
        ctx.user_data.pop("topic_outside", None)
        await query.message.reply_text("📚 Mavzuni tanlang:", reply_markup=topics_keyboard())

    elif data == "msg_teacher":
        ctx.user_data["await_teacher_msg"] = True
        await query.message.reply_text(
            "✉️ Ustoga yuboriladigan xabarni yozing:",
            reply_markup=cancel_keyboard()
        )

    elif data.startswith("topic_"):
        num   = data.split("_")[1]
        topic = TOPICS.get(num)
        if not topic:
            return
        ctx.user_data["topic_outside"] = topic
        await query.message.reply_text(
            f"✅ Tanlandi: *{topic}*\n\n"
            "📎 *Endi dalilni yuboring:*\n"
            "• 🖼 Rasm (sertifikat, guvohnoma)\n"
            "• 📄 PDF hujjat\n"
            "• 🔗 Havola (link)\n\n"
            "_Ustoz ko'rib chiqqandan so'ng ball qo'shiladi._",
            parse_mode="Markdown",
            reply_markup=proof_back_keyboard()
        )

# ─── Free text + media (conversation tashqarisi) ─────────────────────────────
async def handle_free_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_admin(uid):
        return

    student = get_student(uid)
    if not student:
        return

    # Ustoga xabar yuborish rejimi
    if ctx.user_data.get("await_teacher_msg"):
        ctx.user_data.pop("await_teacher_msg")
        for admin_id in ADMIN_IDS:
            try:
                await ctx.bot.send_message(
                    admin_id,
                    f"✉️ *Talabadan xabar*\n\n"
                    f"👤 {student[1]}\n"
                    f"💬 {update.message.text}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ Ustoz paneli", callback_data="adm_back")
                    ]])
                )
            except Exception as e:
                logger.error(e)
        await update.message.reply_text(
            "✅ Xabaringiz ustoga yuborildi!",
            reply_markup=student_main_keyboard()
        )
        return

    # Mavzu tanlanmagan bo'lsa
    topic = ctx.user_data.get("topic_outside")
    if not topic:
        await update.message.reply_text(
            "📚 Avval mavzu tanlang:",
            reply_markup=student_main_keyboard()
        )
        return

    msg = update.message
    if msg.photo:
        file_id, ftype = msg.photo[-1].file_id, "photo"
    elif msg.document:
        file_id, ftype = msg.document.file_id, "document"
    elif msg.text and (msg.text.startswith("http") or msg.text.startswith("www")):
        file_id, ftype = msg.text.strip(), "link"
    else:
        await msg.reply_text(
            "❌ *Rasm*, *PDF hujjat* yoki *havola* yuboring!",
            parse_mode="Markdown",
            reply_markup=proof_back_keyboard()
        )
        return

    sub_id = save_submission(uid, topic, file_id, ftype)
    ctx.user_data.pop("topic_outside", None)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    await send_to_admins(ctx.bot, sub_id, student[1], student[3], topic, file_id, ftype, now)

    await msg.reply_text(
        "✅ *Topshirig'ingiz qabul qilindi!*\n\n"
        "Ustoz ko'rib chiqqanidan so'ng sizga ball qo'yiladi va xabar yuboriladi. ⏳",
        parse_mode="Markdown",
        reply_markup=student_main_keyboard()
    )

async def handle_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await handle_free_text(update, ctx)

# ═══════════════════════════════════════════════════════════════════════════════
#  DAILY REMINDER
# ═══════════════════════════════════════════════════════════════════════════════
async def daily_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    for sid in students_without_submission():
        try:
            await ctx.bot.send_message(
                sid,
                "⏰ *Kunlik eslatma!*\n\n"
                "Siz hali topshirig'ingizni yuklamagansiz.\n"
                "Bugun ham vaqtingizni boy bermang — mavzuni tanlang va dalilni yuboring! 📚",
                parse_mode="Markdown",
                reply_markup=student_main_keyboard()
            )
        except:
            pass

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # ── Ro'yxatdan o'tish conversation ──────────────────────────────────────
    reg_conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, state_name)],
            PHONE: [MessageHandler((filters.CONTACT | filters.TEXT) & ~filters.COMMAND, state_phone)],
            GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, state_group)],
            TOPIC: [
                CallbackQueryHandler(state_topic_cb,   pattern=r"^topic_\d$"),
                CallbackQueryHandler(conv_back_main,   pattern=r"^back_main$"),
            ],
            PROOF: [
                MessageHandler(
                    (filters.PHOTO | filters.Document.ALL | filters.TEXT) & ~filters.COMMAND,
                    state_proof
                ),
                CallbackQueryHandler(conv_back_topics, pattern=r"^back_topics$"),
                CallbackQueryHandler(conv_back_main,   pattern=r"^back_main$"),
            ],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        allow_reentry=False,   # ← qayta ro'yxatdan o'tishni to'sadi
        name="registration"
    )

    # ── Baholash conversation (admin) ────────────────────────────────────────
    grade_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_grade_button, pattern=r"^g_\d+_[234]$")],
        states={
            AWAIT_COMMENT: [
                CallbackQueryHandler(cb_grade_skip,    pattern=r"^grade_skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_comment),
            ],
        },
        fallbacks=[],
        name="grading"
    )

    app.add_handler(reg_conv)
    app.add_handler(grade_conv)
    app.add_handler(CallbackQueryHandler(admin_callbacks,   pattern=r"^adm_"))
    app.add_handler(CallbackQueryHandler(student_callbacks, pattern=r"^(show_topics|back_main|back_topics|msg_teacher|topic_\d)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_media))

    app.job_queue.run_repeating(daily_reminder, interval=86400, first=60)

    logger.info("✅ Bot ishga tushdi...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
