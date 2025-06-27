import asyncio
import json
import os
from aiohttp import ClientSession
from telegram import Bot

DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

async def check_wallets(app):
    bot: Bot = app.bot
    api_key = os.getenv("BSCSCAN_API_KEY")
    data = load_data()

    async with ClientSession() as session:
        for user_id, user_info in data.items():
            for wallet in user_info.get("wallets", []):
                address = wallet["address"]
                for token in user_info.get("tokens", []):
                    if token["wallet_name"] != wallet["name"]:
                        continue

                    url = (
                        f"https://api.bscscan.com/api"
                        f"?module=account"
                        f"&action=tokentx"
                        f"&address={address}"
                        f"&contractaddress={token['contract']}"
                        f"&sort=desc"
                        f"&apikey={api_key}"
                    )

                    try:
                        async with session.get(url) as resp:
                            res = await resp.json()
                            if res.get("status") != "1":
                                continue

                            for tx in res["result"][:20]:
                                # ---- Додаємо фільтр тільки на вихідні транзакції ----
                                if tx["from"].lower() != address.lower():
                                    continue
                                # -------------------------------------------------------

                                quantity = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
                                if float(token["min"]) <= quantity <= float(token["max"]):
                                    tx_hash = tx["hash"]

                                    if tx_hash in user_info.get("seen", []):
                                        continue

                                    message = (
                                        f"🔔 Транзакція токену {token['name']}:\n"
                                        f"📤 Кількість: {quantity}\n"  # змінили іконку на вихід
                                        f"🔗 Хеш: {tx_hash}"
                                    )

                                    await bot.send_message(chat_id=user_id, text=message)

                                    # Зберігаємо хеш транзакції
                                    user_info.setdefault("seen", []).append(tx_hash)

                                    # Залишаємо лише останні 100
                                    if len(user_info["seen"]) > 100:
                                        user_info["seen"] = user_info["seen"][-100:]

                    except Exception as e:
                        print(f"⚠️ Помилка при запиті до API: {e}")

    save_data(data)

async def start_scheduler(app):
    while True:
        try:
            await check_wallets(app)
        except Exception as e:
            print(f"❌ Scheduler error: {e}")
        await asyncio.sleep(15)
