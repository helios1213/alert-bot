import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from flask import Flask, request
from threading import Thread

from handlers import wallet_handler, token_handler
from utils.scheduler import start_scheduler

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Flask для webhook-серверу
flask_app = Flask(__name__)

# Telegram Application
app = ApplicationBuilder().token(TOKEN).build()


# === Telegram handlers ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [
        [InlineKeyboardButton("➕ Додати гаманець", callback_data='add_wallet')],
        [InlineKeyboardButton("➕ Додати токен", callback_data='add_token')],
        [InlineKeyboardButton("🗑 Видалити гаманець", callback_data='remove_wallet')],
        [InlineKeyboardButton("🗑 Видалити токен", callback_data='remove_token')],
        [InlineKeyboardButton("📋 Список", callback_data='list')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('👋 Вітаю! Обери дію:', reply_markup=reply_markup)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'add_wallet':
        await wallet_handler.prompt_wallet_address(update, context)
    elif data == 'add_token':
        await token_handler.prompt_token_wallet_choice(update, context)
    elif data == 'remove_wallet':
        await wallet_handler.prompt_wallet_removal(update, context)
    elif data == 'remove_token':
        await token_handler.prompt_token_removal(update, context)
    elif data == 'list':
        await token_handler.show_user_data(update, context)
    else:
        await token_handler.handle_callback_query(update, context)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await wallet_handler.handle_text(update, context)
    await token_handler.handle_text(update, context)


# === Flask route ===
@flask_app.post("/webhook")
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), app.bot)
        await app.update_queue.put(update)
        return "ok"
    return "error", 400


# === Webhook setup ===
async def set_webhook():
    await app.bot.set_webhook(WEBHOOK_URL)


# === Start all ===
def run_flask():
    flask_app.run(host="0.0.0.0", port=10000)


async def main():
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    await set_webhook()
    await start_scheduler(app)


if __name__ == "__main__":
    # Flask у потоці
    Thread(target=run_flask).start()

    import asyncio
    asyncio.run(main())
