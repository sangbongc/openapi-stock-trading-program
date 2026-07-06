import os
import sqlite3
from config import DB_PATH


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

#current_prices table 생성
def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS current_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_at TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            change INTEGER,
            change_rate REAL,
            open INTEGER,
            high INTEGER,
            low INTEGER,
            volume INTEGER,
            per REAL,
            pbr REAL
        )
    """)

    conn.commit()
    conn.close()

#current_prices에 현재가 저장
def save_current_price(price_data: dict):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO current_prices (
            collected_at,
            stock_code,
            name,
            price,
            change,
            change_rate,
            open,
            high,
            low,
            volume,
            per,
            pbr
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        price_data["collected_at"],
        price_data["stock_code"],
        price_data["name"],
        price_data["price"],
        price_data["change"],
        price_data["change_rate"],
        price_data["open"],
        price_data["high"],
        price_data["low"],
        price_data["volume"],
        price_data["per"],
        price_data["pbr"],
    ))

    conn.commit()
    conn.close()
def fetch_all_current_prices():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM current_prices
        ORDER BY collected_at DESC
    """)

    rows = cur.fetchall()
    conn.close()

    return [dict(row) for row in rows]
#daily_prices table 생성
def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS current_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_at TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            change INTEGER,
            change_rate REAL,
            open INTEGER,
            high INTEGER,
            low INTEGER,
            volume INTEGER,
            per REAL,
            pbr REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            date TEXT NOT NULL,
            open INTEGER NOT NULL,
            high INTEGER NOT NULL,
            low INTEGER NOT NULL,
            close INTEGER NOT NULL,
            volume INTEGER NOT NULL,
            UNIQUE(stock_code, date)
        )
    """)

    conn.commit()
    conn.close()
#종가 저장함수
def save_daily_price(daily_data: dict):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO daily_prices (
            stock_code,
            date,
            open,
            high,
            low,
            close,
            volume
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        daily_data["stock_code"],
        daily_data["date"],
        daily_data["open"],
        daily_data["high"],
        daily_data["low"],
        daily_data["close"],
        daily_data["volume"],
    ))

    conn.commit()
    conn.close()
#종가목록 조회함수
def fetch_daily_prices_by_stock(stock_code: str, limit: int = 20):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM daily_prices
        WHERE stock_code = ?
        ORDER BY date DESC
        LIMIT ?
    """, (stock_code, limit))

    rows = cur.fetchall()
    conn.close()

    return [dict(row) for row in rows]    