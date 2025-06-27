# bot.py — Telegram-бот для моніторингу вихідних транзакцій з гаманців (BSC)
import asyncio
import sqlite3
import aiohttp
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

TELEGRAM_BOT_TOKEN = "7677758563:AAFJDHUOkC0qLO-rBcp4ekCuqIujtpDvL_Y"
BSCSCAN_API_KEY = "HXG8TV93WD1UYC9YAFZKGA8QU7Q78ZDS1J"

# База даних SQLite
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS wallets (chat_id INTEGER, address TEXT)")
c.execute("""CREATE TABLE IF NOT EXISTS tokens (
    chat_id INTEGER,
    wallet TEXT,
    token_address TEXT,
    symbol TEXT,
    min REAL,
    max REAL
)""")
conn.commit()

user_state = {}

# /start команда
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Add Wallet", callback_data="add_wallet")],
        [InlineKeyboardButton("Add Token", callback_data="add_token")],
        [InlineKeyboardButton("Set Range", callback_data="set_range")],
        [InlineKeyboardButton("Delete Token", callback_data="delete_token")],
        [InlineKeyboardButton("Show Wallets", callback_data="show_wallets")]
    ]
    await update.message.reply_text("Welcome! Choose:", reply_markup=InlineKeyboardMarkup(keyboard))

# Обробка кнопок
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id

    if query.data == "add_wallet":
        user_state[chat_id] = {"action": "add_wallet"}
        await query.message.reply_text("Send wallet address:")
    elif query.data == "add_token":
        user_state[chat_id] = {"action": "add_token"}
        await query.message.reply_text("Format: Wallet;TokenAddress;Symbol")
    elif query.data == "set_range":
        user_state[chat_id] = {"action": "set_range"}
        await query.message.reply_text("Format: Wallet;Symbol;Min;Max")
    elif query.data == "delete_token":
        user_state[chat_id] = {"action": "delete_token"}
        await query.message.reply_text("Format: Wallet;Symbol")
    elif query.data == "show_wallets":
        c.execute("SELECT DISTINCT address FROM wallets WHERE chat_id=?", (chat_id,))
        wallets = [row[0] for row in c.fetchall()]
        msg = "\n".join(wallets) if wallets else "No wallets"
        await query.message.reply_text(msg)

# Обробка введення вручну
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text
    action = user_state.get(chat_id, {}).get("action")

    if action == "add_wallet":
        c.execute("SELECT COUNT(*) FROM wallets WHERE chat_id=?", (chat_id,))
        if c.fetchone()[0] >= 5:
            await update.message.reply_text("Max 5 wallets")
            return
        c.execute("INSERT INTO wallets VALUES (?, ?)", (chat_id, text.strip()))
        conn.commit()
        await update.message.reply_text("Wallet added ✅")

    elif action == "add_token":
        try:
            wallet, contract, symbol = [x.strip() for x in text.split(";")]
            c.execute("INSERT INTO tokens VALUES (?, ?, ?, ?, ?, ?)", (chat_id, wallet, contract, symbol, 0, 999999))
            conn.commit()
            await update.message.reply_text("Token added ✅")
        except:
            await update.message.reply_text("Wrong format")

    elif action == "set_range":
        try:
            wallet, symbol, min_val, max_val = text.split(";")
            c.execute("UPDATE tokens SET min=?, max=? WHERE chat_id=? AND wallet=? AND symbol=?",
                      (float(min_val), float(max_val), chat_id, wallet.strip(), symbol.strip()))
            conn.commit()
            await update.message.reply_text("Range set ✅")
        except:
            await update.message.reply_text("Wrong format")

    elif action == "delete_token":
        try:
            wallet, symbol = [x.strip() for x in text.split(";")]
            c.execute("DELETE FROM tokens WHERE chat_id=? AND wallet=? AND symbol=?",
                      (chat_id, wallet, symbol))
            conn.commit()
            await update.message.reply_text("Token deleted ✅")
        except:
            await update.message.reply_text("Wrong format")

    user_state[chat_id] = {}

# Перевірка транзакцій через BscScan (вихідні)
async def check_transfers(app):
    c.execute("SELECT DISTINCT chat_id FROM wallets")
    users = [row[0] for row in c.fetchall()]
    async with aiohttp.ClientSession() as session:
        for chat_id in users:
            c.execute("SELECT address FROM wallets WHERE chat_id=?", (chat_id,))
            wallets = [row[0] for row in c.fetchall()]
            for wallet in wallets:
                c.execute("SELECT * FROM tokens WHERE chat_id=? AND wallet=?", (chat_id, wallet))
                tokens = c.fetchall()
                for _, _, _, token_addr, symbol, min_val, max_val in tokens:
                    url = f"https://api.bscscan.com/api?module=account&action=tokentx&address={wallet}&contractaddress={token_addr}&page=1&offset=5&sort=desc&apikey={BSCSCAN_API_KEY}"
                    try:
                        async with session.get(url) as resp:
                            data = await resp.json()
                            for tx in data.get("result", []):
                                if tx["from"].lower() == wallet.lower():
                                    amount = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
                                    if min_val <= amount <= max_val:
                                        msg = f"📤 {amount} {symbol} from {wallet}\nhttps://bscscan.com/tx/{tx['hash']}"
                                        await app.bot.send_message(chat_id, msg)
                    except Exception as e:
                        print(f"Error for {wallet}: {e}")

# Головна функція
async def run():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    async def periodic():
        while True:
            await check_transfers(app)
            await asyncio.sleep(60)

    asyncio.create_task(periodic())
    await app.run_polling()

# Запуск
if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(run())
        else:
            loop.run_until_complete(run())
    except RuntimeError:
        asyncio.run(run())

