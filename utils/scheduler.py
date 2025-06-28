import asyncio
from collections import defaultdict, deque
from utils.db import list_users, list_wallets, list_tokens, get_seen_events, add_seen_event

from aiohttp import ClientSession
from telegram import Bot


# Обмеження: не більше 10 повідомлень на токен за останню хвилину
_rate_limit = defaultdict(deque)  # ключ: (user_id, token_contract), значення: deque(times)

async def check_wallets(app):
    bot: Bot = app.bot
    api_key = os.getenv("BSCSCAN_API_KEY")
    users = list_users()

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
                                quantity = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
                                if not (float(token["min"]) <= quantity <= float(token["max"])):
                                    continue

                                tx_hash = tx["hash"]
                                seen = user_info.setdefault("seen", [])
                                if tx_hash in seen:
                                    continue

                                # RATE LIMITING
                                key = (user_id, token["contract"])
                                now = time.time()
                                dq = _rate_limit[key]
                                # видаляємо всі, що старші за 60 секунд
                                while dq and now - dq[0] > 60:
                                    dq.popleft()
                                # якщо вже 10 сповіщень за останню хвилину — пропускаємо
                                if len(dq) >= 10:
                                    print(f"⚠️ Rate limit reached for {key}, skipping message")
                                    continue

                                # скорочена форма хешу (останні 7 символів)
                                short_hash = tx_hash[-7:]
                                display = f"…{short_hash}"
                                # формуємо повністю клікабельний HTML-лінк
                                message = (
                                    f"🔔 Транзакція токену {token['name']}:\n"
                                    f"📥 Кількість: {quantity}\n"
                                    f'<a href="https://bscscan.com/tx/{tx_hash}">Tx hash: {display}</a>'
                                )
                                await bot.send_message(
                                    chat_id=user_id,
                                    text=message,
                                    parse_mode="HTML",
                                    disable_web_page_preview=True
                                )

                                # зберігаємо хеш та час відправки
                                seen.append(tx_hash)
                                dq.append(now)

                                # обмежуємо довжину списку seen
                                if len(seen) > 100:
                                    user_info["seen"] = seen[-100:]

                    except Exception as e:
                        print(f"⚠️ Помилка при запиті до API: {e}")

async def start_scheduler(app):
    while True:
        try:
            await check_wallets(app)
        except Exception as e:
            print(f"❌ Scheduler error: {e}")
        await asyncio.sleep(15)
