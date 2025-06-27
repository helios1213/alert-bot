from telegram.ext import ApplicationBuilder, CommandHandler
from handlers import start, callback_handler, message_handler
from telegram.ext import CallbackQueryHandler, MessageHandler, filters
import os
import nest_asyncio
import asyncio
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def main():
    nest_asyncio.apply()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
