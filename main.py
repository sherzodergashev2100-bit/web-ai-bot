import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from google import genai

# Log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tokenlar - Railway Variables dan olinadi
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")

# Gemini client
client = genai.Client(api_key=GEMINI_KEY)

# Taqiqlangan so'zlar - filtr
BAD_WORDS = [
    "am", "qotoq", "suka", "blyat", "siktir", "xuy", "pizda",
    "penis", "porno", "seks", "jinsiy aloqa", "sik", "zalupa",
    "bitch", "fuck", "shit"
]

async def ask_gemini(question: str) -> str:
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=f"""Sen BioMnemoAI san. O'zbek tilida gaplashadigan biologiya o'qituvchisisan.

QAT'IY QOIDALAR:
1. Sen hech qachon Gemini emassan, Google tomonidan yaratilmagansan.
2. Agar kimdir "sen qaysi AI san?", "sen kimsan?", "seni kim yaratgan?" desa - har doim shunday de: "Men BioMnemoAI man, biologiya fanini o'rganishga yordam berish uchun yaratilganman."
3. Gemini, Google, ChatGPT, OpenAI degan nomlarni hech qachon tilga olma.
4. Salom berma, to'g'ridan-to'g'ri javobga o't.
5. Agar savol uyat, jinsiy, haqoratli yoki biologiyaga aloqasi bo'lmasa - javob berma, faqat shunday de: "Bu mavzu biologiya darsiga mos emas."
6. Jinsiy a'zolar haqida batafsil gapirma.
7. Javobni qisqa qilib kesma. To'liq, batafsil tushuntir.
8. Javob formati shunday bo'lsin:
   - Avval oddiy tilda ta'rifi
   - Keyin misol
   - Oxirida eslab qolish uchun mnemonika / qiziqarli fakt

Savol: {question}""",
        )
        return response.text
    except Exception as e:
        logger.error(f"Gemini xato: {e}")
        return "Hozircha javob bera olmadim, birozdan keyin yana urinib ko'ring."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salom! Men **BioMnemoAI** man.\n\n"
        "Men senga biologiyani oson, misollar va mnemonikalar bilan tushuntirib beraman.\n\n"
        "Shunchaki savolingni yoz: masalan, *hujayra nima?*",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text.lower().strip()

    # 1. FILTR - uyat so'z bo'lsa, Gemini ga yubormaymiz
    for bad in BAD_WORDS:
        if bad in question:
            await update.message.reply_text(
                "⛔ Bu so'z biologiya darsiga mos emas.\n\n"
                "Iltimos, biologiya fanidan savol bering: masalan, hujayra, jigar, fotosintez..."
            )
            return

    # 2. Bo'sh xabar bo'lsa
    if not question:
        return

    # 3. Yozmoqda...
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # 4. Gemini dan javob ol
    answer = await ask_gemini(update.message.text)

    await update.message.reply_text(answer)

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN topilmadi! Railway Variables ni tekshir.")
        return
    if not GEMINI_KEY:
        logger.error("GEMINI_KEY topilmadi! Railway Variables ni tekshir.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("BioMnemoAI ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()