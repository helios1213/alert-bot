# handlers/wallet_handler.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.db import add_wallet, remove_wallet, list_wallets
import logging

# Назви полів у user_data
STATE_ADD_WALLET = "adding_wallet"
STATE_REMOVE_WALLET = "removing_wallet"
TEMP_WALLET_NAME = "wallet_to_remove"

async def prompt_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Крок 1: користувач натиснув Додати гаманець."""
    # Ставимо флаг — тепер наступне текстове повідомлення це адреса
    context.user_data[STATE_ADD_WALLET] = True
    await update.callback_query.message.reply_text("🔷 Введіть адресу гаманця (BSC):")

async def prompt_wallet_removal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Крок 1: користувач натиснув Видалити гаманець."""
    wallets = list_wallets(update.effective_user.id)
    if not wallets:
        return await update.callback_query.message.reply_text("📭 У вас немає гаманців.")
    buttons = [
        InlineKeyboardButton(w["name"], callback_data=f"remove_wallet_{w['name']}")
        for w in wallets
    ]
    # Ставимо флаг — вибір на видалення
    context.user_data[STATE_REMOVE_WALLET] = True
    await update.callback_query.message.reply_text(
        "🗑 Оберіть гаманець для видалення:", 
        reply_markup=InlineKeyboardMarkup([buttons])
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data

    # Обробка видалення після натискання кнопки конкретного гаманця
    if data.startswith("remove_wallet_") and context.user_data.pop(STATE_REMOVE_WALLET, False):
        name = data[len("remove_wallet_"):]
        remove_wallet(update.effective_user.id, name)
        await update.callback_query.message.reply_text(f"🗑 Гаманець '{name}' видалено.")
        logging.info(f"[wallet] user={update.effective_user.id} removed wallet '{name}'")
        return

    # Якщо не наше, далі будуть інші колбеки викликані в main.py
