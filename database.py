import logging
import os
import sqlite3
from typing import Any

from config import DB_PATH
from datetime import datetime
from typing import Optional

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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price INTEGER NOT NULL,
                order_no TEXT,
                status TEXT NOT NULL,
                message_code TEXT,
                message TEXT)
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


def save_order(
    stock_code: str,
    side: str,
    order_type: str,
    quantity: int,
    price: int,
    status: str,
    order_no: Optional[str] = None,
    message_code: Optional[str] = None,
    message: Optional[str] = None,
) -> int:
    """
    주문 요청과 결과를 orders 테이블에 저장한다.

    Parameters
    ----------
    stock_code : str
        6자리 종목코드.
        잘못된 입력을 기록하는 REJECTED 상태에서는
        대체 코드 000000을 사용할 수 있다.

    side : str
        BUY, SELL 또는 UNKNOWN

    order_type : str
        MARKET, LIMIT 또는 UNKNOWN

    quantity : int
        주문 수량.
        REJECTED 상태에서는 0을 허용한다.

    price : int
        주문 가격. 시장가는 0

    status : str
         ACCEPTED 또는 FAILED

    ACCEPTED는 증권사가 주문을 정상 접수했다는 의미이며,
    실제 체결 완료를 의미하지 않는다.

    order_no : str, optional
        증권사에서 반환한 주문번호

    message_code : str, optional
        오류 종류 또는 API 응답 메시지 코드

    message : str, optional
        검증 실패, API 응답 또는 오류 메시지

    Returns
    -------
    int
        저장된 주문 기록의 ID
    """
    stock_code = str(stock_code).strip()
    side = str(side).upper().strip()
    order_type = str(order_type).upper().strip()
    status = str(status).upper().strip()

    allowed_statuses = {
        "FAILED",
        "ACCEPTED",
    }

    if status not in allowed_statuses:
        raise ValueError(
            "status는 ACCEPTED 또는 FAILED 여야 합니다."
        )

    if len(stock_code) != 6 or not stock_code.isdigit():
        raise ValueError(
            "stock_code는 숫자로 된 6자리 종목코드여야 합니다."
        )

    allowed_sides = {
        "BUY",
        "SELL",
    }

    allowed_order_types = {
        "MARKET",
        "LIMIT",
    }

    if status == "REJECTED":
        allowed_sides.add("UNKNOWN")
        allowed_order_types.add("UNKNOWN")

    if side not in allowed_sides:
        raise ValueError(
            f"{status} 상태에서 허용되지 않는 side입니다: "
            f"{side}"
        )

    if order_type not in allowed_order_types:
        raise ValueError(
            f"{status} 상태에서 허용되지 않는 "
            f"order_type입니다: {order_type}"
        )

    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise TypeError(
            "quantity는 정수여야 합니다."
        )

    if status == "REJECTED":
        if quantity < 0:
            raise ValueError(
                "REJECTED 상태의 quantity는 "
                "0 이상이어야 합니다."
            )
    elif quantity <= 0:
        raise ValueError(
            "quantity는 1 이상이어야 합니다."
        )

    if isinstance(price, bool) or not isinstance(price, int):
        raise TypeError(
            "price는 정수여야 합니다."
        )

    if price < 0:
        raise ValueError(
            "price는 0 이상이어야 합니다."
        )

    if order_type == "MARKET" and price != 0:
        raise ValueError(
        "시장가 주문은 가격을 지정할 수 없습니다. "
        "price는 0으로 설정해야 합니다."
    )

    if order_type == "LIMIT" and price <= 0:
        raise ValueError(
        "지정가 주문에서는 price를 1 이상으로 지정해야 합니다."
    )
    if order_no is not None:
        order_no = str(order_no).strip() or None

    if message_code is not None:
        message_code = str(message_code).strip() or None

    if message is not None:
        message = str(message).strip() or None

    created_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO orders (
                created_at,
                stock_code,
                side,
                order_type,
                quantity,
                price,
                order_no,
                status,
                message_code,
                message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                stock_code,
                side,
                order_type,
                quantity,
                price,
                order_no,
                status,
                message_code,
                message,
            ),
        )

        conn.commit()

        return cursor.lastrowid

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def fetch_orders(
    stock_code: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """
    최근 주문 기록을 조회한다.

    Parameters
    ----------
    stock_code : str, optional
        특정 종목만 조회할 때 사용하는 종목코드

    limit : int, default=100
        최대 조회 건수

    Returns
    -------
    list[dict]
        주문 기록 목록
    """
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError("limit은 정수여야 합니다.")

    if limit <= 0:
        raise ValueError("limit은 1 이상이어야 합니다.")

    conn = get_connection()
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()

        if stock_code is None:
            cursor.execute(
                """
                SELECT *
                FROM orders
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )

        else:
            stock_code = str(stock_code).strip()

            if len(stock_code) != 6 or not stock_code.isdigit():
                raise ValueError(
                    "stock_code는 숫자로 된 "
                    "6자리 종목코드여야 합니다."
                )

            cursor.execute(
                """
                SELECT *
                FROM orders
                WHERE stock_code = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (
                    stock_code,
                    limit,
                ),
            )

        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()