import asyncio
import logging
import os
from telegram.ext import ApplicationBuilder, CommandHandler
from handlers import setup_handlers
from monitor import periodic_check
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
IS_PRIMARY = os.getenv("IS_PRIMARY", "1") == "1"

async def main():
    if not IS_PRIMARY:
        logger.info("Secondary instance detected. Exiting...")
        return

    from telegram.error import Conflict
    import nest_asyncio
    nest_asyncio.apply()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", setup_handlers))
    setup_handlers(app)

    asyncio.create_task(periodic_check(app))
    try:
        await app.run_polling()
    except Conflict:
        logger.error("Another bot instance is already running.")

if __name__ == "__main__":
    asyncio.run(main())
