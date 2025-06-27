import asyncio
import logging
import os
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackContext,
    ContextTypes,
    MessageHandler,
    filters,
)

from wallet_handler import handle_wallet_message
from token_handler import handle_token_message
from scheduler import start_scheduler

# Налаштування логування
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Ініціалізація Flask
flask_app = Flask(__name__)

# Отримання токена з середовища
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL")  # має бути https://your-app.onrender.com

# Ініціалізація Telegram Application
application = ApplicationBuilder().token(TOKEN).build()


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Надішли мені токен або адресу гаманця.")


# Обробка повідомлень
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text.startswith("0x") and len(text) == 42:
        await handle_wallet_message(update, context)
    elif text.startswith("0x") and len(text) == 66:
        await handle_token_message(update, context)
    else:
        await update.message.reply_text("Надішли правильну адресу гаманця або токена.")


# Додавання хендлерів
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


# Flask маршрут для webhook
@flask_app.route("/", methods=["POST"])
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return "ok"


async def main():
    # Запуск шедулера
    await start_scheduler(application.bot)

    # Встановлення webhook
    await application.bot.set_webhook(url=WEBHOOK_URL)

    # Запуск Flask
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


if __name__ == "__main__":
    asyncio.run(main())
