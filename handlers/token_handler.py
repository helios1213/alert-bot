from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import logging

from data_manager import load_data, save_data

token_states = {}

# --- TOKEN LOGIC ---
async def handle_token_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await handle_text(update, context)
    elif update.callback_query:
        await handle_callback_query(update, context)

async def prompt_token_wallet_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    wallets = data.get(user_id, {}).get("wallets", [])

    if not wallets:
        await update.callback_query.message.reply_text("ℹ️ Спочатку додай гаманець.")
        return

    token_states[user_id] = {"step": "select_wallet"}
    buttons = [
        [InlineKeyboardButton(w["name"], callback_data=f"token_wallet_{w['name']}")] for w in wallets
    ]
    markup = InlineKeyboardMarkup(buttons)
    await update.callback_query.message.reply_text("🔹 Вибери гаманець для токену:", reply_markup=markup)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(update.effective_user.id)
    await query.answer()
    data = query.data
    state = token_states.get(user_id, {})

    if data.startswith("token_wallet_") and state.get("step") == "select_wallet":
        wallet_name = data.replace("token_wallet_", "")
        token_states[user_id] = {
            "wallet_name": wallet_name,
            "step": "awaiting_contract"
        }
        await query.message.reply_text("🔹 Введи контракт токену:")

    elif data.startswith("remove_token_"):
        token_name = data.replace("remove_token_", "")
        data_store = load_data()
        user_data = data_store.get(user_id, {})
        tokens = user_data.get("tokens", [])
        updated_tokens = [t for t in tokens if t["name"] != token_name]
        data_store[user_id]["tokens"] = updated_tokens
        save_data(data_store)
        await query.message.reply_text(f"🗑 Токен `{token_name}` видалено.", parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()
    state = token_states.get(user_id)
    if not state:
        return

    data_store = load_data()
    user_info = data_store.setdefault(user_id, {"wallets": [], "tokens": [], "seen": []})

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

async def prompt_token_removal(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def show_user_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    info = data.get(user_id, {})
    msg = "📋 Список:\n\n"

    for w in info.get("wallets", []):
        msg += f"🔹 {w['name']} — `{w['address']}`\n"
    for t in info.get("tokens", []):
        msg += f"🪙 {t['name']} [{t['wallet_name']}]: `{t['contract']}` ({t['min']} - {t['max']})\n"
    await update.callback_query.message.reply_text(msg, parse_mode="Markdown")

# --- START/BASIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Вітаю! Готовий працювати з гаманцями і токенами!")

# --- MAIN APP ---
async def run_bot():
    # Читаємо токен з оточення
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set!")

    # LOGGING (опціонально)
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )

    application = ApplicationBuilder().token(TOKEN).build()

    # HANDLERS (налаштуй під себе!)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT, handle_text))

    # --- Додай свої callback-и на кнопки тут, якщо треба ---

    print("Бот запущено!")
    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_bot())
