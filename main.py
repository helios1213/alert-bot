import os
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from wallet_handler import (
    prompt_wallet_address,
    prompt_wallet_removal,
    handle_text as wallet_handle_text,
)
from token_handler import (
    prompt_token_wallet_choice,
    prompt_token_removal,
    show_user_data,
    handle_callback_query as token_callback_handler,
    handle_text as token_handle_text,
)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

bot = Bot(token=TELEGRAM_TOKEN)
app = Flask(__name__)

application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# --- Команди
application.add_handler(CommandHandler("start", show_user_data))

# --- Callback кнопки
application.add_handler(CallbackQueryHandler(prompt_wallet_address, pattern="^add_wallet$"))
application.add_handler(CallbackQueryHandler(prompt_wallet_removal, pattern="^remove_wallet$"))
application.add_handler(CallbackQueryHandler(prompt_token_wallet_choice, pattern="^add_token$"))
application.add_handler(CallbackQueryHandler(prompt_token_removal, pattern="^remove_token$"))
application.add_handler(CallbackQueryHandler(show_user_data, pattern="^show_data$"))
application.add_handler(CallbackQueryHandler(token_callback_handler))  # для динамічних токенів/гаманців

# --- Повідомлення
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, wallet_handle_text))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, token_handle_text))

# --- Flask endpoint для Webhook
@app.route("/webhook", methods=["POST"])
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        await application.process_update(update)
    return "ok", 200

# --- Головна функція
if __name__ == "__main__":
    import asyncio

    async def run():
        await application.bot.set_webhook(url=WEBHOOK_URL)
        print(f"📡 Webhook встановлено: {WEBHOOK_URL}")
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

    asyncio.run(run())
