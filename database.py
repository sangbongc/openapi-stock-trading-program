import os
import sqlite3
from config import DB_PATH


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


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
            stock_code TEXT NOT NULL,
            date TEXT NOT NULL,
            open INTEGER NOT NULL,
            high INTEGER NOT NULL,
            low INTEGER NOT NULL,
            close INTEGER NOT NULL,
            volume INTEGER NOT NULL,
            PRIMARY KEY (stock_code, date)
        )
    """)

    conn.commit()
    conn.close()


def reset_daily_prices_table():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS daily_prices")

    cur.execute("""
        CREATE TABLE daily_prices (
            stock_code TEXT NOT NULL,
            date TEXT NOT NULL,
            open INTEGER NOT NULL,
            high INTEGER NOT NULL,
            low INTEGER NOT NULL,
            close INTEGER NOT NULL,
            volume INTEGER NOT NULL,
            PRIMARY KEY (stock_code, date)
        )
    """)

    conn.commit()
    conn.close()


def save_current_price(price_data: dict):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO current_prices (
            collected_at, stock_code, name, price, change, change_rate,
            open, high, low, volume, per, pbr
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


def save_daily_prices(rows: list[dict]):
    conn = get_connection()
    cur = conn.cursor()

    cur.executemany("""
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
    """, [
        (
            row["stock_code"],
            row["date"],
            row["open"],
            row["high"],
            row["low"],
            row["close"],
            row["volume"],
        )
        for row in rows
    ])

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


def fetch_all_daily_prices():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM daily_prices
        ORDER BY stock_code, date DESC
    """)

    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]