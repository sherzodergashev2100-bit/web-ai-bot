import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import google.generativeai as genai

BOT_TOKEN = os.environ["BOT_TOKEN"]
GEMINI_KEY = os.environ["GEMINI_KEY"]

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Men BioMnemoAI man ✅\n\n"
        "Savolingni yoz - men biologiya bo'yicha tushuntirib beraman.\n\n"
        "Masalan: Hujayra nima?"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await update.message.reply_text("O'ylayapman... 🤔")

    try:
        prompt = f"""
        Sen biologiya o'qituvchisisan. O'zbek tilida, sodda va tushunarli javob ber.
        Savol: {user_text}
        Faqat aniq, ilmiy javob ber. Misollar bilan tushuntir.
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