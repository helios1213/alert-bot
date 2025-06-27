import os
import sys
import asyncio
import json
import sqlite3
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
import aiohttp

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY")
SENT_NOTIF_FILE = "sent_notifications.json"
LOCKFILE = "bot.lock"

# --- Функції блокування ---
def create_lock():
    if os.path.exists(LOCKFILE):
        print("Bot already running (lockfile exists). Exiting.")
        sys.exit(1)
    else:
        with open(LOCKFILE, "w") as f:
            f.write(str(os.getpid()))

def remove_lock():
    if os.path.exists(LOCKFILE):
        os.remove(LOCKFILE)

# --- Ініціалізація бази ---
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS wallets (chat_id INTEGER, wallet_address TEXT, wallet_name TEXT)")
c.execute("""
CREATE TABLE IF NOT EXISTS tokens (
    chat_id INTEGER,
    wallet_address TEXT,
    token_contract TEXT,
    token_name TEXT,
    min_amount REAL,
    max_amount REAL
)
""")
conn.commit()

user_state = {}

try:
    with open(SENT_NOTIF_FILE, "r") as f:
        sent_notifications = json.load(f)
except FileNotFoundError:
    sent_notifications = {}

def save_sent_notifications():
    with open(SENT_NOTIF_FILE, "w") as f:
        json.dump(sent_notifications, f)

# --- Меню ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Add Wallet", callback_data="add_wallet")],
        [InlineKeyboardButton("Add Token", callback_data="add_token")],
        [InlineKeyboardButton("Set Range", callback_data="set_range")],
        [InlineKeyboardButton("Show Wallets", callback_data="show_wallets")],
        [InlineKeyboardButton("Delete Wallet", callback_data="del_wallet")],
        [InlineKeyboardButton("Delete Token", callback_data="del_token")]
    ]
    await update.message.reply_text("Welcome! Choose an option:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- Обробка меню ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    await query.answer()

    if query.data == "add_wallet":
        user_state[chat_id] = {"action": "add_wallet", "step": "waiting_wallet_address"}
        await query.message.reply_text("Send wallet address (BSC):")
    elif query.data == "add_token":
        c.execute("SELECT wallet_address FROM wallets WHERE chat_id=?", (chat_id,))
        wallets = c.fetchall()
        if not wallets:
            await query.message.reply_text("Add at least one wallet first.")
            return
        user_state[chat_id] = {"action": "add_token", "step": "waiting_wallet_for_token"}
        await query.message.reply_text("Send wallet address from your added wallets to add token for:")
    elif query.data == "set_range":
        user_state[chat_id] = {"action": "set_range", "step": "waiting_wallet_for_range"}
        await query.message.reply_text("Send wallet address to set token range for:")
    elif query.data == "show_wallets":
        c.execute("SELECT wallet_address, wallet_name FROM wallets WHERE chat_id=?", (chat_id,))
        rows = c.fetchall()
        if not rows:
            await query.message.reply_text("No wallets added yet.")
            return
        msg = "Your wallets:\n" + "\n".join([f"{addr} — {name}" for addr, name in rows])
        await query.message.reply_text(msg)
    elif query.data == "del_wallet":
        c.execute("SELECT wallet_address, wallet_name FROM wallets WHERE chat_id=?", (chat_id,))
        rows = c.fetchall()
        if not rows:
            await query.message.reply_text("No wallets to delete.")
            return
        keyboard = [[InlineKeyboardButton(f"{name} ({addr})", callback_data=f"delw_{addr}")] for addr, name in rows]
        await query.message.reply_text("Select wallet to delete:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif query.data.startswith("delw_"):
        addr = query.data[5:]
        c.execute("DELETE FROM wallets WHERE chat_id=? AND wallet_address=?", (chat_id, addr))
        c.execute("DELETE FROM tokens WHERE chat_id=? AND wallet_address=?", (chat_id, addr))
        conn.commit()
        await query.message.reply_text(f"Deleted wallet {addr} and its tokens.")
    elif query.data == "del_token":
        c.execute("SELECT wallet_address FROM wallets WHERE chat_id=?", (chat_id,))
        wallets = [row[0] for row in c.fetchall()]
        if not wallets:
            await query.message.reply_text("Add wallets first.")
            return
        user_state[chat_id] = {"action": "del_token", "step": "waiting_wallet_for_token_del"}
        await query.message.reply_text("Send wallet address to delete token from:")
    elif query.data.startswith("deltok_"):
        parts = query.data.split("_", 2)
        if len(parts) < 3:
            await query.message.reply_text("Invalid token delete command.")
            return
        _, wallet, token_contract = parts
        c.execute("DELETE FROM tokens WHERE chat_id=? AND wallet_address=? AND token_contract=?", (chat_id, wallet, token_contract))
        conn.commit()
        await query.message.reply_text(f"Deleted token {token_contract} from wallet {wallet}.")

# --- Обробка повідомлень ---
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text.strip()
    state = user_state.get(chat_id)

    if not state:
        await update.message.reply_text("Use /start to see menu.")
        return

    action = state.get("action")
    step = state.get("step")

    if action == "add_wallet":
        if step == "waiting_wallet_address":
            if not text.startswith("0x") or len(text) != 42:
                await update.message.reply_text("Invalid wallet address format. Try again:")
                return
            state["wallet_address"] = text
            state["step"] = "waiting_wallet_name"
            await update.message.reply_text("Send wallet name:")
        elif step == "waiting_wallet_name":
            c.execute("SELECT COUNT(*) FROM wallets WHERE chat_id=?", (chat_id,))
            if c.fetchone()[0] >= 5:
                await update.message.reply_text("Max 5 wallets allowed.")
                user_state.pop(chat_id)
                return
            wallet_address = state["wallet_address"]
            wallet_name = text
            c.execute("INSERT INTO wallets VALUES (?, ?, ?)", (chat_id, wallet_address, wallet_name))
            conn.commit()
            await update.message.reply_text("Wallet added ✅")
            user_state.pop(chat_id)

    elif action == "add_token":
        if step == "waiting_wallet_for_token":
            c.execute("SELECT wallet_address FROM wallets WHERE chat_id=? AND wallet_address=?", (chat_id, text))
            if not c.fetchone():
                await update.message.reply_text("Wallet not found in your list. Send correct wallet address:")
                return
            state["wallet_address"] = text
            state["step"] = "waiting_token_contract"
            await update.message.reply_text("Send token contract address (BEP-20):")
        elif step == "waiting_token_contract":
            if not text.startswith("0x") or len(text) != 42:
                await update.message.reply_text("Invalid token contract address format. Try again:")
                return
            state["token_contract"] = text
            state["step"] = "waiting_token_name"
            await update.message.reply_text("Send token name:")
        elif step == "waiting_token_name":
            token_name = text
            wallet_address = state["wallet_address"]
            token_contract = state["token_contract"]
            c.execute(
                "INSERT INTO tokens VALUES (?, ?, ?, ?, ?, ?)",
                (chat_id, wallet_address, token_contract, token_name, 0.0, 999999999.0)
            )
            conn.commit()
            await update.message.reply_text("Token added ✅")
            user_state.pop(chat_id)

    elif action == "set_range":
        if step == "waiting_wallet_for_range":
            c.execute("SELECT wallet_address FROM wallets WHERE chat_id=? AND wallet_address=?", (chat_id, text))
            if not c.fetchone():
                await update.message.reply_text("Wallet not found. Send wallet address:")
                return
            state["wallet_address"] = text
            state["step"] = "waiting_token_for_range"
            await update.message.reply_text("Send token contract address to set range for:")
        elif step == "waiting_token_for_range":
            c.execute(
                "SELECT token_contract FROM tokens WHERE chat_id=? AND wallet_address=? AND token_contract=?",
                (chat_id, state["wallet_address"], text)
            )
            if not c.fetchone():
                await update.message.reply_text("Token not found for this wallet. Send token contract address again:")
                return
            state["token_contract"] = text
            state["step"] = "waiting_range"
            await update.message.reply_text("Send range as min;max (e.g. 0.1;100):")
        elif step == "waiting_range":
            try:
                min_s, max_s = text.split(";")
                min_val = float(min_s)
                max_val = float(max_s)
                if min_val > max_val:
                    raise ValueError()
            except:
                await update.message.reply_text("Wrong format. Send range as min;max (e.g. 0.1;100):")
                return
            c.execute(
                "UPDATE tokens SET min_amount=?, max_amount=? WHERE chat_id=? AND wallet_address=? AND token_contract=?",
                (min_val, max_val, chat_id, state["wallet_address"], state["token_contract"])
            )
            conn.commit()
            await update.message.reply_text("Range set ✅")
            user_state.pop(chat_id)

    elif action == "del_token":
        if step == "waiting_wallet_for_token_del":
            c.execute("SELECT token_contract, token_name FROM tokens WHERE chat_id=? AND wallet_address=?", (chat_id, text))
            tokens = c.fetchall()
            if not tokens:
                await update.message.reply_text("No tokens found for this wallet. Send another wallet address:")
                return
            keyboard = [
                [InlineKeyboardButton(f"{name} ({contract})", callback_data=f"deltok_{text}_{contract}")]
                for contract, name in tokens
            ]
            await update.message.reply_text("Select token to delete:", reply_markup=InlineKeyboardMarkup(keyboard))
            user_state.pop(chat_id)

    else:
        await update.message.reply_text("Use /start to see menu.")

# --- Перевірка транзакцій ---
async def check_transfers(app):
    c.execute("SELECT DISTINCT chat_id FROM wallets")
    users = [row[0] for row in c.fetchall()]
    async with aiohttp.ClientSession() as session:
        for chat_id in users:
            c.execute("SELECT wallet_address FROM wallets WHERE chat_id=?", (chat_id,))
            wallets = [row[0] for row in c.fetchall()]
            for wallet in wallets:
                c.execute("SELECT token_contract, token_name, min_amount, max_amount FROM tokens WHERE chat_id=? AND wallet_address=?", (chat_id, wallet))
                tokens = c.fetchall()
                for token_contract, token_name, min_amount, max_amount in tokens:
                    url = (
                        f"https://api.bscscan.com/api?module=account&action=tokentx"
                        f"&address={wallet}&contractaddress={token_contract}&page=1&offset=10&sort=desc"
                        f"&apikey={BSCSCAN_API_KEY}"
                    )
                    try:
                        async with session.get(url) as resp:
                            data = await resp.json()
                            if data.get("status") != "1":
                                continue
                            for tx in data.get("result", []):
                                tx_hash = tx["hash"]
                                to_addr = tx["to"].lower()
                                from_addr = tx["from"].lower()
                                amount = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
                                if not (min_amount <= amount <= max_amount):
                                    continue
                                if tx_hash not in sent_notifications:
                                    sent_notifications[tx_hash] = {}
                                key = f"{chat_id}_{wallet}_{token_contract}"
                                sent_count = sent_notifications[tx_hash].get(key, 0)
                                if sent_count >= 5:
                                    continue
                                if to_addr == wallet.lower() or from_addr == wallet.lower():
                                    direction = "IN" if to_addr == wallet.lower() else "OUT"
                                    msg = (
                                        f"🔔 {direction} {amount} {token_name}\n"
                                        f"Wallet: {wallet}\n"
                                        f"Tx: https://bscscan.com/tx/{tx_hash}"
                                    )
                                    await app.bot.send_message(chat_id, msg)
                                    sent_notifications[tx_hash][key] = sent_count + 1
                                    save_sent_notifications()
                    except Exception as e:
                        print(f"Error checking wallet {wallet}: {e}")

async def periodic_check(app):
    while True:
        await check_transfers(app)
        await asyncio.sleep(15)

async def main():
    create_lock()  # Створюємо lock файл
    import nest_asyncio
    nest_asyncio.apply()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    asyncio.create_task(periodic_check(app))
    try:
        await app.run_polling()
    finally:
        remove_lock()  # При завершенні видаляємо lock файл

if __name__ == "__main__":
    asyncio.run(main())
