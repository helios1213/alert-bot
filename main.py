import os
import json
import asyncio
from dotenv import load_dotenv
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from handlers import wallet_handler, token_handler
from utils.scheduler import start_scheduler

# Завантаження змінних середовища
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = Flask(__name__)

# Створення Telegram бота
bot_app = ApplicationBuilder().token(TOKEN).build()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [
        [InlineKeyboardButton("➕ Додати гаманець", callback_data='add_wallet')],
        [InlineKeyboardButton("➕ Додати токен", callback_data='add_token')],
        [InlineKeyboardButton("🗑 Видалити гаманець", callback_data='remove_wallet')],
        [InlineKeyboardButton("🗑 Видалити токен", callback_data='remove_token')],
        [InlineKeyboardButton("📋 Список", callback_data='list')]
    ]
    await update.message.reply_text("👋 Вітаю! Обери дію:", reply_markup=InlineKeyboardMarkup(keyboard))

# Обробка натискань кнопок
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

# Обробка повідомлень
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await wallet_handler.handle_text(update, context)
    await token_handler.handle_text(update, context)

# Додаємо хендлери до Telegram application
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(handle_callback))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

# Webhook endpoint
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    asyncio.run(bot_app.process_update(update))
    return "ok", 200

# Функція встановлення webhook
async def setup_webhook():
    bot = Bot(token=TOKEN)
    await bot.set_webhook(url=WEBHOOK_URL)

# Запуск
if __name__ == "__main__":
    asyncio.run(setup_webhook())
    asyncio.get_event_loop().create_task(start_scheduler(bot_app))
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
