import asyncio
import os
import sqlite3
import aiohttp
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

# Отримання API ключів з Render Environment Variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
BSCSCAN_API_KEY = os.environ.get("BSCSCAN_API_KEY")

# Підключення до бази даних
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS wallets (chat_id INTEGER, address TEXT)")
c.execute("""
    CREATE TABLE IF NOT EXISTS tokens (
        chat_id INTEGER,
        wallet TEXT,
        token_address TEXT,
        symbol TEXT,
        min REAL,
        max REAL
    )
""")
conn.commit()

# Стартова команда
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Додати гаманець", callback_data='add_wallet')]]
    await update.message.reply_text("👋 Вітаю! Вибери опцію:", reply_markup=InlineKeyboardMarkup(keyboard))

# Обробка кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "add_wallet":
        await query.edit_message_text("Введи адресу гаманця:")
        context.user_data["awaiting_wallet"] = True

# Отримання адреси гаманця
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_wallet"):
        address = update.message.text
        chat_id = update.effective_chat.id
        c.execute("INSERT INTO wallets (chat_id, address) VALUES (?, ?)", (chat_id, address))
        conn.commit()
        await update.message.reply_text(f"✅ Гаманець {address} збережено.")
        context.user_data["awaiting_wallet"] = False

# Функція перевірки транзакцій
async def check_transactions(app):
    while True:
        c.execute("SELECT DISTINCT chat_id, address FROM wallets")
        for chat_id, address in c.fetchall():
            url = f"https://api.bscscan.com/api?module=account&action=txlist&address={address}&sort=desc&apikey={BSCSCAN_API_KEY}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        data = await response.json()
                        txs = data.get("result", [])
                        if txs:
                            last_tx = txs[0]
                            if last_tx.get("from", "").lower() == address.lower():
                                to_addr = last_tx.get("to")
                                value = int(last_tx.get("value", "0")) / 1e18
                                msg = f"🚨 Вихідна транзакція:\n\n💸 *{value:.4f} BNB* до `{to_addr}`"
                                await app.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Error: {e}")
        await asyncio.sleep(30)

# Запуск бота
async def run():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    asyncio.create_task(check_transactions(app))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(run())
