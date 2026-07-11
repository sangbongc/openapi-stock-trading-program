import logging
import os
import sqlite3
from typing import Any

from config import DB_PATH


logger = logging.getLogger(__name__)


# 현재가 저장 SQL
INSERT_CURRENT_PRICE_SQL = """
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
"""


# 일봉 저장 SQL
INSERT_DAILY_PRICE_SQL = """
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
"""


def get_connection() -> sqlite3.Connection:
    """
    SQLite 데이터베이스 연결 객체를 생성하여 반환한다.

    DB 파일이 저장될 디렉터리가 존재하지 않으면 자동으로 생성한다.
    조회 결과를 컬럼명으로 접근할 수 있도록 row_factory를 설정한다.

    Returns
    -------
    sqlite3.Connection
        SQLite 데이터베이스 연결 객체
    """
    db_directory = os.path.dirname(DB_PATH)

    if db_directory:
        os.makedirs(db_directory, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    return conn


def create_tables() -> None:
    """
    자동매매 프로그램에서 사용하는 테이블과 인덱스를 생성한다.

    생성 테이블
    -----------
    current_prices
        종목의 현재가 수집 내역을 저장한다.

    daily_prices
        종목별 일봉 데이터를 저장한다.
    """
    try:
        with get_connection() as conn:
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

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_current_prices_stock_time
                ON current_prices (stock_code, collected_at DESC)
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_prices_date
                ON daily_prices (date DESC)
            """)

        logger.info("데이터베이스 테이블 생성 완료")

    except sqlite3.Error:
        logger.exception("데이터베이스 테이블 생성 중 오류 발생")
        raise


def reset_daily_prices_table() -> None:
    """
    daily_prices 테이블을 삭제한 뒤 다시 생성한다.

    데이터베이스 구조를 변경하거나 일봉 데이터를 완전히
    초기화할 때 사용한다.

    주의
    ----
    기존 daily_prices 데이터는 모두 삭제된다.
    """
    try:
        with get_connection() as conn:
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

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_prices_date
                ON daily_prices (date DESC)
            """)

        logger.info("daily_prices 테이블 초기화 완료")

    except sqlite3.Error:
        logger.exception("daily_prices 테이블 초기화 중 오류 발생")
        raise


def save_current_price(price_data: dict[str, Any]) -> int:
    """
    현재가 데이터를 current_prices 테이블에 저장한다.

    Parameters
    ----------
    price_data : dict[str, Any]
        parser.py에서 가공된 현재가 데이터

    Returns
    -------
    int
        새로 저장된 행의 ID
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute(
                INSERT_CURRENT_PRICE_SQL,
                (
                    price_data["collected_at"],
                    price_data["stock_code"],
                    price_data["name"],
                    price_data["price"],
                    price_data.get("change"),
                    price_data.get("change_rate"),
                    price_data.get("open"),
                    price_data.get("high"),
                    price_data.get("low"),
                    price_data.get("volume"),
                    price_data.get("per"),
                    price_data.get("pbr"),
                ),
            )

            inserted_id = cur.lastrowid

        logger.info(
            "현재가 저장 완료: stock_code=%s, price=%s",
            price_data["stock_code"],
            price_data["price"],
        )

        if inserted_id is None:
            raise RuntimeError("현재가 저장 후 행 ID를 확인할 수 없습니다.")

        return inserted_id

    except KeyError as error:
        logger.exception(
            "현재가 데이터에 필수 키가 없습니다: %s",
            error,
        )
        raise

    except sqlite3.Error:
        logger.exception(
            "현재가 저장 중 데이터베이스 오류 발생: stock_code=%s",
            price_data.get("stock_code"),
        )
        raise


def save_daily_prices(rows: list[dict[str, Any]]) -> int:
    """
    여러 건의 일봉 데이터를 daily_prices 테이블에 일괄 저장한다.

    동일한 stock_code와 date 조합이 이미 존재하면
    기존 데이터를 새로운 데이터로 교체한다.

    Parameters
    ----------
    rows : list[dict[str, Any]]
        저장할 일봉 데이터 목록

    Returns
    -------
    int
        저장을 시도한 일봉 데이터 개수
    """
    if not rows:
        logger.info("저장할 일봉 데이터가 없습니다.")
        return 0

    values = [
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
    ]

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.executemany(INSERT_DAILY_PRICE_SQL, values)

        logger.info("일봉 데이터 %d건 저장 완료", len(rows))
        return len(rows)

    except KeyError as error:
        logger.exception(
            "일봉 데이터에 필수 키가 없습니다: %s",
            error,
        )
        raise

    except sqlite3.Error:
        logger.exception("일봉 데이터 저장 중 데이터베이스 오류 발생")
        raise


def fetch_all_current_prices() -> list[dict[str, Any]]:
    """
    current_prices 테이블의 모든 현재가 데이터를 조회한다.

    Returns
    -------
    list[dict[str, Any]]
        수집 시각을 기준으로 내림차순 정렬된 현재가 데이터
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT *
                FROM current_prices
                ORDER BY collected_at DESC
            """)

            rows = cur.fetchall()

        return [dict(row) for row in rows]

    except sqlite3.Error:
        logger.exception("전체 현재가 조회 중 데이터베이스 오류 발생")
        raise


def fetch_latest_current_price(
    stock_code: str,
) -> dict[str, Any] | None:
    """
    특정 종목의 가장 최근 현재가 데이터를 조회한다.

    Parameters
    ----------
    stock_code : str
        종목 코드

    Returns
    -------
    dict[str, Any] | None
        가장 최근 현재가 데이터.
        저장된 데이터가 없으면 None을 반환한다.
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT *
                FROM current_prices
                WHERE stock_code = ?
                ORDER BY collected_at DESC
                LIMIT 1
            """, (stock_code,))

            row = cur.fetchone()

        return dict(row) if row else None

    except sqlite3.Error:
        logger.exception(
            "최근 현재가 조회 중 데이터베이스 오류 발생: stock_code=%s",
            stock_code,
        )
        raise


def fetch_daily_prices_by_stock(
    stock_code: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    특정 종목의 최근 일봉 데이터를 조회한다.

    Parameters
    ----------
    stock_code : str
        종목 코드

    limit : int, default=20
        조회할 최대 데이터 개수

    Returns
    -------
    list[dict[str, Any]]
        날짜를 기준으로 내림차순 정렬된 일봉 데이터
    """
    if limit <= 0:
        raise ValueError("limit은 1 이상의 정수여야 합니다.")

    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT *
                FROM daily_prices
                WHERE stock_code = ?
                ORDER BY date DESC
                LIMIT ?
            """, (stock_code, limit))

            rows = cur.fetchall()

        return [dict(row) for row in rows]

    except sqlite3.Error:
        logger.exception(
            "종목별 일봉 조회 중 데이터베이스 오류 발생: stock_code=%s",
            stock_code,
        )
        raise


def fetch_all_daily_prices() -> list[dict[str, Any]]:
    """
    daily_prices 테이블의 모든 일봉 데이터를 조회한다.

    Returns
    -------
    list[dict[str, Any]]
        종목 코드 오름차순, 날짜 내림차순으로 정렬된 일봉 데이터
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT *
                FROM daily_prices
                ORDER BY stock_code, date DESC
            """)

            rows = cur.fetchall()

        return [dict(row) for row in rows]

    except sqlite3.Error:
        logger.exception("전체 일봉 조회 중 데이터베이스 오류 발생")
        raise


def fetch_latest_daily_date(stock_code: str) -> str | None:
    """
    특정 종목의 가장 최근 일봉 저장 날짜를 조회한다.

    Parameters
    ----------
    stock_code : str
        종목 코드

    Returns
    -------
    str | None
        가장 최근 저장 날짜.
        저장된 일봉이 없으면 None을 반환한다.
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT MAX(date) AS latest_date
                FROM daily_prices
                WHERE stock_code = ?
            """, (stock_code,))

            row = cur.fetchone()

        if row is None:
            return None

        return row["latest_date"]

    except sqlite3.Error:
        logger.exception(
            "최근 일봉 날짜 조회 중 데이터베이스 오류 발생: stock_code=%s",
            stock_code,
        )
        raise


def fetch_saved_stock_codes() -> list[str]:
    """
    daily_prices 테이블에 저장된 종목 코드 목록을 조회한다.

    Returns
    -------
    list[str]
        중복이 제거된 종목 코드 목록
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT DISTINCT stock_code
                FROM daily_prices
                ORDER BY stock_code
            """)

            rows = cur.fetchall()

        return [row["stock_code"] for row in rows]

    except sqlite3.Error:
        logger.exception("저장 종목 코드 조회 중 데이터베이스 오류 발생")
        raise


def clear_current_prices() -> int:
    """
    current_prices 테이블의 모든 데이터를 삭제한다.

    Returns
    -------
    int
        삭제된 행의 개수
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM current_prices")

            deleted_count = cur.rowcount

        logger.info("현재가 데이터 %d건 삭제 완료", deleted_count)
        return deleted_count

    except sqlite3.Error:
        logger.exception("현재가 데이터 삭제 중 데이터베이스 오류 발생")
        raise


def clear_daily_prices() -> int:
    """
    daily_prices 테이블의 모든 데이터를 삭제한다.

    테이블 구조는 유지하고 저장된 데이터만 제거한다.

    Returns
    -------
    int
        삭제된 행의 개수
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM daily_prices")

            deleted_count = cur.rowcount

        logger.info("일봉 데이터 %d건 삭제 완료", deleted_count)
        return deleted_count

    except sqlite3.Error:
        logger.exception("일봉 데이터 삭제 중 데이터베이스 오류 발생")
        raise