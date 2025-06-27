from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from db import conn, c, user_state

# --- Callback handler ---
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

# --- Message handler ---
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
                "INSERT INTO tokens VALUES (?, ?, ?, ?, ?, ?, 1)",
                (chat_id, wallet_address, token_contract, token_name, 0.0, 999999999.0,)
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
                "UPDATE tokens SET min_amount=?, max_amount=?, is_active=1 WHERE chat_id=? AND wallet_address=? AND token_contract=?",
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
        await update.message.reply_text("Use /menu to see menu.")
