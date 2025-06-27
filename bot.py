import os
import asyncio
import json
import aiohttp
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY")

# Файл для збереження відправлених сповіщень
SENT_NOTIFICATIONS_FILE = "sent_notifications.json"

# Зчитуємо/ініціалізуємо збережені повідомлення
try:
    with open(SENT_NOTIFICATIONS_FILE, "r") as f:
        sent_notifications = json.load(f)
except FileNotFoundError:
    sent_notifications = {}

user_state = {}
wallets = {}  # {chat_id: {wallet_address: wallet_name}}
tokens = {}  # {chat_id: {wallet_address: {token_address: {"symbol": ..., "min":..., "max":...}}}}


def save_sent_notifications():
    with open(SENT_NOTIFICATIONS_FILE, "w") as f:
        json.dump(sent_notifications, f)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    if chat_id not in wallets:
        wallets[chat_id] = {}
    if chat_id not in tokens:
        tokens[chat_id] = {}

    keyboard = [
        [InlineKeyboardButton("Add Wallet", callback_data="add_wallet")],
        [InlineKeyboardButton("Add Token", callback_data="add_token")],
        [InlineKeyboardButton("Set Range", callback_data="set_range")],
        [InlineKeyboardButton("Show Wallets", callback_data="show_wallets")],
        [InlineKeyboardButton("Delete Wallet", callback_data="del_wallet")],
        [InlineKeyboardButton("Delete Token", callback_data="del_token")],
    ]
    await update.message.reply_text(
        "Welcome! Choose option:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id

    if query.data == "add_wallet":
        user_state[chat_id] = {"action": "add_wallet_step1"}
        await query.message.reply_text("Send wallet address (BSC):")
    elif query.data == "add_token":
        if not wallets.get(chat_id):
            await query.message.reply_text("Add at least one wallet first!")
            return
        user_state[chat_id] = {"action": "add_token_step1"}
        await query.message.reply_text("Send wallet address for token:")
    elif query.data == "set_range":
        user_state[chat_id] = {"action": "set_range"}
        await query.message.reply_text("Send in format:\nWalletAddress;TokenSymbol;MinAmount;MaxAmount")
    elif query.data == "show_wallets":
        msg = ""
        if chat_id in wallets and wallets[chat_id]:
            for w_addr, w_name in wallets[chat_id].items():
                msg += f"{w_name} — {w_addr}\n"
        else:
            msg = "No wallets added."
        await query.message.reply_text(msg)
    elif query.data == "del_wallet":
        if not wallets.get(chat_id):
            await query.message.reply_text("No wallets to delete.")
            return
        user_state[chat_id] = {"action": "del_wallet"}
        wallet_list = [f"{name} — {addr}" for addr, name in wallets[chat_id].items()]
        await query.message.reply_text(
            "Send exact wallet address to delete:\n" + "\n".join(wallet_list)
        )
    elif query.data == "del_token":
        if not tokens.get(chat_id):
            await query.message.reply_text("No tokens to delete.")
            return
        user_state[chat_id] = {"action": "del_token_step1"}
        # list wallets with tokens
        wallet_list = [f"{w}" for w in tokens[chat_id].keys()]
        await query.message.reply_text(
            "Send wallet address to delete token from:\n" + "\n".join(wallet_list)
        )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    text = update.message.text.strip()
    state = user_state.get(chat_id, {})
    action = state.get("action")

    if action == "add_wallet_step1":
        # Save wallet address, ask for wallet name
        wallet_addr = text.lower()
        if chat_id not in wallets:
            wallets[chat_id] = {}
        if len(wallets[chat_id]) >= 5:
            await update.message.reply_text("Max 5 wallets allowed.")
            user_state.pop(chat_id, None)
            return
        state["wallet_addr"] = wallet_addr
        user_state[chat_id] = {"action": "add_wallet_step2", "wallet_addr": wallet_addr}
        await update.message.reply_text("Send a name for this wallet:")
    elif action == "add_wallet_step2":
        wallet_addr = state.get("wallet_addr")
        wallet_name = text
        wallets.setdefault(chat_id, {})[wallet_addr] = wallet_name
        # Also clear tokens for this wallet if new
        tokens.setdefault(chat_id, {}).setdefault(wallet_addr, {})
        await update.message.reply_text(f"Wallet '{wallet_name}' added ✅")
        user_state.pop(chat_id, None)

    elif action == "add_token_step1":
        wallet_addr = text.lower()
        if chat_id not in wallets or wallet_addr not in wallets[chat_id]:
            await update.message.reply_text("Wallet not found, try again.")
            return
        user_state[chat_id] = {"action": "add_token_step2", "wallet_addr": wallet_addr}
        await update.message.reply_text("Send token contract address:")
    elif action == "add_token_step2":
        token_addr = text.lower()
        if chat_id not in user_state or "wallet_addr" not in user_state[chat_id]:
            await update.message.reply_text("Unexpected error, try /start")
            user_state.pop(chat_id, None)
            return
        wallet_addr = user_state[chat_id]["wallet_addr"]
        user_state[chat_id] = {"action": "add_token_step3", "wallet_addr": wallet_addr, "token_addr": token_addr}
        await update.message.reply_text("Send token symbol:")
    elif action == "add_token_step3":
        token_symbol = text.upper()
        wallet_addr = state.get("wallet_addr")
        token_addr = state.get("token_addr")
        if chat_id not in tokens:
            tokens[chat_id] = {}
        if wallet_addr not in tokens[chat_id]:
            tokens[chat_id][wallet_addr] = {}
        tokens[chat_id][wallet_addr][token_addr] = {"symbol": token_symbol, "min": 0, "max": 999999999}
        await update.message.reply_text(f"Token '{token_symbol}' added to wallet ✅")
        user_state.pop(chat_id, None)

    elif action == "set_range":
        try:
            wallet_addr, token_symbol, min_val, max_val = [x.strip() for x in text.split(";")]
            token_symbol = token_symbol.upper()
            min_val = float(min_val)
            max_val = float(max_val)
        except:
            await update.message.reply_text("Wrong format. Use WalletAddress;TokenSymbol;Min;Max")
            return

        if chat_id not in tokens or wallet_addr not in tokens[chat_id] or not any(
            t["symbol"] == token_symbol for t in tokens[chat_id][wallet_addr].values()
        ):
            await update.message.reply_text("Wallet or token not found.")
            return

        # Find token address by symbol
        token_addr_to_update = None
        for t_addr, t_data in tokens[chat_id][wallet_addr].items():
            if t_data["symbol"] == token_symbol:
                token_addr_to_update = t_addr
                break

        if token_addr_to_update:
            tokens[chat_id][wallet_addr][token_addr_to_update]["min"] = min_val
            tokens[chat_id][wallet_addr][token_addr_to_update]["max"] = max_val
            await update.message.reply_text(f"Range for {token_symbol} set to {min_val} - {max_val} ✅")
        else:
            await update.message.reply_text("Token not found.")
        user_state.pop(chat_id, None)

    elif action == "del_wallet":
        wallet_addr = text.lower()
        if chat_id in wallets and wallet_addr in wallets[chat_id]:
            wallets[chat_id].pop(wallet_addr)
            tokens[chat_id].pop(wallet_addr, None)
            await update.message.reply_text(f"Wallet {wallet_addr} deleted ✅")
        else:
            await update.message.reply_text("Wallet not found.")
        user_state.pop(chat_id, None)

    elif action == "del_token_step1":
        wallet_addr = text.lower()
        if chat_id not in tokens or wallet_addr not in tokens[chat_id]:
            await update.message.reply_text("Wallet not found or no tokens here.")
            user_state.pop(chat_id, None)
            return
        user_state[chat_id] = {"action": "del_token_step2", "wallet_addr": wallet_addr}
        token_list = [f"{data['symbol']} — {t_addr}" for t_addr, data in tokens[chat_id][wallet_addr].items()]
        await update.message.reply_text("Send token contract address to delete:\n" + "\n".join(token_list))

    elif action == "del_token_step2":
        token_addr = text.lower()
        wallet_addr = state.get("wallet_addr")
        if chat_id in tokens and wallet_addr in tokens[chat_id] and token_addr in tokens[chat_id][wallet_addr]:
            symbol = tokens[chat_id][wallet_addr][token_addr]["symbol"]
            tokens[chat_id][wallet_addr].pop(token_addr)
            await update.message.reply_text(f"Token {symbol} deleted from wallet ✅")
        else:
            await update.message.reply_text("Token not found.")
        user_state.pop(chat_id, None)

    else:
        await update.message.reply_text("Use /start to begin.")

async def check_transfers(app):
    async with aiohttp.ClientSession() as session:
        for chat_id in wallets:
            for wallet_addr in wallets[chat_id]:
                if chat_id not in tokens or wallet_addr not in tokens[chat_id]:
                    continue
                for token_addr, t_data in tokens[chat_id][wallet_addr].items():
                    symbol = t_data["symbol"]
                    min_val = t_data["min"]
                    max_val = t_data["max"]

                    url = (
                        f"https://api.bscscan.com/api?module=account&action=tokentx"
                        f"&address={wallet_addr}&contractaddress={token_addr}&page=1&offset=10&sort=desc"
                        f"&apikey={BSCSCAN_API_KEY}"
                    )

                    try:
                        async with session.get(url) as resp:
                            data = await resp.json()
                            txs = data.get("result", [])
                            count_sent = 0
                            for tx in txs:
                                tx_hash = tx["hash"]
                                if sent_notifications.get(chat_id, {}).get(wallet_addr, {}).get(token_addr) is None:
                                    sent_notifications.setdefault(chat_id, {}).setdefault(wallet_addr, {})[token_addr] = []
                                if tx_hash in sent_notifications[chat_id][wallet_addr][token_addr]:
                                    continue  # already sent

                                to_addr = tx["to"].lower()
                                from_addr = tx["from"].lower()
                                amount = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))

                                if min_val <= amount <= max_val and (to_addr == wallet_addr or from_addr == wallet_addr):
                                    direction = "IN" if to_addr == wallet_addr else "OUT"
                                    msg = (
                                        f"🔁 {direction} {amount} {symbol} "
                                        f"{'to' if direction == 'IN' else 'from'} {wallet_addr}\n"
                                        f"https://bscscan.com/tx/{tx_hash}"
                                    )
                                    await app.bot.send_message(chat_id, msg)
                                    sent_notifications[chat_id][wallet_addr][token_addr].append(tx_hash)
                                    count_sent += 1
                                    if count_sent >= 5:
                                        break
                            # Keep only last 5 hashes to limit storage and notifications
                            if len(sent_notifications[chat_id][wallet_addr][token_addr]) > 5:
                                sent_notifications[chat_id][wallet_addr][token_addr] = sent_notifications[chat_id][wallet_addr][token_addr][-5:]
                    except Exception as e:
                        print(f"Error checking wallet {wallet_addr} token {token_addr}: {e}")

    save_sent_notifications()


async def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    async def periodic():
        while True:
            await check_transfers(app)
            await asyncio.sleep(15)

    asyncio.create_task(periodic())

    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
