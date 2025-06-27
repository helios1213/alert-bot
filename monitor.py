import os
import asyncio
from monitor_utils import check_transfers
from telegram.ext import ApplicationBuilder
from dotenv import load_dotenv
import nest_asyncio

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def periodic_check(app):
    while True:
        await check_transfers(app)
        await asyncio.sleep(15)

async def main():
    nest_asyncio.apply()
    app = ApplicationBuilder().token(TOKEN).build()
    asyncio.create_task(periodic_check(app))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
