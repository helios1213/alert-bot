import asyncio
import os
import time
from collections import defaultdict, deque

from aiohttp import ClientSession
from telegram import Bot

# 🔄 Імпортуємо централізовані функції, що пишуть у /data/data.json на Render Persistent Disk
from data_manager import load_data, save_data

# Обмеження: не більше 10 повідомлень на токен за останню хвилину
_rate_limit = defaultdict(deque)  # ключ: (user_id, token_contract), значення: deque(times)

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

                            # Охоплення останніх 50 транзакцій
                            for tx in res["result"][:50]:
                                if tx["from"].lower() != address.lower():
                                    continue

                                quantity = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
                                if not (float(token["min"]) <= quantity <= float(token["max"])):
                                    continue

                                tx_hash = tx["hash"]
                                seen = user_info.setdefault("seen", [])
                                if tx_hash in seen:
                                    continue

                                key = (user_id, token["contract"])
                                now = time.time()
                                dq = _rate_limit[key]
                                while dq and now - dq[0] > 60:
                                    dq.popleft()
                                if len(dq) >= 10:
                                    print(f"⚠️ Rate limit reached for {key}, skipping message")
                                    continue

                                short_hash = tx_hash[-7:]
                                display = f"…{short_hash}"
                                message = (
                                    f"🔔 Транзакція токену {token['name']}:\n"
                                    f"📥 Кількість: {quantity}\n"
                                    f'<a href="https://bscscan.com/tx/{tx_hash}">Tx hash: {display}</a>'
                                )
                                await bot.send_message(
                                    chat_id=-1002506895973,  # 🔄 канал, куди пишемо
                                    text=message,
                                    parse_mode="HTML",
                                    disable_web_page_preview=True
                                )

                                seen.append(tx_hash)
                                dq.append(now)

                                if len(seen) > 1000:
                                    user_info["seen"] = seen[-1000:]

                    except Exception as e:
                        print(f"⚠️ Помилка при запиті до API: {e}")

    save_data(data)


async def start_scheduler(app):
    while True:
        try:
            await check_wallets(app)
        except Exception as e:
            print(f"❌ Scheduler error: {e}")
        await asyncio.sleep(5)
