import logging
import os
import asyncio
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

# --- Додаємо debug print для перевірки токена ---
print(f"TOKEN: {TOKEN!r}")  # Тут побачиш токен в логах!

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

app = Flask(__name__)
application = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Надішли мені адресу гаманця або токен.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith("0x") and len(text) == 42:
        await handle_wallet_message(update, context)
    else:
        await handle_token_message(update, context)

@app.route("/", methods=["GET", "POST"])
async def webhook():
    if request.method == "POST":
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        await application.update_queue.put(update)
        return "OK"
    return "Bot is running!"

async def run_bot():
    global application
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await application.bot.set_webhook(WEBHOOK_URL)

    # Запуск планувальника
    asyncio.create_task(start_scheduler(application.bot))

    await application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        webhook_url=WEBHOOK_URL,
    )

if __name__ == "__main__":
    asyncio.run(run_bot())
