from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from db import conn, user_state

c = conn.cursor()

def setup_handlers(app):
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

def keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Add Wallet", callback_data="add_wallet")],
        [InlineKeyboardButton("Add Token", callback_data="add_token")],
        [InlineKeyboardButton("Set Range", callback_data="set_range")],
        [InlineKeyboardButton("Show Wallets", callback_data="show_wallets")],
        [InlineKeyboardButton("Delete Wallet", callback_data="del_wallet")],
        [InlineKeyboardButton("Delete Token", callback_data="del_token")]
    ])

async def setup_handlers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome!", reply_markup=keyboard())
