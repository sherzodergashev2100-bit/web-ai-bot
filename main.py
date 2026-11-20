import os
import io
import re
import logging
import math
import random
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from google import genai

# ---------- SOZLAMALAR ----------
TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

logging.basicConfig(level=logging.INFO)
HOLAT = {}

# ---------- KLAVIATURALAR ----------
def admin_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("👥 Users"), KeyboardButton("📩 Mail to users"), KeyboardButton("📁 Add file")],
         [KeyboardButton("📕 Add pdf"), KeyboardButton("✏️ Change"), KeyboardButton("🤖 Ask Manu AI")],
         [KeyboardButton("📊 Statistika"), KeyboardButton("🆘 Support")],
         [KeyboardButton("🖼️ Rasm yasash"), KeyboardButton("🎨 AI Rasm")]],
        resize_keyboard=True
    )

def user_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🤖 Manu AI")],
         [KeyboardButton("🖼️ Rasm yasash"), KeyboardButton("🎨 AI Rasm")],
         [KeyboardButton("🆘 Support")]],
        resize_keyboard=True
    )

def back_kb():
    return ReplyKeyboardMarkup([[KeyboardButton("⬅️ Orqaga")]], resize_keyboard=True)

# ---------- GEMINI ----------
def gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)

async def ask_manu_ai(prompt: str) -> str:
    try:
        client = gemini_client()
        res = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=f"Sen Manu AI san, o'zbek tilida qisqa va aniq javob ber. Savol: {prompt}"
        )
        return res.text or "Javob chiqmadi."
    except Exception as e:
        return f"Xato: {e}"

# ---------- GEMINI PRO PILLOW KOD YOZADI ----------

def kodni_tozalash(text: str) -> str:
    # ```python ... ``` ichidan kodni olamiz
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()

def gemini_pillow_kod_yoz(prompt: str) -> str:
    client = gemini_client()
    system_prompt = f"""
Sen professional Python Pillow rassomisan.
Foydalanuvchi so'rovi: "{prompt}"

Vazifa: Faqat Python kodi yoz, hech qanday izoh, matn yozma.
Kod quyidagi qoidalarga amal qilsin:
- from PIL import Image, ImageDraw, ImageFont, math, random dan foydalanish mumkin
- 900x700 o'lchamli chiroyli, rangli, professional rasm chiz
- Yuqorida sarlavha, pastda izoh bo'lsin
- Shakllar: ellipse, rectangle, polygon, line, arc, text ishlat
- Sodda kartochka emas, haqiqiy illustratsiya chiz. Masalan hujayra desa - yadro, mitoxondriya, membrana chiz. Odam desa - bosh, tana, qo'l, oyoq chiz. Intizom desa - soat, kitob, reja, galochka chiz.
- Oxirida shunday funksiya bo'lsin:
def make_image():
    img = Image.new("RGB", (900, 700), color=(220, 240, 255))
    draw = ImageDraw.Draw(img)
    # ... bu yerda chizish ...
    return img
Faqat kodni qaytar.
"""
    res = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=system_prompt
    )
    return kodni_tozalash(res.text or "")

def kodni_ishga_tushir(kod: str) -> io.BytesIO:
    # Xavfsiz muhitda kodni ishlatamiz
    local_vars = {}
    safe_globals = {
        "Image": Image,
        "ImageDraw": ImageDraw,
        "ImageFont": ImageFont,
        "math": math,
        "random": random,
        "io": io,
    }
    exec(kod, safe_globals, local_vars)
    # make_image funksiyasini topamiz
    make_image = local_vars.get("make_image") or safe_globals.get("make_image")
    if not make_image:
        # Agar funksiya bo'lmasa, img o'zgaruvchisini qidiramiz
        img = local_vars.get("img") or safe_globals.get("img")
        if img is None:
            raise ValueError("make_image topilmadi")
        return img_to_bytes(img)
    img = make_image()
    return img_to_bytes(img)

def img_to_bytes(img) -> io.BytesIO:
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

async def pro_rasm_yasa(update: Update, prompt: str):
    try:
        await update.message.reply_text(f"✏️ Gemini sen uchun kod yozyapti: {prompt}...")
        kod = gemini_pillow_kod_yoz(prompt)
        print("GEMINI KOD:", kod[:500])
        try:
            rasm = kodni_ishga_tushir(kod)
        except Exception as e1:
            # 1 marta qayta urinib ko'ramiz - Gemini ga xatoni aytib tuzattiramiz
            print("Birinchi urinish xato:", e1)
            await update.message.reply_text("Kodda xato chiqdi, tuzatyapman...")
            kod2 = gemini_pillow_kod_yoz(f"{prompt}. Oldingi kodda xato: {e1}. To'g'ri kod yoz.")
            rasm = kodni_ishga_tushir(kod2)
        await update.message.reply_photo(photo=rasm, caption=f"🎨 {prompt}\n\nGemini yozgan Pillow kod bilan chizildi")
    except Exception as e:
        await update.message.reply_text(f"Rasm yasashda xato: {e}\nQaytadan urinib ko'r.")

# ---------- HANDLERLAR ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    HOLAT[user_id] = None
    if user_id == ADMIN_ID:
        await update.message.reply_text("Salom Admin! 👋", reply_markup=admin_kb())
    else:
        await update.message.reply_text("Salom! 👋 Manu AI\n\nNima chizaylik? Sen ayt, Gemini kod yozib chizib beradi.\nMasalan: hujayra, odam, intizom", reply_markup=user_kb())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    matn = (update.message.text or "").strip()
    is_admin = (user_id == ADMIN_ID)

    if matn == "⬅️ Orqaga":
        HOLAT[user_id] = None
        await update.message.reply_text("Bosh menyu", reply_markup=admin_kb() if is_admin else user_kb())
        return

    holat = HOLAT.get(user_id)

    if holat == "manu_ai_kutmoqda":
        HOLAT[user_id] = None
        javob = await ask_manu_ai(matn)
        await update.message.reply_text(javob, reply_markup=admin_kb() if is_admin else user_kb())
        return

    if holat in ["ai_rasm_kutmoqda", "rasm_yasash_kutmoqda"]:
        HOLAT[user_id] = None
        await pro_rasm_yasa(update, matn)
        await update.message.reply_text("Yana nima chizaylik?", reply_markup=admin_kb() if is_admin else user_kb())
        return

    if matn == "🤖 Ask Manu AI" or matn == "🤖 Manu AI":
        HOLAT[user_id] = "manu_ai_kutmoqda"
        await update.message.reply_text("Savolingni yoz:", reply_markup=back_kb())
        return

    if matn == "🎨 AI Rasm" or matn == "🖼️ Rasm yasash":
        HOLAT[user_id] = "rasm_yasash_kutmoqda"
        await update.message.reply_text("Nima chizaylik? ✏️\n\nSen ayt, Gemini o'sha uchun maxsus kod yozib chizib beradi.\n\nMasalan:\n• hujayra\n• odam kitob o'qiyapti\n• intizomli o'quvchi\n• kosmosda raketa\n• mushuk", reply_markup=back_kb())
        return

    if matn in ["👥 Users", "📩 Mail to users", "📁 Add file", "📕 Add pdf", "✏️ Change", "📊 Statistika", "🆘 Support"]:
        await update.message.reply_text(f"{matn} bo'limi hozircha tayyorlanmoqda.", reply_markup=admin_kb() if is_admin else user_kb())
        return

    await update.message.reply_text("Iltimos, tugmalardan foydalaning", reply_markup=admin_kb() if is_admin else user_kb())

def main():
    if not TOKEN:
        print("BOT_TOKEN topilmadi!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()