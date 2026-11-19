import os
import asyncio
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from google import genai

BOT_TOKEN = os.environ["BOT_TOKEN"]
GEMINI_KEY = os.environ["GEMINI_KEY"]
client = genai.Client(api_key=GEMINI_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! Men BioMnemoAI man ✅\nSavolingni yoz.")

def ask_gemini(question):
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=f"Biologiya o'qituvchisisan. O'zbek tilida, qisqa, 10 gapdan oshmasin. Savol: {question}",
        config={"max_output_tokens": 700}
    )
    return response.text

async def progress_updater(msg, start_time, stop_event):
    # Taxminiy vaqt: 6 sekund deb olamiz
    TAXMINIY_VAQT = 6
    while not stop_event.is_set():
        otgan = time.time() - start_time
        # 90% gacha boradi, 100% ni faqat tayyor bo'lganda ko'rsatamiz
        foiz = min(int((otgan / TAXMINIY_VAQT) * 90), 90)
        qoldi = max(TAXMINIY_VAQT - otgan, 0)
        
        # Chiroyli progress bar
        tola = int(foiz // 10)
        bosh = 10 - tola
        bar = "🟩" * tola + "⬜" * bosh
        
        try:
            await msg.edit_text(
                f"🤔 O'ylayapman...\n\n{bar} {foiz}%\n"
                f"Taxminiy: {qoldi:.0f} soniya qoldi..."
            )
        except:
            pass
        await asyncio.sleep(0.8)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    start_time = time.time()
    
    msg = await update.message.reply_text("🤔 O'ylayapman...\n\n⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0%\nTaxminiy: 6 soniya qoldi...")
    
    stop_event = asyncio.Event()
    progress_task = asyncio.create_task(progress_updater(msg, start_time, stop_event))
    
    try:
        text = await asyncio.to_thread(ask_gemini, user_text)
        stop_event.set()
        await progress_task
        
        haqiqiy_vaqt = time.time() - start_time
        # Avval 100% qilib, keyin javobni yuboramiz
        await msg.edit_text(f"✅ Tayyor! 100%\n{haqiqiy_vaqt:.1f} soniyada topildi.")
        await update.message.reply_text(text[:4000])
        
    except Exception as e:
        stop_event.set()
        await progress_task
        print(f"Xato: {e}")
        await msg.edit_text("Sekinlik uchun uzr, qayta yozib ko'r 😅")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()