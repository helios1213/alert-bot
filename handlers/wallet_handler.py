# handlers/wallet_handler.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.db import add_wallet, remove_wallet, list_wallets
import logging

# Стани FSM у context.user_data
STATE_WALLET_NAME = "wallet_name"
STATE_WALLET_ADDRESS = "wallet_address"

async def prompt_wallet_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Крок 1: користувач натиснув Додати гаманець, запитуємо назву."""
    context.user_data[STATE_WALLET_NAME] = True
    await update.callback_query.message.reply_text("🔷 Введіть назву гаманця:")

async def prompt_wallet_removal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Крок 1: користувач натиснув Видалити гаманець."""
    wallets = list_wallets(update.effective_user.id)
    if not wallets:
        return await update.callback_query.message.reply_text("📭 У вас немає гаманців.")
    buttons = [InlineKeyboardButton(w["name"], callback_data=f"remove_wallet_{{w['name']}}") for w in wallets]
    await update.callback_query.message.reply_text(
        "🗑 Оберіть гаманець для видалення:",
        reply_markup=InlineKeyboardMarkup([buttons])
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    # Видалення гаманець
    if data.startswith("remove_wallet_"):
        name = data.split("remove_wallet_", 1)[1]
        remove_wallet(update.effective_user.id, name)
        await update.callback_query.message.reply_text(f"🗑 Гаманець '{name}' видалено.")
        logging.info(f"[wallet] user={update.effective_user.id} removed wallet '{name}'")
        return
    # Інші callback обробляються в main

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # 1) Отримали назву гаманця
    if context.user_data.pop(STATE_WALLET_NAME, False):
        context.user_data['new_wallet_name'] = text
        context.user_data[STATE_WALLET_ADDRESS] = True
        await update.message.reply_text("🔷 Тепер введіть адресу гаманця (BSC):")
        return

    # 2) Отримали адресу гаманця
    if context.user_data.pop(STATE_WALLET_ADDRESS, False):
        name = context.user_data.pop('new_wallet_name')
        address = text
        add_wallet(user_id, name, address)
        await update.message.reply_text(
            f"✅ Гаманець '{name}' з адресою `{address}` додано.",
            parse_mode="Markdown"
        )
        logging.info(f"[wallet] user={user_id} added wallet '{name}:{address}'")
        return

    # Інакше — нічого

