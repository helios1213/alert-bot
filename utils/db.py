import sqlite3
import threading

DB_FILE = "data.db"
_lock = threading.Lock()

def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _lock:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            address TEXT,
            UNIQUE(user_id, name)
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            contract TEXT,
            UNIQUE(user_id, name)
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS seen_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            token_contract TEXT,
            event_id TEXT
        );
        """)
        conn.commit()
        conn.close()

def add_wallet(user_id: int, name: str, address: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
    cur.execute(
        "INSERT OR REPLACE INTO wallets(user_id, name, address) VALUES(?,?,?)",
        (user_id, name, address)
    )
    conn.commit()
    conn.close()

def remove_wallet(user_id: int, name: str):
    conn = get_conn()
    conn.execute("DELETE FROM wallets WHERE user_id=? AND name=?", (user_id, name))
    conn.commit()
    conn.close()

def list_wallets(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name, address FROM wallets WHERE user_id=?", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return [{"name": r["name"], "address": r["address"]} for r in rows]

def add_token(user_id: int, name: str, contract: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
    cur.execute(
        "INSERT OR REPLACE INTO tokens(user_id, name, contract) VALUES(?,?,?)",
        (user_id, name, contract)
    )
    conn.commit()
    conn.close()

def remove_token(user_id: int, name: str):
    conn = get_conn()
    conn.execute("DELETE FROM tokens WHERE user_id=? AND name=?", (user_id, name))
    conn.commit()
    conn.close()

def list_tokens(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name, contract FROM tokens WHERE user_id=?", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return [{"name": r["name"], "contract": r["contract"]} for r in rows]

def list_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    rows = cur.fetchall()
    conn.close()
    return [r["user_id"] for r in rows]

def get_seen_events(user_id: int, contract: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT event_id FROM seen_events WHERE user_id=? AND token_contract=?",
        (user_id, contract)
    )
    ev = [r["event_id"] for r in cur.fetchall()]
    conn.close()
    return ev

def add_seen_event(user_id: int, contract: str, event_id: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO seen_events(user_id, token_contract, event_id) VALUES(?,?,?)",
        (user_id, contract, event_id)
    )
    conn.commit()
    conn.close()
