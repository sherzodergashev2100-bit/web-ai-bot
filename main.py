import os
import json
import logging
import requests
import fitz
import io
import re
import asyncio
import time
import random
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from google import genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= SOZLAMALAR =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MODEL = "gemini-3.8-flash"

client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

def yukla(nom, default):
    if os.path.exists(nom):
        try:
            return json.load(open(nom, encoding="utf-8"))
        except:
            return default
    return default

def saqla(nom, data):
    json.dump(data, open(nom, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

PDFS = yukla("pdfs.json", [])
USERS = yukla("users.json", {})
FILES = yukla("files.json", [])
HOLAT = {}
XOTIRA = {}
VAQTINCHA = {}
SPAM = defaultdict(list)

BAD_WORDS = ["porno", "seks", "siktir", "qotoq", "blyat", "xuy", "pizda"]
RASMI_SOZLAR = ["rasm chiz", "chizib ber", "rasmini chiz", "draw", "image", "kartina chiz", "realistik", "rasm yasab ber"]

# ================= KLAVIATURALAR =================
def user_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🤖 Manu AI"), KeyboardButton("🆘 Support")],
         [KeyboardButton("🧪 Test"), KeyboardButton("🖼️ Rasm yasash")],
         [KeyboardButton("🎨 AI Rasm")]],
        resize_keyboard=True
    )

def admin_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("👥 Users"), KeyboardButton("📩 Mail to users"), KeyboardButton("📁 Add file")],
         [KeyboardButton("📕 Add pdf"), KeyboardButton("✏️ Change"), KeyboardButton("🤖 Ask Manu AI")],
         [KeyboardButton("📊 Statistika"), KeyboardButton("🆘 Support")]],
        resize_keyboard=True
    )

def orqaga_kb():
    return ReplyKeyboardMarkup([[KeyboardButton("🔙 Orqaga")]], resize_keyboard=True)

# ================= PILLOW - MNEMONIKA KARTOCHKA =================
def mnemonika_rasmi_yasa(matn: str, sarlavha: str = "Manual AI"):
    img = Image.new("RGB", (1080, 1080), (18, 32, 62))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 1080, 140], fill=(0, 180, 120))
    try:
        font_big = ImageFont.truetype("DejaVuSans-Bold.ttf", 52)
        font = ImageFont.truetype("DejaVuSans.ttf", 38)
    except:
        font_big = ImageFont.load_default()
        font = ImageFont.load_default()
    draw.text((60, 35), sarlavha[:30], fill=(255, 255, 255), font=font_big)
    y = 200
    sozlar = matn.split()
    qator = ""
    for s in sozlar:
        if len(qator + " " + s) > 38:
            draw.text((60, y), qator, fill=(255, 255, 255), font=font)
            y += 55
            qator = s
            if y > 950:
                break
        else:
            qator = (qator + " " + s).strip()
    if qator and y <= 950:
        draw.text((60, y), qator, fill=(255, 255, 255), font=font)
    draw.text((60, 1000), "BioMnemoAI • Manual AI", fill=(0, 180, 120), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ================= OCR - 4 MARTA AYLANTIRISH =================
def sahifani_oqish(page):
    pix = page.get_pixmap(dpi=200)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    for urinish in range(4):
        burchak = urinish * 90
        rasm = img.rotate(burchak, expand=True) if burchak != 0 else img
        buf = io.BytesIO()
        rasm.save(buf, format="PNG")
        open("temp.png", "wb").write(buf.getvalue())
        try:
            f = client.files.upload(file="temp.png")
            resp = client.models.generate_content(model=MODEL, contents=["Bu rasmda yozilgan matnni aynan ko'chirib yoz. Matn bo'lmasa faqat 'OQILMADI' de.", f])
            matn = resp.text.strip()
            if len(matn) > 30 and "OQILMADI" not in matn:
                return matn
        except Exception as e:
            logger.error(f"OCR xato: {e}")
            continue
    return ""

async def pdfni_backendda_oqish(app, idx):
    pdf = PDFS[idx]
    try:
        file_id = pdf["drive_link"].split("/d/")[1].split("/")[0]
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        r = requests.get(url, timeout=120)
        doc = fitz.open(stream=r.content, filetype="pdf")
        all_text = ""
        for i, page in enumerate(doc):
            all_text += f"\n--- Sahifa {i+1} ---\n" + sahifani_oqish(page)
            if (i+1) % 10 == 0:
                open(pdf["teksti"], "w", encoding="utf-8").write(all_text)
        open(pdf["teksti"], "w", encoding="utf-8").write(all_text)
        PDFS[idx]["tayyor"] = True
        saqla("pdfs.json", PDFS)
        await app.bot.send_message(chat_id=ADMIN_ID, text=f"✅ PDF tayyor: {pdf['nomi']}\nMavzular: {', '.join(pdf['mavzular'])}")
    except Exception as e:
        logger.error(f"PDF xato: {e}")
        await app.bot.send_message(chat_id=ADMIN_ID, text=f"❌ PDF o'qishda xato: {pdf['nomi']} - {e}")

# ================= MANUAL AI =================
def mavzu_ruxsatmi(savol: str):
    savol_low = savol.lower()
    barcha = [m for p in PDFS for m in p.get("mavzular", [])]
    if not barcha:
        return False, barcha
    for m in barcha:
        if m.lower() in savol_low:
            return True, barcha
    try:
        resp = client.models.generate_content(model=MODEL, contents=f"Ruxsatli mavzular: {', '.join(barcha)}\nSavol: {savol}\nSavol shu mavzularga tegishlimi? Faqat HA yoki YO'Q de.")
        if "HA" in resp.text.upper():
            return True, barcha
    except:
        pass
    return False, barcha

def kerakli_parcha(savol: str, matn: str):
    sozlar = re.findall(r'\w+', savol.lower())
    parchalar = matn.split("--- Sahifa")
    ballar = []
    for p in parchalar:
        ball = sum(1 for s in sozlar if len(s) > 3 and s in p.lower())
        ballar.append((ball, p))
    ballar.sort(key=lambda x: x[0], reverse=True)
    return "\n".join([p for _, p in ballar[:3]])[:12000]

async def manual_ai_javob(savol: str, user_id):
    # 1. AI Rasm so'ralsa - halol "qila olmayman"
    if any(s in savol.lower() for s in RASMI_SOZLAR):
        return (
            "❌ Bu rasmni qila olmayman.\n\n"
            "Men AI rasm generatori emasman. Realistik hujayra, odam, hayvon rasmini chiza olmayman.\n\n"
            "✅ O'rniga senga Pillow kartochka yasab beraman — chiroyli mnemonika kartochka.\n"
            "🖼️ Rasm yasash ni bos va mavzuni yoz."
        )
    # 2. Qayta yoz
    if savol.lower() in ["qayta yoz", "qayta", "tushunmadim", "boshqacha tushuntir", "soddaroq", "yana bir marta"]:
        x = XOTIRA.get(user_id)
        if not x:
            return "Nimani qayta yozay? Avval savol bering."
        resp = client.models.generate_content(model=MODEL, contents=f"Oldingi savol: {x['savol']}\nOldingi javob: {x['javob']}\nShu savolga yana, yanada sodda, 5-sinf bolasi tushunadigan qilib, boshqa misollar bilan javob ber. Boshqa mavzuga o'tma.")
        XOTIRA[user_id]["javob"] = resp.text
        return resp.text
    # 3. Mavzu filtri
    ruxsat, barcha = mavzu_ruxsatmi(savol)
    if not ruxsat:
        mavzular_txt = ', '.join(barcha) if barcha else 'Hali PDF qoshilmagan'
        return "⛔ Bu savol ruxsat berilgan mavzularga kirmaydi.\n\nRuxsatli mavzular: " + mavzular_txt + "\n\nIltimos, shu mavzulardan savol bering."
    # 4. PDF dan parcha topish
    kontekst = ""
    for pdf in PDFS:
        if not pdf.get("tayyor"):
            continue
        if not os.path.exists(pdf["teksti"]):
            continue
        matn = open(pdf["teksti"], encoding="utf-8").read()
        kontekst += f"\n[Kitob: {pdf['nomi']}]\n" + kerakli_parcha(savol, matn)
    if not kontekst.strip():
        return "📚 Kitob hali tayyor emas. Biroz kuting."
    resp = client.models.generate_content(model=MODEL, contents=f"""Sen Manual AI san. Sen Gemini emassan, Google tomonidan yaratilmagansan.

QAT'IY QOIDA:
1. Faqat quyidagi KITOB parchasi bo'yicha javob ber. O'zingcha qo'shma, uydirma.
2. Javob kitobda yo'q bo'lsa: "Bu savolga kitobda javob yo'q."
3. Format: Ta'rif + Misol (kitobdan) + Mnemonika

KITOB PARCHASI:
{kontekst}

Savol: {savol}""")
    XOTIRA[user_id] = {"savol": savol, "javob": resp.text}
    return resp.text

def spammi(user_id):
    hozir = time.time()
    SPAM[user_id] = [t for t in SPAM[user_id] if hozir - t < 60]
    if len(SPAM[user_id]) >= 3:
        return True
    SPAM[user_id].append(hozir)
    return False

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    if uid not in USERS:
        USERS[uid] = {"username": user.username or "", "firstname": user.first_name or "", "count": 0, "ball": 0, "ban": False}
    USERS[uid]["count"] += 1
    USERS[uid]["username"] = user.username or USERS[uid]["username"]
    USERS[uid]["firstname"] = user.first_name or USERS[uid]["firstname"]
    saqla("users.json", USERS)
    HOLAT[user.id] = "asosiy"
    if user.id == ADMIN_ID:
        await update.message.reply_text(f"👋 Salom Admin {user.first_name}!", reply_markup=admin_kb())
    else:
        await update.message.reply_text(
            f"👋 Salom {user.first_name}!\n\nMen Manual AI man.\n🤖 Manu - kitob bo'yicha savol\n🧪 Test - bilimni tekshirish\n🖼️ Rasm yasash - mnemonika kartochka\n🎨 AI Rasm - haqiqiy rasm (qila olamanmi?)\n🆘 Support - admin bilan aloqa",
            reply_markup=user_kb()
        )

# ================= ASOSIY HANDLER =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    matn = update.message.text.strip() if update.message.text else ""
    holat = HOLAT.get(user_id, "asosiy")

    if str(user_id) in USERS and USERS[str(user_id)].get("ban"):
        await update.message.reply_text("⛔ Siz bloklangansiz.")
        return

    # ---------- ADMIN ----------
    if user_id == ADMIN_ID:
        if matn == "📕 Add pdf":
            HOLAT[user_id] = "add_pdf_nomi"; VAQTINCHA[user_id] = {}
            await update.message.reply_text("📕 PDF nomini yozing:\nMasalan: Biologiya 1-qism", reply_markup=orqaga_kb())
            return
        if holat == "add_pdf_nomi":
            VAQTINCHA[user_id]["nomi"] = matn; HOLAT[user_id] = "add_pdf_link"
            await update.message.reply_text("🔗 Google Drive havolasini yuboring:\nDrive da 'Anyone with link can view' bo'lsin.")
            return
        if holat == "add_pdf_link":
            if "drive.google.com" not in matn:
                await update.message.reply_text("❌ Bu Drive havola emas. Qaytadan yuboring.")
                return
            VAQTINCHA[user_id]["drive_link"] = matn; HOLAT[user_id] = "add_pdf_mavzu"
            await update.message.reply_text("📚 Ruxsatli mavzularni vergul bilan yozing:\nMasalan: hujayra, to'qima, fotosintez")
            return
        if holat == "add_pdf_mavzu":
            VAQTINCHA[user_id]["mavzular"] = [m.strip() for m in matn.split(",") if m.strip()]
            HOLAT[user_id] = "add_pdf_qiyinlik"
            await update.message.reply_text("🎯 Qiyinlikni tanlang:\n5-sinf / 9-sinf / Abituriyent deb yozing")
            return
        if holat == "add_pdf_qiyinlik":
            yangi = {"nomi": VAQTINCHA[user_id]["nomi"], "drive_link": VAQTINCHA[user_id]["drive_link"], "mavzular": VAQTINCHA[user_id]["mavzular"], "qiyinlik": matn, "teksti": f"kitob_{len(PDFS)+1}.txt", "tayyor": False}
            PDFS.append(yangi); saqla("pdfs.json", PDFS); HOLAT[user_id] = "asosiy"
            await update.message.reply_text(f"✅ PDF qo'shildi!\n📕 {yangi['nomi']}\n📚 {', '.join(yangi['mavzular'])}\n🎯 {yangi['qiyinlik']}\n\n⏳ Orqa fonda o'qiyapman...", reply_markup=admin_kb())
            asyncio.create_task(pdfni_backendda_oqish(context.application, len(PDFS)-1))
            return
        if matn == "👥 Users":
            aktiv = len([u for u in USERS.values() if u.get("count", 0) > 0])
            await update.message.reply_text(f"👥 Jami: {len(USERS)}\nAktiv: {aktiv}\n\nBirinchi 100 ta:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"100 ta ko'rish ({len(USERS)})", callback_data="users_100")]]))
            return
        if matn == "📊 Statistika":
            await update.message.reply_text(f"📊 Statistika:\n👥 Foydalanuvchilar: {len(USERS)}\n📕 PDF lar: {len(PDFS)} - Tayyor: {len([p for p in PDFS if p.get('tayyor')])}\n📁 Fayllar: {len(FILES)}")
            return
        if matn == "📁 Add file":
            HOLAT[user_id] = "add_file_kutmoqda"
            await update.message.reply_text("📁 Faylni yuboring - video, audio, rasm, hujjat. Yoki /empty yozing.")
            return
        if matn == "📩 Mail to users":
            HOLAT[user_id] = "mail_media"
            await update.message.reply_text("📩 Mail: Avval media yuboring (rasm/video/fayl) yoki /empty yozing.")
            return
        if holat == "mail_media":
            VAQTINCHA[user_id] = {"media": None if matn == "/empty" else "matn_only"}
            HOLAT[user_id] = "mail_matn"
            await update.message.reply_text("✍️ Endi xabar matnini yozing:")
            return
        if holat == "mail_matn":
            VAQTINCHA[user_id]["matn"] = matn
            HOLAT[user_id] = "asosiy"
            await update.message.reply_text(f"👀 PREVIEW:\n\n{matn}\n\n👥 {len(USERS)} ta foydalanuvchiga boradi.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Yuborish", callback_data="mail_yubor"), InlineKeyboardButton("✏️ O'zgartirish", callback_data="mail_ozgartir")]]))
            return
        if matn == "✏️ Change":
            royxat = "\n".join([f"{i+1}. {p['nomi']} - {', '.join(p['mavzular'])}" for i, p in enumerate(PDFS)]) or "PDF yo'q"
            await update.message.reply_text(f"✏️ Change:\n\n{royxat}\n\nO'chirish uchun: /del_pdf_1 deb yozing")
            return
        if matn == "🤖 Ask Manual":
            HOLAT[user_id] = "manual_ai"
            await update.message.reply_text("🤖 Manual AI rejimidasan (Admin tekshiruv). Savol yoz:")
            return
        if matn == "🆘 Support":
            await update.message.reply_text("Support: @shukrullomakhkamov")
            return

    # ---------- UMUMIY TUGMALAR ----------
    if matn == "🔙 Orqaga":
        HOLAT[user_id] = "asosiy"
        await update.message.reply_text("Asosiy menyu", reply_markup=admin_kb() if user_id == ADMIN_ID else user_kb())
        return
    if matn == "🤖 Manual AI":
        HOLAT[user_id] = "manual_ai"
        await update.message.reply_text("🤖 Manual AI rejimidasan.\nFaqat admin ruxsat bergan mavzular va PDF lar bo'yicha javob beraman.\nSavolingni yoz:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("⌨️ Savol yozish"), KeyboardButton("🔙 Orqaga")]], resize_keyboard=True))
        return
    if matn == "⌨️ Savol yozish":
        await update.message.reply_text("Savolingni yoz ✍️")
        return
    if matn == "🆘 Support":
        await update.message.reply_text("🆘 Support: @shukrullomakhkamov ga yozing, sizga yordam beramiz.")
        return
    if matn == "🖼️ Rasm yasash":
        HOLAT[user_id] = "rasm_kutmoqda"
        await update.message.reply_text("🖼️ Qaysi mavzuda mnemonika kartochka yasay? Masalan: hujayra")
        return
    if matn == "🎨 AI Rasm":
        HOLAT[user_id] = "rasm_kutmoqda"
        await update.message.reply_text(
            "🎨 AI Rasm haqida halol javob:\n\n"
            "❌ Men Midjourney / DALL-E kabi haqiqiy AI rasm chiza olmayman.\n"
            "Masalan: 'Hujayra rasmini chiz' desangiz — realistik hujayra rasmini yarata olmayman.\n\n"
            "✅ Men qila oladigan narsa:\n"
            "🖼️ Pillow orqali chiroyli mnemonika kartochka yasash — matn + rang + sarlavha\n\n"
            "Kartochka yasaymi? Mavzuni yozing, masalan: hujayra",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🖼️ Rasm yasash"), KeyboardButton("🔙 Orqaga")]], resize_keyboard=True)
        )
        return
    if holat == "rasm_kutmoqda":
        # Agar AI rasm so'rasa - qila olmayman deydi
        if any(s in matn.lower() for s in RASMI_SOZLAR):
            await update.message.reply_text("❌ Bu rasmni qila olmayman. Men realistik AI rasm chiza olmayman.\n\n✅ O'rniga Pillow kartochka yasab beraman. Faqat mavzuni yozing, masalan: hujayra")
            return
        HOLAT[user_id] = "manual_ai"
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
        javob = await manual_ai_javob(matn, user_id)
        qisqa = javob[:350]
        rasm_buf = mnemonika_rasmi_yasa(qisqa, sarlavha=matn[:25])
        await update.message.reply_photo(photo=rasm_buf, caption=f"🖼️ {matn} - Mnemonika kartochka\n\n{javob[:500]}")
        return
    if matn == "🧪 Test":
        HOLAT[user_id] = "test"
        if not PDFS or not any(p.get("tayyor") for p in PDFS):
            await update.message.reply_text("📚 Hali PDF tayyor emas.")
            return
        kontekst = ""
        for p in PDFS:
            if p.get("tayyor") and os.path.exists(p["teksti"]):
                kontekst += open(p["teksti"], encoding="utf-8").read()[:8000]
        try:
            resp = client.models.generate_content(model=MODEL, contents=f"Quyidagi kitob matnidan 5 ta test tuz. Har birida 4 ta variant bo'lsin. Format: Savol? A) ... B) ... C) ... D) ... To'g'ri: A\n\n{kontekst[:8000]}")
            await update.message.reply_text(f"🧪 Test:\n\n{resp.text}\n\nJavoblaringizni yozing, men tekshiraman.")
        except Exception as e:
            await update.message.reply_text(f"Test tuzishda xato: {e}")
        return

    if holat == "manual_ai":
        if any(b in matn.lower() for b in BAD_WORDS):
            await update.message.reply_text("⛔ Bu mavzu ruxsat berilmagan.")
            return
        if spammi(user_id):
            await update.message.reply_text("⏳ Judayam tez yozayapsan. 1 daqiqa kuting.")
            return
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        javob = await manual_ai_javob(matn, user_id)
        await update.message.reply_text(javob)
        return

    # Fayl qabul qilish
    if update.message.photo or update.message.document or update.message.video or update.message.voice:
        if user_id == ADMIN_ID and holat in ["add_file_kutmoqda", "mail_media"]:
            file_id = ""
            if update.message.photo:
                file_id = update.message.photo[-1].file_id
            elif update.message.document:
                file_id = update.message.document.file_id
            elif update.message.video:
                file_id = update.message.video.file_id
            FILES.append({"file_id": file_id, "caption": update.message.caption or ""})
            saqla("files.json", FILES)
            HOLAT[user_id] = "asosiy"
            await update.message.reply_text("✅ Fayl saqlandi!", reply_markup=admin_kb())
            return
        await update.message.reply_text("Fayl qabul qilinmaydi. Iltimos matn yozing.")
        return

    await update.message.reply_text("Iltimos, tugmalardan foydalaning.", reply_markup=admin_kb() if user_id == ADMIN_ID else user_kb())

# ================= CALLBACK =================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "users_100":
        royxat = ""
        for u in list(USERS.values())[:100]:
            royxat += "@" + str(u.get('username','-')) + " - " + str(u.get('firstname','')) + "\n"
        await q.message.reply_text("Birinchi 100 ta:\n\n" + (royxat or "Foydalanuvchi yoq"))
    elif q.data == "mail_yubor":
        matn = VAQTINCHA.get(q.from_user.id, {}).get("matn", "")
        yuborildi = 0
        for uid in list(USERS.keys()):
            try:
                await context.bot.send_message(chat_id=int(uid), text=matn)
                yuborildi += 1
            except:
                pass
        await q.message.reply_text("Yuborildi: " + str(yuborildi) + " / " + str(len(USERS)) + " ta foydalanuvchiga") context.bot.send_message(chat_id=int(uid), text=matn)
                yuborildi += 1
            except:
                pass
        await q.message.reply_text(f"✅ Yuborildi: {yuborildi} / {len(USERS)} ta foydalanuvchiga")
    elif q.data == "mail_ozgartir":
        await q.message.reply_text("✏️ O'zgartirish:\n[Media] - yangi media yuboring\n[Matn] - yangi matn yozing", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Media", callback_data="mail_media_oz"), InlineKeyboardButton("Matn", callback_data="mail_matn_oz")]]))
    elif q.data == "mail_matn_oz":
        HOLAT[q.from_user.id] = "mail_matn"
        await q.message.reply_text("Yangi matnni yozing:")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    logger.info(f"Manu AI PRO {MODEL} ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()