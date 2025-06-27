import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from dotenv import load_dotenv
from wallet_handler import (
    handle_text as wallet_text,
    prompt_wallet_address,
    prompt_wallet_removal
)
from token_handler import (
    handle_text as token_text,
    prompt_token_wallet_choice,
    prompt_token_removal,
    show_user_data,
    handle_callback_query as token_callback
)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = "data.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)
    print("📁 Створено data.json")

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Додати гаманець", callback_data="add_wallet")],
        [InlineKeyboardButton("🗑 Видалити гаманець", callback_data="remove_wallet")],
        [InlineKeyboardButton("📥 Додати токен", callback_data="add_token")],
        [InlineKeyboardButton("🗑 Видалити токен", callback_data="remove_token")],
        [InlineKeyboardButton("📋 Список", callback_data="view_data")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Привіт! Обери дію 👇", reply_markup=reply_markup)

# --- Головний callback handler ---
async def main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data == "add_wallet":
        await prompt_wallet_address(update, context)
    elif data == "remove_wallet":
        await prompt_wallet_removal(update, context)
    elif data == "add_token":
        await prompt_token_wallet_choice(update, context)
    elif data == "remove_token":
        await prompt_token_removal(update, context)
    elif data == "view_data":
        await show_user_data(update, context)
    else:
        # якщо callback від wallet_handler/token_handler
        await token_callback(update, context)

# --- Запуск ---
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(main_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, wallet_text))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, token_text))

    print("🚀 Бот запущено!")
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=os.environ.get("WEBHOOK_URL")
    )

if __name__ == "__main__":
    main()
