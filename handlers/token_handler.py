import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

token_states = {}

async def prompt_token_wallet_choice(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    data = load_data()
    wallets = data.get(str(user_id), {}).get("wallets", [])

    if not wallets:
        await update.callback_query.message.reply_text("ℹ️ Спочатку додай гаманець.")
        return

    token_states[user_id] = {"step": "select_wallet"}
    buttons = [[InlineKeyboardButton(w["name"], callback_data=f"token_wallet_{w['name']}")] for w in wallets]
    markup = InlineKeyboardMarkup(buttons)
    await update.callback_query.message.reply_text("🔹 Вибери гаманець для токену:", reply_markup=markup)

async def handle_callback_query(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()

    data = query.data
    state = token_states.get(user_id, {})

    if data.startswith("token_wallet_") and state.get("step") == "select_wallet":
        wallet_name = data.replace("token_wallet_", "")
        state["wallet_name"] = wallet_name
        state["step"] = "awaiting_contract"
        await query.message.reply_text("🔹 Введи контракт токену:")
    elif data.startswith("remove_token_"):
        token_name = data.replace("remove_token_", "")
        data_store = load_data()
        tokens = data_store.get(str(user_id), {}).get("tokens", [])
        data_store[str(user_id)]["tokens"] = [t for t in tokens if t["name"] != token_name]
        save_data(data_store)
        await query.message.reply_text(f"🗑 Токен {token_name} видалено.")

async def handle_text(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    state = token_states.get(user_id)
    if not state:
        return

    text = update.message.text.strip()
    data_store = load_data()
    user_info = data_store.setdefault(str(user_id), {"wallets": [], "tokens": [], "seen": []})

    if state["step"] == "awaiting_contract":
        state["contract"] = text
        state["step"] = "awaiting_name"
        await update.message.reply_text("🔹 Введи назву токену:")
    elif state["step"] == "awaiting_name":
        state["token_name"] = text
        state["step"] = "awaiting_min"
        await update.message.reply_text("🔹 Введи мінімальну кількість токенів:")
    elif state["step"] == "awaiting_min":
        try:
            float(text)
            state["min"] = text
            state["step"] = "awaiting_max"
            await update.message.reply_text("🔹 Введи максимальну кількість токенів:")
        except ValueError:
            await update.message.reply_text("❌ Введи число.")
    elif state["step"] == "awaiting_max":
        try:
            float(text)
            user_info["tokens"].append({
                "wallet_name": state["wallet_name"],
                "contract": state["contract"],
                "name": state["token_name"],
                "min": state["min"],
                "max": text
            })
            save_data(data_store)
            token_states.pop(user_id)
            await update.message.reply_text("✅ Токен додано.")
        except ValueError:
            await update.message.reply_text("❌ Введи число.")

async def prompt_token_removal(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    data = load_data()
    tokens = data.get(user_id, {}).get("tokens", [])

    if not tokens:
        await update.callback_query.message.reply_text("ℹ️ Немає токенів для видалення.")
        return

    buttons = [
        [InlineKeyboardButton(f"{t['name']} [{t['wallet_name']}]", callback_data=f"remove_token_{t['name']}")]
        for t in tokens
    ]
    markup = InlineKeyboardMarkup(buttons)
    await update.callback_query.message.reply_text("🔻 Вибери токен для видалення:", reply_markup=markup)

async def show_user_data(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    data = load_data()
    info = data.get(user_id, {})
    msg = "📋 Список:\\n\\n"

for w in info.get("wallets", []):
    msg += f"🔹 {w['name']} — `{w['address']}`\\n"

for t in info.get("tokens", []):
    msg += f"🪙 {t['name']} [{t['wallet_name']}]: {t['contract']} ({t['min']} - {t['max']})\\n"

await update.callback_query.message.reply_text(msg, parse_mode="Markdown")
