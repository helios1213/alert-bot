import json
import os
from telegram import Update
from telegram.ext import CallbackContext

DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA, "w") as f:
        json.dump(data, f, indent=2)

user_states = {}

async def prompt_wallet_address(update: Update, context: CallbackContext):
    user_states[update.effective_user.id] = {"step": "awaiting_wallet_address"}
    await update.callback_query.message.reply_text("🔹 Введи адресу гаманця (BSC):")

async def handle_text(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in user_states:
        return

    state = user_states[user_id]
    text = update.message.text

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

async def prompt_wallet_removal(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    data = load_data()
    user_info = data.get(user_id, {})

    if not user_info.get("wallets"):
        await update.callback_query.message.reply_text("ℹ️ Немає доданих гаманців.")
        return

    buttons = []
    for w in user_info["wallets"]:
        buttons.append([{"text": w["name"], "callback_data": f"remove_wallet_{w['name']}"}])

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [[InlineKeyboardButton(b["text"], callback_data=b["callback_data"])] for b in sum(buttons, [])]
    markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text("🔻 Вибери гаманець для видалення:", reply_markup=markup)