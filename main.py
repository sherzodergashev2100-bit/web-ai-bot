import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from ddgs import DDGS
import google.generativeai as genai

# SHU YERGA O'ZINGNIKINNI YOZ
import os
BOT_TOKEN = os.environ["BOT_TOKEN"]
GEMINI_KEY = os.environ["GEMINI_KEY"]
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

async def javob_ber(update: Update, context: ContextTypes.DEFAULT_TYPE):
    savol = update.message.text
    await update.message.reply_text("🔍 Qidiryapman...")

    # 1. Web dan qidirish
    matnlar = ""
    with DDGS() as ddgs:
        natijalar = list(ddgs.text(savol, max_results=5))
        for r in natijalar:
            matnlar += f"{r['title']}: {r['body']}\n"

    # 2. AI ga qisqa tushuntirishga berish
    prompt = f"""
    Quyidagi internet ma'lumotlari asosida savolga o'zbek tilida,
    juda qisqa, 3-4 qator, tushunarli qilib javob ber. 
    Ortiqcha gap yozma.
    Savol: {savol}
    Ma'lumotlar: {matnlar}
    """
    javob = model.generate_content(prompt).text

    await update.message.reply_text(javob)

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, javob_ber))
print("Bot ishlayapti...")
app.run_polling()