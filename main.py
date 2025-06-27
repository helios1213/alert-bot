import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from handlers import wallet_handler, token_handler
from utils.scheduler import start_scheduler
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL    = os.getenv("WEBHOOK_URL")
PORT           = int(os.environ.get("PORT", "5000"))

if not TELEGRAM_TOKEN or not WEBHOOK_URL:
    raise RuntimeError("❌ TELEGRAM_TOKEN або WEBHOOK_URL не задані в .env!")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# /start – показує головне меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Додати гаманець", callback_data="add_wallet")],
        [InlineKeyboardButton("➕ Додати токен",    callback_data="add_token")],
        [InlineKeyboardButton("🗑 Видалити гаманець", callback_data="remove_wallet")],
        [InlineKeyboardButton("🗑 Видалити токен",    callback_data="remove_token")],
        [InlineKeyboardButton("📋 Переглянути список", callback_data="list")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👋 Вітаю! Оби дію:", reply_markup=reply_markup)

# CallbackQuery – делегуємо в обидва handler-и
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    await update.callback_query.answer()
    # гаманець
    if data == "add_wallet":
        return await wallet_handler.prompt_wallet_address(update, context)
    if data == "remove_wallet":
        return await wallet_handler.prompt_wallet_removal(update, context)
    # токен
    if data == "add_token":
        return await token_handler.prompt_token_wallet_choice(update, context)
    if data == "remove_token":
        return await token_handler.prompt_token_removal(update, context)
    # список
    if data == "list":
        return await token_handler.show_user_data(update, context)
    # усі callback-и від token_handler і wallet_handler
    # (наприклад вибір якогось конкретного гаманця чи токена)
    # підключаємо їхні on_callback_query
    if data.startswith("token_wallet_") or data.startswith("remove_token_"):
        return await token_handler.handle_callback_query(update, context)
    if data.startswith("remove_wallet_"):
        return await wallet_handler.handle_callback_query(update, context)

# Звичайні текстові повідомлення – теж делегуємо
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    # якщо в процесі додавання гаманця
    await wallet_handler.handle_text(update, context)
    # якщо в процесі додавання токена
    await token_handler.handle_text(update, context)

async def on_startup(app: ApplicationBuilder):
    # ставимо вебхук
    await app.bot.set_webhook(WEBHOOK_URL)
    # запускаємо scheduler
    app.create_task(start_scheduler(app.bot))
    logging.info("🚀 Scheduler запущено та вебхук встановлено.")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Команди та хендлери
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    # після іниціалізації
    app.post_init = on_startup

    # стартуємо webhook‐сервер
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL,
    )

if __name__ == "__main__":
    main()
