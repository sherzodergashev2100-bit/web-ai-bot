import os
import io
import logging
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from google import genai

# ---------- SOZLAMALAR ----------
TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # o'zingni Telegram ID'ingni Railway Variables ga yoz

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Holatlar: user_id -> nima kutayotgani
HOLAT = {}

# ---------- KLAVIATURALAR ----------

def admin_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("👥 Users"), KeyboardButton("📩 Mail to users"), KeyboardButton("📁 Add file")],
         [KeyboardButton("📕 Add pdf"), KeyboardButton("✏️ Change"), KeyboardButton("🤖 Ask Manu AI")],
         [KeyboardButton("📊 Statistika"), KeyboardButton("🆘 Support")],
         [KeyboardButton("🖼️ Rasm yasash"), KeyboardButton("🎨 AI Rasm")],
         [KeyboardButton("🍌 Nano Banana")]],
        resize_keyboard=True
    )

def user_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🤖 Manu AI"), KeyboardButton("🍌 Nano Banana")],
         [KeyboardButton("🖼️ Rasm yasash"), KeyboardButton("🎨 AI Rasm")],
         [KeyboardButton("🆘 Support")]],
        resize_keyboard=True
    )

def back_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("⬅️ Orqaga")]],
        resize_keyboard=True
    )

# ---------- GEMINI FUNKSIYALAR ----------

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

async def nano_banana_yasa(update: Update, prompt: str):
    try:
        await update.message.reply_text("🍌 Chizyapman, biroz kut...")
        client = gemini_client()
        result = client.models.generate_content(
            model="gemini-nano-banana-2.1",
            contents=prompt
        )
        for part in result.candidates[0].content.parts:
            if part.inline_data:
                data = part.inline_data.data
                # data bytes yoki base64 bo'lishi mumkin
                if isinstance(data, str):
                    import base64
                    data = base64.b64decode(data)
                await update.message.reply_photo(photo=io.BytesIO(data), caption=f"🍌 {prompt}")
                return
        await update.message.reply_text("Rasm chiqmadi, boshqacha yozib ko'r.")
    except Exception as e:
        await update.message.reply_text(f"Nano Banana xato: {e}")

# ---------- PILLOW BILAN ODDIY RASM (AI RASM) ----------

def pillow_rasm_yasa(matn: str) -> io.BytesIO:
    img = Image.new("RGB", (800, 600), color=(25, 25, 112))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except:
        font = ImageFont.load_default()
    draw.text((40, 250), matn[:40], fill="white", font=font)
    draw.text((40, 320), "AI Rasm - Manu AI", fill="yellow", font=font)
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

# ---------- HANDLERLAR ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    HOLAT[user_id] = None
    if user_id == ADMIN_ID:
        await update.message.reply_text("Salom Admin! 👋", reply_markup=admin_kb())
    else:
        await update.message.reply_text("Salom! 👋 Manu AI botga xush kelibsiz.", reply_markup=user_kb())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    matn = (update.message.text or "").strip()
    is_admin = (user_id == ADMIN_ID)

    # Orqaga
    if matn == "⬅️ Orqaga":
        HOLAT[user_id] = None
        await update.message.reply_text("Bosh menyu", reply_markup=admin_kb() if is_admin else user_kb())
        return

    # --- HOLAT BO'YICHA KUTISH ---
    holat = HOLAT.get(user_id)

    if holat == "manu_ai_kutmoqda":
        HOLAT[user_id] = None
        javob = await ask_manu_ai(matn)
        await update.message.reply_text(javob, reply_markup=admin_kb() if is_admin else user_kb())
        return

    if holat == "nano_banana_kutmoqda":
        HOLAT[user_id] = None
        await nano_banana_yasa(update, matn)
        await update.message.reply_text("Yana yasaymi?", reply_markup=admin_kb() if is_admin else user_kb())
        return

    if holat == "ai_rasm_kutmoqda":
        HOLAT[user_id] = None
        rasm = pillow_rasm_yasa(matn)
        await update.message.reply_photo(photo=rasm, caption=f"🎨 {matn}")
        await update.message.reply_text("Tayyor!", reply_markup=admin_kb() if is_admin else user_kb())
        return

    if holat == "rasm_yasash_kutmoqda":
        HOLAT[user_id] = None
        rasm = pillow_rasm_yasa(matn)
        await update.message.reply_photo(photo=rasm, caption=f"🖼️ {matn}")
        return

    # --- TUGMALAR ---

    # Admin: Ask Manu AI
    if matn == "🤖 Ask Manu AI":
        HOLAT[user_id] = "manu_ai_kutmoqda"
        await update.message.reply_text("Savolingni yoz:", reply_markup=back_kb())
        return

    # User: Manu AI
    if matn == "🤖 Manu AI":
        HOLAT[user_id] = "manu_ai_kutmoqda"
        await update.message.reply_text("Savolingni yoz:", reply_markup=back_kb())
        return

    # Nano Banana - ikkalasi uchun ham bir xil
    if matn == "🍌 Nano Banana":
        HOLAT[user_id] = "nano_banana_kutmoqda"
        await update.message.reply_text("🍌 Nano Banana\n\nRasmni tasvirlab yoz, masalan: hujayra, yadro bilan, yorqin rangda", reply_markup=back_kb())
        return

    # AI Rasm - Pillow
    if matn == "🎨 AI Rasm":
        HOLAT[user_id] = "ai_rasm_kutmoqda"
        await update.message.reply_text("🎨 Nima yozilgan rasm yasaylik? Matnni yoz:", reply_markup=back_kb())
        return

    # Rasm yasash - Pillow
    if matn == "🖼️ Rasm yasash":
        HOLAT[user_id] = "rasm_yasash_kutmoqda"
        await update.message.reply_text("🖼️ Rasm uchun matn yoz:", reply_markup=back_kb())
        return

    # Admin tugmalari - hozircha oddiy javob
    if matn in ["👥 Users", "📩 Mail to users", "📁 Add file", "📕 Add pdf", "✏️ Change", "📊 Statistika", "🆘 Support"]:
        await update.message.reply_text(f"{matn} bo'limi hozircha tayyorlanmoqda. Tez orada qo'shamiz.", reply_markup=admin_kb() if is_admin else user_kb())
        return

    # Agar hech qaysi tugmaga to'g'ri kelmasa
    await update.message.reply_text("Iltimos, tugmalardan foydalaning", reply_markup=admin_kb() if is_admin else user_kb())

# ---------- ISHGA TUSHIRISH ----------

def main():
    if not TOKEN:
        print("TOKEN topilmadi! Railway Variables ga TOKEN yoz.")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()