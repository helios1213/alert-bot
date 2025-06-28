# handlers/token_handler.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.db import add_token, remove_token, list_tokens
import logging

# Назви полів у user_data
STATE_ADD_TOKEN     = "adding_token"
STATE_REMOVE_TOKEN  = "removing_token"

async def prompt_token_wallet_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Крок 1: користувач натиснув Додати токен."""
    context.user_data[STATE_ADD_TOKEN] = True
    await update.callback_query.message.reply_text("🔷 Введіть адресу контракту токена (BSC):")

async def prompt_token_removal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Крок 1: користувач натиснув Видалити токен."""
    tokens = list_tokens(update.effective_user.id)
    if not tokens:
        return await update.callback_query.message.reply_text("📭 У вас немає токенів.")
    buttons = [
        InlineKeyboardButton(t["name"], callback_data=f"remove_token_{t['name']}")
        for t in tokens
    ]
    context.user_data[STATE_REMOVE_TOKEN] = True
    await update.callback_query.message.reply_text(
        "🗑 Оберіть токен для видалення:", 
        reply_markup=InlineKeyboardMarkup([buttons])
    )

async def show_user_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Колбек для кнопки 'list' — показати все."""
    wallets = list_tokens(update.effective_user.id)
    tokens  = list_tokens(update.effective_user.id)
    text = ["🔷 Ваші гаманці:"]
    text += [f"• {w['name']}: `{w['address']}`" for w in wallets] or ["(немає)"]
    text += ["\n🔷 Ваші токени:"]
    text += [f"• {t['name']}: `{t['contract']}`" for t in tokens] or ["(немає)"]
    await update.callback_query.message.reply_text("\n".join(text), parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text    = update.message.text.strip()

    # 1) Додавання токена (адреси контракту)
    if context.user_data.pop(STATE_ADD_TOKEN, False):
        # Для спрощення ім'я токена беремо як частину контракту
        name = text[:8]  # або будь-який інший підхід до імені
        add_token(user_id, name, text)
        await update.message.reply_text(f"✅ Токен з контрактом `{text}` додано.", parse_mode="Markdown")
        logging.info(f"[token] user={user_id} added token '{name}'")
        return

    # 2) Видалення токена після натискання конкретної кнопки
    if text.startswith("remove_token_") and context.user_data.pop(STATE_REMOVE_TOKEN, False):
        name = text[len("remove_token_"):]
        remove_token(user_id, name)
        await update.message.reply_text(f"🗑 Токен '{name}' видалено.")
        logging.info(f"[token] user={user_id} removed token '{name}'")
        return

    # 3) Якщо це звичайне повідомлення — нічого з ним не робимо
