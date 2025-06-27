import sqlite3

conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS wallets (
    chat_id INTEGER, wallet_address TEXT, wallet_name TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS tokens (
    chat_id INTEGER,
    wallet_address TEXT,
    token_contract TEXT,
    token_name TEXT,
    min_amount REAL,
    max_amount REAL,
    is_active INTEGER DEFAULT 0
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS notifications (
    chat_id INTEGER,
    tx_hash TEXT,
    wallet_address TEXT,
    token_contract TEXT,
    PRIMARY KEY (chat_id, tx_hash, wallet_address, token_contract)
)
""")

conn.commit()
user_state = {}
