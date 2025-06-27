import logging
import os
import asyncio

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

# !! ВАЖЛИВО: Перевіряй, щоб TELEGRAM_TOKEN і WEBHOOK_URL були в .env !!
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

print(f"TOKEN: {TOKEN!r}")  # Для дебага — видалити у проді

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Надішли мені адресу гаманця або токен.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith("0x") and len(text) == 42:
        await handle_wallet_message(update, context)
    else:
        await handle_token_message(update, context)

async def run_bot():
    if not TOKEN or not WEBHOOK_URL:
        print("❌ Не знайдено TELEGRAM_TOKEN або WEBHOOK_URL!")
        return

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Ставимо webhook
    await application.bot.set_webhook(WEBHOOK_URL)

    # Запуск планувальника (асинхронно)
    asyncio.create_task(start_scheduler(application.bot))

    # Запуск самого Telegram Webhook server-а
    await application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        webhook_url=WEBHOOK_URL,
    )

if __name__ == "__main__":
    asyncio.run(run_bot())
