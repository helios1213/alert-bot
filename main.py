import os
import logging
from dotenv import load_dotenv
from flask import Flask, request
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from handlers.wallet_handler import (
    prompt_wallet_address,
    prompt_wallet_removal,
    handle_text as wallet_handle_text,
    handle_callback_query as wallet_callback,
)
from handlers.token_handler import (
    prompt_token_wallet_choice,
    prompt_token_removal,
    show_user_data,
    handle_text as token_handle_text,
    handle_callback_query as token_callback,
)
from utils.scheduler import start_scheduler

# Load environment variables
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Flask app for webhook
app = Flask(__name__)

# Telegram Bot app
bot = Bot(token=TOKEN)
application = Application.builder().token(TOKEN).build()


# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Додати гаманець", callback_data="add_wallet")],
        [InlineKeyboardButton("➖ Видалити гаманець", callback_data="remove_wallet")],
        [InlineKeyboardButton("➕ Додати токен", callback_data="add_token")],
        [InlineKeyboardButton("➖ Видалити токен", callback_data="remove_token")],
        [InlineKeyboardButton("📋 Показати дані", callback_data="show_data")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👋 Привіт! Обери дію:", reply_markup=reply_markup)


# Handle button presses
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    # Роутинг по callback'ам
    if data == "add_wallet":
        await prompt_wallet_address(update, context)
    elif data == "remove_wallet":
        await prompt_wallet_removal(update, context)
    elif data == "add_token":
        await prompt_token_wallet_choice(update, context)
    elif data == "remove_token":
        await prompt_token_removal(update, context)
    elif data == "show_data":
        await show_user_data(update, context)
    else:
        # Якщо це не основне меню, передати в хендлери
        await wallet_callback(update, context)
        await token_callback(update, context)


# Handle text messages (input values)
async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await wallet_handle_text(update, context)
    await token_handle_text(update, context)


# Webhook route
@app.route("/webhook", methods=["POST"])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        application.update_queue.put_nowait(update)
        return "ok", 200


# Main entry
if __name__ == "__main__":
    # Telegram handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    # Запускаємо scheduler (перевірки)
    start_scheduler(application.bot)

    # Запускаємо webhook сервер Flask
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        webhook_url=WEBHOOK_URL,
    )
