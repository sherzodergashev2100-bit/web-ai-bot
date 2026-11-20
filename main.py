import os
import asyncio
import io
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai

TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

client = genai.Client(api_key=GEMINI_KEY)

# Tugmalar
ASOSIY_MENU = ReplyKeyboardMarkup(
    [["🖼️ Rasm yasash"]],
    resize_keyboard=True
)
ORQAGA_MENU = ReplyKeyboardMarkup(
    [["⬅️ Orqaga"]],
    resize_keyboard=True
)

# Foydalanuvchi qaysi bo'limda ekanini saqlaymiz
user_state = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state[update.effective_user.id] = "menu"
    await update.message.reply_text(
        "👋 Salom! Men rasm yasab bera olaman.\n\nQuyidagi tugmani bosing:",
        reply_markup=ASOSIY_MENU
    )

async def rasm_bolimi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state[update.effective_user.id] = "rasm"
    await update.message.reply_text(
        "🎨 Qanday rasm yasashni xohlaysiz? Yozib yuboring.\n\nMasalan: `qizil kitob`",
        reply_markup=ORQAGA_MENU
    )

async def orqaga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state[update.effective_user.id] = "menu"
    await update.message.reply_text(
        "Asosiy menyuga qaytdik.",
        reply_markup=ASOSIY_MENU
    )

async def xabar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    holat = user_state.get(user_id, "menu")

    if text == "⬅️ Orqaga":
        await orqaga(update, context)
        return

    if text == "🖼️ Rasm yasash":
        await rasm_bolimi(update, context)
        return

    if holat != "rasm":
        await update.message.reply_text(
            "Avval 🖼️ Rasm yasash tugmasini bosing.",
            reply_markup=ASOSIY_MENU
        )
        return

    # RASM YASASH — TEZ VA QOTMAYDIGAN QISM
    await update.message.reply_text("🎨 Rasm yasayapman, biroz kuting...")

    try:
        def yasash():
            response = client.models.generate_content(
                model="gemini-2.0-flash-preview-image-generation",
                contents=f"Generate an image: {text}"
            )
            return response

        # 25 sekunddan ko'p kutmaydi
        response = await asyncio.wait_for(
            asyncio.to_thread(yasash),
            timeout=25
        )

        # Rasmni topamiz
        rasm_topildi = False
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    rasm_bytes = part.inline_data.data
                    await update.message.reply_photo(
                        photo=io.BytesIO(rasm_bytes),
                        caption="✅ Tayyor!",
                        reply_markup=ORQAGA_MENU
                    )
                    rasm_topildi = True
                    break

        if not rasm_topildi:
            await update.message.reply_text(
                "❌ Xatolik yuz berdi, qayta urinib ko'ring.",
                reply_markup=ORQAGA_MENU
            )

    except asyncio.TimeoutError:
        await update.message.reply_text(
            "❌ Xatolik yuz berdi, qayta urinib ko'ring.",
            reply_markup=ORQAGA_MENU
        )
    except Exception as e:
        print(f"Xato: {e}")
        await update.message.reply_text(
            "❌ Xatolik yuz berdi, qayta urinib ko'ring.",
            reply_markup=ORQAGA_MENU
        )

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, xabar))
    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()