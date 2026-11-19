import os
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from google import genai

BOT_TOKEN = os.environ["BOT_TOKEN"]
GEMINI_KEY = os.environ["GEMINI_KEY"]
client = genai.Client(api_key=GEMINI_KEY)

executor = ThreadPoolExecutor(max_workers=4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! Men BioMnemoAI man ✅\nSavolingni yoz.")

def ask_gemini(question):
    # Gemini 3 Flash - 503 bo'lsa 3 marta urinadi
    for urinish in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=f"Biologiya o'qituvchisisan. O'zbek tilida, qisqa, 10 gapdan oshmasin. Savol: {question}",
                config={"max_output_tokens": 700}
            )
            return response.text
        except Exception as e:
            print(f"Urinish {urinish+1} xato: {e}")
            # Agar model topilmasa, eski flash ga tushadi
            if "404" in str(e) or "NOT_FOUND" in str(e):
                print("3 Flash topilmadi, 2.5 Flash ga o'tyapman...")
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=f"Biologiya o'qituvchisisan. O'zbek tilida, qisqa, 10 gapdan oshmasin. Savol: {question}",
                    config={"max_output_tokens": 700}
                )
                return response.text
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                if urinish < 2:
                    time.sleep(3)
                    continue
            raise e
    return "Javob topilmadi"

async def progress_updater(msg, start_time, stop_event):
    TAXMINIY_VAQT = 5  # 3 Flash tezroq, 5 sek deb oldik
    while not stop_event.is_set():
        otgan = time.time() - start_time
        foiz = min(int((otgan / TAXMINIY_VAQT) * 90), 90)
        qoldi = max(TAXMINIY_VAQT - otgan, 0)
        tola = int(foiz // 10)
        bosh = 10 - tola
        bar = "🟩" * tola + "⬜" * bosh
        try:
            await msg.edit_text(
                f"🤔 O'ylayapman...\n\n{bar} {foiz}%\n"
                f"Taxminiy: {qoldi:.0f} soniya qoldi..."
            )
        except Exception:
            pass
        await asyncio.sleep(0.8)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    start_time = time.time()
    msg = await update.message.reply_text(
        "🤔 O'ylayapman...\n\n⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0%\nTaxminiy: 5 soniya qoldi..."
    )
    stop_event = asyncio.Event()
    progress_task = asyncio.create_task(progress_updater(msg, start_time, stop_event))
    try:
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(executor, ask_gemini, user_text)
        stop_event.set()
        await progress_task
        haqiqiy_vaqt = time.time() - start_time
        await msg.edit_text(f"✅ Tayyor! 100%\n{haqiqiy_vaqt:.1f} soniyada topildi.")
        await update.message.reply_text(text[:4000])
    except Exception as e:
        stop_event.set()
        try:
            await progress_task
        except Exception:
            pass
        print(f"Xato: {e}")
        try:
            await msg.edit_text("Gemini hozir band, 10 sekunddan keyin qayta yozib ko'r 😅")
        except Exception:
            pass

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()