import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

DATA_FILE = "data.json"
user_states = {}

# --- Завантаження/збереження даних ---
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f)
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# --- Додати гаманець ---
async def prompt_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = {"step": "awaiting_wallet_address"}
    print(f"[wallet] user={user_id} — prompting wallet address")
    await update.callback_query.message.reply_text("🔹 Введи адресу гаманця (BSC):")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_states:
        print(f"[wallet] user={user_id} — no state, skipping")
        return

    state = user_states[user_id]
    text = update.message.text.strip()
    print(f"[wallet] user={user_id}, step={state['step']}, input={text}")

    data = load_data()
    user_info = data.setdefault(str(user_id), {"wallets": [], "tokens": [], "seen": []})

    if state["step"] == "awaiting_wallet_address":
        if len(user_info["wallets"]) >= 5:
            await update.message.reply_text("❌ Можна додати не більше 5 гаманців.")
            return
        state["address"] = text
        state["step"] = "awaiting_wallet_name"
        await update.message.reply_text("🔹 Введи назву для цього гаманця:")

    elif state["step"] == "awaiting_wallet_name":
        user_info["wallets"].append({
            "name": text,
            "address": state["address"]
        })
        save_data(data)
        user_states.pop(user_id)
        await update.message.reply_text("✅ Гаманець додано.")
        print(f"[wallet] user={user_id} — wallet added")

# --- Видалити гаманець ---
async def prompt_wallet_removal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    wallets = data.get(user_id, {}).get("wallets", [])

    if not wallets:
        await update.callback_query.message.reply_text("ℹ️ Немає доданих гаманців.")
        return

    buttons = [
        [InlineKeyboardButton(w["name"], callback_data=f"remove_wallet_{w['name']}")]
        for w in wallets
    ]
    markup = InlineKeyboardMarkup(buttons)
    await update.callback_query.message.reply_text("🔻 Вибери гаманець для видалення:", reply_markup=markup)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(update.effective_user.id)
    await query.answer()

    data = query.data
    if data.startswith("remove_wallet_"):
        wallet_name = data.replace("remove_wallet_", "")
        data_store = load_data()
        wallets = data_store.get(user_id, {}).get("wallets", [])

        data_store[user_id]["wallets"] = [w for w in wallets if w["name"] != wallet_name]
        save_data(data_store)

        await query.message.reply_text(f"🗑 Гаманець {wallet_name} видалено.")
        print(f"[wallet] user={user_id} — wallet '{wallet_name}' removed")

# --- Обгортка для обробки гаманця ---
async def handle_wallet_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await prompt_wallet_address(update, context)
    elif update.message:
        await handle_text(update, context)
