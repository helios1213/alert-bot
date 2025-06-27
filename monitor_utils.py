import aiohttp
import os
from db import c, conn
import logging

BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_transfers(app):
    c.execute("SELECT DISTINCT chat_id FROM wallets")
    users = [row[0] for row in c.fetchall()]
    async with aiohttp.ClientSession() as session:
        for chat_id in users:
            c.execute("SELECT wallet_address FROM wallets WHERE chat_id=?", (chat_id,))
            wallets = [row[0] for row in c.fetchall()]
            for wallet in wallets:
                c.execute("""
                SELECT token_contract, token_name, min_amount, max_amount FROM tokens
                WHERE chat_id=? AND wallet_address=? AND is_active=1
                """, (chat_id, wallet))
                tokens = c.fetchall()
                for token_contract, token_name, min_amount, max_amount in tokens:
                    url = (
                        f"https://api.bscscan.com/api?module=account&action=tokentx"
                        f"&address={wallet}&contractaddress={token_contract}&page=1&offset=10&sort=desc"
                        f"&apikey={BSCSCAN_API_KEY}"
                    )
                    try:
                        async with session.get(url) as resp:
                            data = await resp.json()
                            if data.get("status") != "1":
                                continue
                            for tx in data.get("result", []):
                                tx_hash = tx["hash"]
                                to_addr = tx["to"].lower()
                                from_addr = tx["from"].lower()
                                amount = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
                                if not (min_amount <= amount <= max_amount):
                                    continue
                                c.execute("SELECT 1 FROM notifications WHERE chat_id=? AND tx_hash=? AND wallet_address=? AND token_contract=?", (chat_id, tx_hash, wallet, token_contract))
                                if c.fetchone():
                                    continue
                                direction = "IN" if to_addr == wallet.lower() else "OUT"
                                msg = (
                                    f"🔔 {direction} {amount} {token_name}\n"
                                    f"Wallet: {wallet}\n"
                                    f"Tx: https://bscscan.com/tx/{tx_hash}"
                                )
                                await app.bot.send_message(chat_id, msg)
                                c.execute("INSERT INTO notifications VALUES (?, ?, ?, ?)", (chat_id, tx_hash, wallet, token_contract))
                                conn.commit()
                    except Exception as e:
                        logger.error(f"Error checking wallet {wallet}: {e}")
