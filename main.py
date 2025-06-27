import logging
import os

from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from handlers.wallet_handler import handle_wallet_message
from handlers.token_handler import handle_token_message
from utils.scheduler import start_scheduler

from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

print(f"TOKEN: {TOKEN!r}")  # Можна прибрати у продакшн

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Flask app
app = Flask(__name__)
application = None  # Тут буде твій telegram-application

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Надішли мені адресу гаманця або токен.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith("0x") and len(text) == 42:
        await handle_wallet_message(update, context)
    else:
        await handle_token_message(update, context)

async def after_startup(application_):
    # Ставимо webhook, тільки якщо його ще не поставлено
    await application_.bot.set_webhook(WEBHOOK_URL)
    # Запуск планувальника (асинхронно)
    application_.create_task(start_scheduler(application_.bot))

@app.route("/", methods=["GET", "POST"])
async def webhook():
    global application
    if request.method == "POST":
        data = request.get_json(force=True)
        print("Webhook received data:", data)   # Додаємо лог!
        update = Update.de_json(data, application.bot)
        await application.update_queue.put(update)
        return "OK"
    print("GET request to /")  # ще лог для GET
    return "Bot is running!"

def main():
    global application
    if not TOKEN or not WEBHOOK_URL:
        print("❌ Не знайдено TELEGRAM_TOKEN або WEBHOOK_URL!")
        return

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.post_init = after_startup

    # Flask сам піднімає сервер, тому просто запускаємо Flask
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

if __name__ == "__main__":
    main()
