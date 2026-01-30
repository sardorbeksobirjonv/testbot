import asyncio
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode

BOT_TOKEN = "8359011231:AAHExjunUsIpLS6bkNDCgbSCk1rP1FB2kF0"
ADMINS = [8105050189]  # Super adminlar
TEACHERS = {}  # {user_id: {"name": str, "bolimlar": {bolim: {...}}}}
USERS = {}  # {user_id: {"name": str, "fam": str, "teacher": teacher_id}}
pending_reg = {}  # {user_id: {"step": int, ...}}
pending_password = {}
user_tests = {}
used_bolimlar = {}  # {user_id: [bolim1, ...]}
user_results = {}   # {user_id: [{bolim, ok, bad, time}]}
pending_bolim = {}  # {teacher_id: {"name": str, "pass": str}}
pending_savol = {}  # {teacher_id: {"bolim": str, "q": str, "o": [], "a": str, "step": int}}

# ===== MAIN MENU =====
def get_main_menu(user_id):
    kb = []
    if user_id in ADMINS:
        kb.append([InlineKeyboardButton("👨‍💼 Admin panel", callback_data="admin_panel")])
    if user_id in TEACHERS:
        kb.append([InlineKeyboardButton("👩‍🏫 Teacher panel", callback_data="teacher_panel")])
    kb.append([InlineKeyboardButton("Bo‘limlar", callback_data="menu_bolimlar"),
               InlineKeyboardButton("Shaxsiy kabinet", callback_data="menu_kabinet")])
    return InlineKeyboardMarkup(kb)

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in USERS and user_id not in ADMINS and user_id not in TEACHERS:
        pending_reg[user_id] = {"step": 1}
        await update.message.reply_text("Ro‘yxatdan o‘tish uchun ismingizni kiriting:")
        return
    await update.message.reply_text(
        "🏠 Asosiy menyu",
        reply_markup=get_main_menu(user_id)
    )

# ===== REGISTRATION =====
async def reg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in pending_reg:
        return
    reg = pending_reg[user_id]
    if reg["step"] == 1:
        reg["name"] = update.message.text.strip()
        reg["step"] = 2
        await update.message.reply_text("Familiyangizni kiriting:")
    elif reg["step"] == 2:
        reg["fam"] = update.message.text.strip()
        reg["step"] = 3
        # Teacherlar ro‘yxati
        if not TEACHERS:
            await update.message.reply_text("Hozircha teacherlar mavjud emas. Keyinroq urinib ko‘ring.")
            pending_reg.pop(user_id)
            return
        kb = [[InlineKeyboardButton(t["name"], callback_data=f"reg_teacher_{tid}")] for tid, t in TEACHERS.items()]
        await update.message.reply_text("O‘qituvchini tanlang:", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text("Iltimos, tugmani bosing.")

async def reg_teacher_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in pending_reg:
        return
    teacher_id = int(query.data.split("_")[-1])
    reg = pending_reg.pop(user_id)
    USERS[user_id] = {"name": reg["name"], "fam": reg["fam"], "teacher": teacher_id}
    await query.message.edit_text("Ro‘yxatdan o‘tdingiz! Asosiy menyu:", reply_markup=get_main_menu(user_id))
    # Teacherga habar
    if teacher_id in TEACHERS:
        await context.bot.send_message(
            teacher_id,
            f"Yangi o‘quvchi: {reg['name']} {reg['fam']} sizni tanladi!"
        )

# ===== ADMIN PANEL =====
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in ADMINS:
        return
    kb = [
        [InlineKeyboardButton("Teacher qo‘shish", callback_data="admin_add_teacher")],
        [InlineKeyboardButton("Teacherlar ro‘yxati", callback_data="admin_teachers")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_back")]
    ]
    await query.message.edit_text("👨‍💼 Admin panel", reply_markup=InlineKeyboardMarkup(kb))

async def admin_add_teacher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    pending_reg[user_id] = {"step": "add_teacher"}
    await query.message.edit_text("Yangi teacherning Telegram user ID sini kiriting:")

async def admin_add_teacher_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in pending_reg or pending_reg[user_id].get("step") != "add_teacher":
        return
    try:
        tid = int(update.message.text.strip())
        TEACHERS[tid] = {"name": f"Teacher_{tid}", "bolimlar": {}}
        await update.message.reply_text(f"Teacher qo‘shildi! ID: {tid}")
    except:
        await update.message.reply_text("Xato! To‘g‘ri ID kiriting.")
    pending_reg.pop(user_id)

async def admin_teachers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "Teacherlar:\n"
    for tid, t in TEACHERS.items():
        text += f"{tid}: {t['name']}\n"
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_panel")]]))

# ===== TEACHER PANEL =====
async def teacher_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in TEACHERS:
        return
    kb = [
        [InlineKeyboardButton("Bo‘lim qo‘shish", callback_data="teacher_add_bolim")],
        [InlineKeyboardButton("Bo‘lim o‘chirish", callback_data="teacher_del_bolim")],
        [InlineKeyboardButton("Savol qo‘shish", callback_data="teacher_add_savol")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_back")]
    ]
    await query.message.edit_text("👩‍🏫 Teacher panel", reply_markup=InlineKeyboardMarkup(kb))

# ===== TEACHER: BO‘LIM QO‘SHISH =====
async def teacher_add_bolim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    pending_bolim[user_id] = {}
    await query.message.edit_text("Bo‘lim nomini kiriting:")

async def teacher_add_bolim_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in pending_bolim:
        return
    if "name" not in pending_bolim[user_id]:
        pending_bolim[user_id]["name"] = update.message.text.strip()
        await update.message.reply_text("Bo‘lim uchun parol kiriting:")
    else:
        name = pending_bolim[user_id]["name"]
        parol = update.message.text.strip()
        TEACHERS[user_id]["bolimlar"][name] = {"pass": parol, "questions": []}
        await update.message.reply_text(f"Bo‘lim '{name}' qo‘shildi!", reply_markup=get_main_menu(user_id))
        pending_bolim.pop(user_id)

# ===== TEACHER: BO‘LIM O‘CHIRISH =====
async def teacher_del_bolim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    bolimlar = TEACHERS[user_id]["bolimlar"]
    if not bolimlar:
        await query.message.edit_text("Bo‘limlar yo‘q.")
        return
    kb = [[InlineKeyboardButton(b, callback_data=f"teacher_delb_{b}")] for b in bolimlar]
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="teacher_panel")])
    await query.message.edit_text("O‘chirish uchun bo‘limni tanlang:", reply_markup=InlineKeyboardMarkup(kb))

async def teacher_delb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    bolim = query.data.split("_", 2)[2]
    TEACHERS[user_id]["bolimlar"].pop(bolim, None)
    await query.message.edit_text(f"Bo‘lim '{bolim}' o‘chirildi.", reply_markup=get_main_menu(user_id))

# ===== TEACHER: SAVOL QO‘SHISH =====
async def teacher_add_savol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    bolimlar = TEACHERS[user_id]["bolimlar"]
    if not bolimlar:
        await query.message.edit_text("Avval bo‘lim qo‘shing.")
        return
    kb = [[InlineKeyboardButton(b, callback_data=f"teacher_adds_{b}")] for b in bolimlar]
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="teacher_panel")])
    await query.message.edit_text("Savol qo‘shiladigan bo‘limni tanlang:", reply_markup=InlineKeyboardMarkup(kb))

async def teacher_adds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    bolim = query.data.split("_", 2)[2]
    pending_savol[user_id] = {"bolim": bolim, "step": 1, "o": []}
    await query.message.edit_text("Savol matnini kiriting:")

async def teacher_adds_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in pending_savol:
        return

    text = update.message.text.strip()
    if text == "/stop":
        await update.message.reply_text("✅ Savol qo‘shish yakunlandi!", reply_markup=get_main_menu(user_id))
        pending_savol.pop(user_id, None)
        return

    # ANS= bilan avtomatik savol va variantlarni ajratish
    if "ANS=" in text:
        parts = text.split("ANS=")
        savol_va_variant = parts[0].strip()
        javob = parts[1].strip()

        # Savol va variantlarni ajratish
        lines = [l.strip() for l in savol_va_variant.split('\n') if l.strip()]
        if len(lines) < 2:
            await update.message.reply_text("❗ Savol va variantlarni to‘g‘ri kiriting!")
            return
        savol = lines[0]
        variants = lines[1:]
        if javob not in variants:
            await update.message.reply_text("❗ To‘g‘ri javob variantlar ichida yo‘q!")
            return

        bolim = pending_savol[user_id]["bolim"]
        TEACHERS[user_id]["bolimlar"][bolim]["questions"].append({
            "q": savol,
            "o": variants,
            "a": javob
        })
        await update.message.reply_text("✅ Savol qo‘shildi! Yangi savol kiriting yoki /stop deb yakunlang.")
        # Savol qo‘shish davom etadi
        return

    # Oddiy tartibda savol qo‘shish (eski usul)
    s = pending_savol[user_id]
    if s.get("step", 1) == 1:
        s["q"] = text
        s["step"] = 2
        await update.message.reply_text("Variantlarni vergul bilan kiriting (masalan: A,B,C,D):")
    elif s["step"] == 2:
        s["o"] = [x.strip() for x in text.split(",")]
        s["step"] = 3
        await update.message.reply_text("To‘g‘ri javobni kiriting (variant matni):")
    elif s["step"] == 3:
        s["a"] = text
        bolim = s["bolim"]
        TEACHERS[user_id]["bolimlar"][bolim]["questions"].append({
            "q": s["q"], "o": s["o"], "a": s["a"]
        })
        await update.message.reply_text("✅ Savol qo‘shildi! Yangi savol kiriting yoki /stop deb yakunlang.")
        s["step"] = 1  # Yangi savol uchun qayta boshlanadi

# ===== MENU HANDLER =====
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "menu_back":
        await query.message.edit_text("🏠 Asosiy menyu", reply_markup=get_main_menu(user_id))
        return

    if data == "admin_panel":
        await admin_panel(update, context)
        return
    if data == "admin_add_teacher":
        await admin_add_teacher(update, context)
        return
    if data == "admin_teachers":
        await admin_teachers(update, context)
        return
    if data == "teacher_panel":
        await teacher_panel(update, context)
        return
    if data == "teacher_add_bolim":
        await teacher_add_bolim(update, context)
        return
    if data == "teacher_del_bolim":
        await teacher_del_bolim(update, context)
        return
    if data.startswith("teacher_delb_"):
        await teacher_delb(update, context)
        return
    if data == "teacher_add_savol":
        await teacher_add_savol(update, context)
        return
    if data.startswith("teacher_adds_"):
        await teacher_adds(update, context)
        return

    # ===== BO‘LIMLAR =====
    if data == "menu_bolimlar":
        if user_id not in USERS:
            await query.message.edit_text("Ro‘yxatdan o‘ting!")
            return
        teacher_id = USERS[user_id]["teacher"]
        bolimlar = TEACHERS.get(teacher_id, {}).get("bolimlar", {})
        ishlagan = used_bolimlar.get(user_id, [])
        kb = []
        for b in bolimlar:
            if b in ishlagan:
                kb.append([InlineKeyboardButton(f"{b} ✅", callback_data="used")])
            else:
                kb.append([InlineKeyboardButton(b, callback_data=f"bolim_{b}")])
        kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_back")])
        await query.message.edit_text(
            "📚 Bo‘limni tanlang:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # ===== SHAXSIY KABINET =====
    if data == "menu_kabinet":
        results = user_results.get(user_id, [])
        if not results:
            text = "🗂 Siz hali hech qaysi bo‘limda test ishlamagansiz."
        else:
            text = "🗂 <b>Shaxsiy kabinet</b>\n\n"
            for i, r in enumerate(results, 1):
                text += (f"{i}. <b>{r['bolim']}</b>\n"
                         f"   ✅ To‘g‘ri: {r['ok']}\n"
                         f"   ❌ Xato: {r['bad']}\n"
                         f"   ⏳ Vaqt: {r['time']}\n\n")
        kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_back")]]
        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )
        return

    # ===== FOYDALANUVCHI BO‘LIM TANLADI =====
    if data.startswith("bolim_"):
        bolim = data.split("_", 1)[1]
        teacher_id = USERS[user_id]["teacher"]
        if bolim in used_bolimlar.get(user_id, []):
            await query.message.edit_text(
                "⛔ Siz bu bo‘limni allaqachon ishlagansiz.\n\n🏠 Asosiy menyu",
                reply_markup=get_main_menu(user_id)
            )
            return
        pending_password[user_id] = (teacher_id, bolim)
        await query.message.edit_text(f"🔐 {bolim} bo‘limi uchun parolni kiriting:")
        return

    if data == "used":
        await query.message.answer("⛔ Bu bo‘limni allaqachon ishlagansiz.")
        return

# ===== PASSWORD HANDLER =====
async def password_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in pending_password:
        # Admin yoki teacher uchun maxsus steplar
        if user_id in pending_reg and pending_reg[user_id].get("step") == "add_teacher":
            await admin_add_teacher_step(update, context)
        elif user_id in pending_bolim:
            await teacher_add_bolim_step(update, context)
        elif user_id in pending_savol:
            await teacher_adds_step(update, context)
        elif user_id in pending_reg:
            await reg_handler(update, context)
        return
    teacher_id, bolim = pending_password[user_id]
    text = update.message.text.strip()
    if text == TEACHERS[teacher_id]["bolimlar"][bolim]["pass"]:
        kb = [[InlineKeyboardButton("Testni boshlash", callback_data=f"starttest_{bolim}")]]
        await update.message.reply_text(
            f"✅ Parol to‘g‘ri! {bolim} bo‘limidagi testni boshlash uchun tugmani bosing",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    else:
        await update.message.reply_text("❌ Parol xato, qayta urinib ko‘ring")
    pending_password.pop(user_id)

# ===== TEST BOSHLASH =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("starttest_"):
        bolim = data.split("_", 1)[1]
        teacher_id = USERS[user_id]["teacher"]

        # Eski testni bloklash (agar mavjud bo'lsa, tugatib yuboriladi)
        if user_id in user_tests:
            # Eski testni yakunlab, foydalanuvchiga test bloklanganini bildiradi
            await query.message.reply_text(
                "⛔ Eski test yakunlandi va bloklandi. Yangi test boshlanmoqda."
            )
            await finish_test(query.message, user_id, timeout=True)

        # Yangi testni boshlash
        user_tests[user_id] = {
            "bolim": bolim,
            "list": TEACHERS[teacher_id]["bolimlar"][bolim]["questions"],
            "i": 0,
            "ok": 0,
            "bad": 0,
            "start_time": datetime.now(),
            "end_time": datetime.now() + timedelta(minutes=45),
            "teacher_id": teacher_id,
        }
        await query.message.edit_text(f"⏳ Test boshlandi (45 daqiqa)")
        asyncio.create_task(test_timeout_watcher(user_id, query.message))
        await send_question(query.message, user_id)

# Test uchun fon kuzatuvchi (timeout) vazifa
async def test_timeout_watcher(user_id, message):
    await asyncio.sleep(45 * 60)  # 45 minut kutadi
    if user_id in user_tests:
        await finish_test(message, user_id, timeout=True)

# ===== SAVOL YUBORISH =====
async def send_question(message, user_id):
    if user_id not in user_tests:
        return
    data = user_tests[user_id]
    if datetime.now() > data["end_time"]:
        await finish_test(message, user_id, timeout=True)
        return
    if data["i"] >= len(data["list"]):
        await finish_test(message, user_id)
        return

    q = data["list"][data["i"]]
    kb = [[InlineKeyboardButton(o, callback_data=f"answer_{o}")] for o in q["o"]]
    await message.reply_text(
        f"❓ {q['q']}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ===== JAVOB QABUL QILISH =====
async def answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in user_tests:
        return

    data = user_tests[user_id]
    if datetime.now() > data["end_time"]:
        await finish_test(query.message, user_id, timeout=True)
        return

    q = data["list"][data["i"]]
    selected = query.data.split("_", 1)[1]

    if selected == q["a"]:
        data["ok"] += 1
        await query.message.reply_text("✅ To‘g‘ri")
    else:
        data["bad"] += 1
        await query.message.reply_text(f"❌ Xato\nTo‘g‘ri: {q['a']}")

    data["i"] += 1
    await send_question(query.message, user_id)

# ===== TESTNI /stop bilan to‘xtatish =====
async def stop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_tests:
        await finish_test(update.message, user_id, timeout=False)
    else:
        await update.message.reply_text("Sizda faol test yo‘q.", reply_markup=get_main_menu(user_id))

# ===== TESTNI YAKUNLASH =====
async def finish_test(message, user_id, timeout=False):
    if user_id not in user_tests:
        return
    data = user_tests.pop(user_id)
    used_bolimlar.setdefault(user_id, []).append(data["bolim"])
    duration_sec = (datetime.now() - data["start_time"]).seconds
    duration_min = duration_sec // 60
    sec = duration_sec % 60
    status = "⏱ Vaqt tugadi" if timeout else "🏁 Test tugadi"
    user_results.setdefault(user_id, []).append({
        "bolim": data["bolim"],
        "ok": data["ok"],
        "bad": data["bad"],
        "time": f"{duration_min} daqiqa {sec} soniya"
    })
    await message.reply_text(
        f"{status}\n✅ To‘g‘ri: {data['ok']}\n❌ Xato: {data['bad']}\n⏳ Vaqt: {duration_min} daqiqa {sec} soniya",
        reply_markup=get_main_menu(user_id)
    )

    # === Natijani teacherga yuborish ===
    user_info = USERS.get(user_id, {})
    ism = user_info.get("name", "Noma'lum")
    fam = user_info.get("fam", "")
    teacher_id = data.get("teacher_id")  # Faqat testdan olamiz!
    bolim = data["bolim"]
    natija = (
        f"📝 Test natijasi\n"
        f"👤 O‘quvchi: {ism} {fam}\n"
        f"📚 Bo‘lim: {bolim}\n"
        f"✅ To‘g‘ri: {data['ok']}\n"
        f"❌ Xato: {data['bad']}\n"
        f"⏳ Vaqt: {duration_min} daqiqa {sec} soniya"
    )
    # Faqat teacherga yuboriladi
    if teacher_id and teacher_id in TEACHERS:
        try:
            await message.get_bot().send_message(teacher_id, natija)
        except Exception:
            pass

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop_handler))  # /stop komandasi
    app.add_handler(CallbackQueryHandler(menu_handler, pattern="^(menu_|admin_|teacher_|bolim_|used)"))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^starttest_"))
    app.add_handler(CallbackQueryHandler(reg_teacher_select, pattern="^reg_teacher_"))
    app.add_handler(CallbackQueryHandler(answer_handler, pattern="^answer_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, password_handler))
    print("✅ Bot ishga tushdi")
    app.run_polling()

if __name__ == "__main__":
    main()