import os
import asyncio
import aiohttp
import json
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY")

# Пам'ять в JSON-файлі
DATA_FILE = "data.json"
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

user_state = {}

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Add Wallet", callback_data="add_wallet")],
        [InlineKeyboardButton("📄 Show Wallets", callback_data="show_wallets")],
        [InlineKeyboardButton("❌ Delete Wallet", callback_data="delete_wallet")],
        [InlineKeyboardButton("❌ Delete Token", callback_data="delete_token")]
    ]
    await update.message.reply_text("👋 Welcome! Choose an option:", reply_markup=InlineKeyboardMarkup(keyboard))

# Обробка кнопок
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = str(query.message.chat.id)
    await query.answer()

    if query.data == "add_wallet":
        user_state[chat_id] = {"step": "awaiting_wallet"}
        await query.message.reply_text("🪪 Send BSC wallet address:")
    elif query.data == "show_wallets":
        data = load_data().get(chat_id, {})
        msg = ""
        for name, val in data.get("wallets", {}).items():
            msg += f"{name}: {val['address']}\n"
            for t in val.get("tokens", {}).values():
                msg += f"    🔹 {t['symbol']} ({t['address']}) [{t['min']} - {t['max']}]\n"
        await query.message.reply_text(msg or "❌ No wallets found")
    elif query.data == "delete_wallet":
        user_state[chat_id] = {"step": "delete_wallet"}
        await query.message.reply_text("✏️ Send wallet name to delete:")
    elif query.data == "delete_token":
        user_state[chat_id] = {"step": "delete_token"}
        await query.message.reply_text("✏️ Format: WalletName;TokenSymbol")

# Ввід вручну
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    text = update.message.text.strip()
    state = user_state.get(chat_id, {})

    data = load_data()
    user_data = data.setdefault(chat_id, {"wallets": {}})

    if state.get("step") == "awaiting_wallet":
        user_state[chat_id] = {"step": "awaiting_wallet_name", "wallet": text}
        await update.message.reply_text("📝 Send a name for this wallet:")
    elif state.get("step") == "awaiting_wallet_name":
        wallet = state["wallet"]
        name = text
        user_data["wallets"][name] = {"address": wallet, "tokens": {}}
        save_data(data)
        user_state[chat_id] = {"step": "awaiting_token"}
        await update.message.reply_text("✅ Wallet added.\nNow send BEP-20 token address:")
    elif state.get("step") == "awaiting_token":
        user_state[chat_id]["token"] = text
        user_state[chat_id]["step"] = "awaiting_token_name"
        await update.message.reply_text("📝 Send token name (symbol):")
    elif state.get("step") == "awaiting_token_name":
        user_state[chat_id]["symbol"] = text
        user_state[chat_id]["step"] = "awaiting_range"
        await update.message.reply_text("🔢 Send range: min;max (e.g. 0.1;100)")
    elif state.get("step") == "awaiting_range":
        try:
            min_val, max_val = map(float, text.split(";"))
            for w_name, w in user_data["wallets"].items():
                if "tokens" not in w:
                    w["tokens"] = {}
            token_data = {
                "address": user_state[chat_id]["token"],
                "symbol": user_state[chat_id]["symbol"],
                "min": min_val,
                "max": max_val,
                "sent": 0
            }
            # Save to the last added wallet
            last_wallet = list(user_data["wallets"].keys())[-1]
            user_data["wallets"][last_wallet]["tokens"][token_data["symbol"]] = token_data
            save_data(data)
            user_state[chat_id] = {}
            await update.message.reply_text("✅ Token added!")
        except:
            await update.message.reply_text("❌ Wrong format. Use: min;max")
    elif state.get("step") == "delete_wallet":
        if text in user_data["wallets"]:
            del user_data["wallets"][text]
            save_data(data)
            await update.message.reply_text("✅ Wallet deleted")
        else:
            await update.message.reply_text("❌ Wallet not found")
    elif state.get("step") == "delete_token":
        try:
            wallet_name, symbol = text.split(";")
            if symbol in user_data["wallets"].get(wallet_name, {}).get("tokens", {}):
                del user_data["wallets"][wallet_name]["tokens"][symbol]
                save_data(data)
                await update.message.reply_text("✅ Token deleted")
            else:
                await update.message.reply_text("❌ Not found")
        except:
            await update.message.reply_text("❌ Wrong format")

# Перевірка транзакцій
async def check_loop(app):
    while True:
        data = load_data()
        async with aiohttp.ClientSession() as session:
            for chat_id, user in data.items():
                for wallet_name, wallet in user.get("wallets", {}).items():
                    address = wallet["address"].lower()
                    for token in wallet.get("tokens", {}).values():
                        url = (
                            f"https://api.bscscan.com/api?module=account&action=tokentx"
                            f"&address={address}&contractaddress={token['address']}&page=1&offset=5&sort=desc"
                            f"&apikey={BSCSCAN_API_KEY}"
                        )
                        try:
                            async with session.get(url) as resp:
                                res = await resp.json()
                                for tx in res.get("result", []):
                                    to_addr = tx["to"].lower()
                                    from_addr = tx["from"].lower()
                                    amount = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
                                    if token["min"] <= amount <= token["max"]:
                                        direction = "IN" if to_addr == address else "OUT"
                                        if token["sent"] < 10:
                                            msg = (
                                                f"🔔 {direction} {amount} {token['symbol']} "
                                                f"{'to' if direction == 'IN' else 'from'} {address}\n"
                                                f"https://bscscan.com/tx/{tx['hash']}"
                                            )
                                            await app.bot.send_message(chat_id=int(chat_id), text=msg)
                                            token["sent"] += 1
                        except Exception as e:
                            print(f"Error: {e}")
        save_data(data)
        await asyncio.sleep(15)

async def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    asyncio.create_task(check_loop(app))
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
