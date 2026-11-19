import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import google.generativeai as genai
from ddgs import DDGS

# Railway Variables dan oladi - kod ichiga token yozilmaydi!
BOT_TOKEN = os.environ["BOT_TOKEN"]
GEMINI_KEY = os.environ["GEMINI_KEY"]

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# Hozircha barcha mavzuga ruxsat - keyingi versiyada bu yerni o'zgartiramiz
ALLOWED_TOPICS = ["biologiya", "anatomiya", "genetika", "fiziologiya", "hujayra", "dnk"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Men BioMnemoAI man ✅\n\n"
        "Savolingni yoz - men biologiya bo'yicha internetdan qidirib, AI bilan tushuntirib beraman.\n\n"
        "Masalan: Hujayra nima?"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await update.message.reply_text("Qidiryapman... 🔍")

    try:
        # 1. Internetdan qidirish
        search_text = ""
        with DDGS() as ddgs:
            results = list(ddgs.text(user_text, max_results=3))
            for r in results:
                search_text += f"\n- {r['title']}: {r['body']}"

        # 2. Gemini ga berish
        prompt = f"""
        Sen biologiya o'qituvchisisan. O'zbek tilida, sodda va tushunarli javob ber.
        Savol: {user_text}
        Internetdan topilgan ma'lumot: {search_text}
        Faqat aniq, ilmiy javob ber.
        """
        response = model.generate_content(prompt)
        await update.message.reply_text(response.text[:4000])

    except Exception as e:
        print(f"Xato: {e}")
        await update.message.reply_text("Xatolik bo'ldi, qayta urinib ko'r 😅")

def main():
    print("Bot ishlayapti...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()