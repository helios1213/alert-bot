import os
import asyncio
import json
import nest_asyncio
from dotenv import load_dotenv
from flask import Flask, request
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from wallet_handler import handle_text as wallet_text, prompt_wallet_address, prompt_wallet_removal
from token_handler import (
    handle_text as token_text,
    handle_callback_query,
    prompt_token_wallet_choice,
    prompt_token_removal,
    show_user_data
)
from scheduler import start_scheduler

# --- INIT ---
load_dotenv()
nest_asyncio.apply()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DATA_FILE = "data.json"

# --- Ensure data.json exists ---
def ensure_data_file():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f, indent=2)
        print("📁 Файл data.json створено.")
    else:
        print("📁 Файл data.json існує.")

ensure_data_file()

# --- Flask ---
app = Flask(__name__)
bot_app = ApplicationBuilder().token(TOKEN).build()

# --- Telegram Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"✅ /start received from user_id={update.effective_user.id}")

    keyboard = [
        [InlineKeyboardButton("➕ Додати гаманець", callback_data='add_wallet')],
        [InlineKeyboardButton("➕ Додати токен", callback_data='add_token')],
        [InlineKeyboardButton("🗑 Видалити гаманець", callback_data='remove_wallet')],
        [InlineKeyboardButton("🗑 Видалити токен", callback_data='remove_token')],
        [InlineKeyboardButton("📋 Список", callback_data='list')]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text("👋 Вітаю! Обери дію:", reply_markup=markup)
    elif update.effective_chat:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="👋 Вітаю! Обери дію:", reply_markup=markup)
    else:
        print("⚠️ Немає доступного чату для відповіді.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"🔘 Callback data: {update.callback_query.data}")
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == 'add_wallet':
        await prompt_wallet_address(update, context)
    elif data == 'add_token':
        await prompt_token_wallet_choice(update, context)
    elif data == 'remove_wallet':
        await prompt_wallet_removal(update, context)
    elif data == 'remove_token':
        await prompt_token_removal(update, context)
    elif data == 'list':
        await show_user_data(update, context)
    else:
        await handle_callback_query(update, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"✉️ Text from user {update.effective_user.id}: {update.message.text}")
    await wallet_text(update, context)
    await token_text(update, context)

# --- Register Handlers ---
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CallbackQueryHandler(handle_callback))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

# --- Webhook Route ---
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot_app.bot)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(bot_app.process_update(update))
        print("📨 Webhook update processed.")
    except Exception as e:
        print(f"❌ Error in webhook: {e}")
    return "ok", 200

# --- Init Webhook + Scheduler ---
async def setup_webhook_and_scheduler():
    print(f"🌐 Установка вебхуку на {WEBHOOK_URL}")
    bot = Bot(token=TOKEN)
    await bot.set_webhook(url=WEBHOOK_URL)
    asyncio.create_task(start_scheduler(bot_app))

async def main():
    await setup_webhook_and_scheduler()
    print("🚀 Бот запущено. Очікування запитів...")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    asyncio.run(main())
