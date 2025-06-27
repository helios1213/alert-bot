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

print(f"TOKEN: {TOKEN!r}")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

app = Flask(__name__)

application = ApplicationBuilder().token(TOKEN).build()

@app.route("/", methods=["GET"])
def healthcheck():
    # Це просто для перевірки Render, чи живий сервер
    return "Bot is running!"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    print("Webhook received data:", data)
    update = Update.de_json(data, application.bot)
    # Тут put/update_queue треба запустити у event loop
    application.create_task(application.update_queue.put(update))
    return "OK"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Надішли мені адресу гаманця або токен.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith("0x") and len(text) == 42:
        await handle_wallet_message(update, context)
    else:
        await handle_token_message(update, context)

async def after_startup(app_):
    await app_.bot.set_webhook(WEBHOOK_URL)
    app_.create_task(start_scheduler(app_.bot))

def main():
    if not TOKEN or not WEBHOOK_URL:
        print("❌ Не знайдено TELEGRAM_TOKEN або WEBHOOK_URL!")
        return

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.post_init = after_startup

    # IMPORTANT: Запускаємо саме application.run_webhook!
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        webhook_url=WEBHOOK_URL,
    )

if __name__ == "__main__":
    main()
