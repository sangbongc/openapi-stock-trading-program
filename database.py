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
    conn.execute("PRAGMA foreign_keys = ON")

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
                updated_at TEXT NOT NULL,

                stock_code TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,

                quantity INTEGER NOT NULL,
                price INTEGER NOT NULL,

                order_no TEXT,

                status TEXT NOT NULL,

                execution_status TEXT NOT NULL
                    DEFAULT 'NOT_APPLICABLE',

                filled_quantity INTEGER NOT NULL
                    DEFAULT 0,

                 remaining_quantity INTEGER NOT NULL
                    DEFAULT 0,

                average_fill_price REAL NOT NULL
                    DEFAULT 0,

                message_code TEXT,
                    message TEXT)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                order_no TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                executed_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (order_id)
                    REFERENCES orders(id)
                    ON DELETE CASCADE,

                UNIQUE (
                    order_no,
                    quantity,
                    price,
                    executed_at
                )
            )
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
    if status == "ACCEPTED":
            execution_status = "PENDING"
            remaining_quantity = quantity
    else:
            execution_status = "NOT_APPLICABLE"
            remaining_quantity = 0

    filled_quantity = 0
    average_fill_price = 0
    updated_at = created_at
    
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
    """
    INSERT INTO orders (
        created_at,
        updated_at,
        stock_code,
        side,
        order_type,
        quantity,
        price,
        order_no,
        status,
        execution_status,
        filled_quantity,
        remaining_quantity,
        average_fill_price,
        message_code,
        message
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        created_at,
        updated_at,
        stock_code,
        side,
        order_type,
        quantity,
        price,
        order_no,
        status,
        execution_status,
        filled_quantity,
        remaining_quantity,
        average_fill_price,
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

def migrate_orders_table() -> None:
    """
    기존 orders 테이블에 체결 관리용 컬럼을 추가한다.

    이미 존재하는 컬럼은 추가하지 않는다.
    """
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(orders)")
        columns = {
            row["name"]
            for row in cursor.fetchall()
        }

        if "updated_at" not in columns:
            cursor.execute(
                """
                ALTER TABLE orders
                ADD COLUMN updated_at TEXT
                """
            )

        if "execution_status" not in columns:
            cursor.execute(
                """
                ALTER TABLE orders
                ADD COLUMN execution_status TEXT
                NOT NULL DEFAULT 'NOT_APPLICABLE'
                """
            )

        if "filled_quantity" not in columns:
            cursor.execute(
                """
                ALTER TABLE orders
                ADD COLUMN filled_quantity INTEGER
                NOT NULL DEFAULT 0
                """
            )

        if "remaining_quantity" not in columns:
            cursor.execute(
                """
                ALTER TABLE orders
                ADD COLUMN remaining_quantity INTEGER
                NOT NULL DEFAULT 0
                """
            )

        if "average_fill_price" not in columns:
            cursor.execute(
                """
                ALTER TABLE orders
                ADD COLUMN average_fill_price REAL
                NOT NULL DEFAULT 0
                """
            )

        cursor.execute(
            """
            UPDATE orders
            SET updated_at = created_at
            WHERE updated_at IS NULL
            """
        )

        cursor.execute(
            """
            UPDATE orders
            SET
                execution_status = 'PENDING',
                remaining_quantity = quantity
            WHERE status = 'ACCEPTED'
              AND execution_status = 'NOT_APPLICABLE'
            """
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def fetch_order_by_order_no(
    order_no: str,
) -> dict[str, Any] | None:
    """
    한국투자증권 주문번호로 로컬 주문을 조회한다.
    """
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM orders
            WHERE order_no = ?
            """,
            (order_no,),
        )

        row = cursor.fetchone()

        if row is None:
            return None

        return dict(row)

    finally:
        conn.close()


def fetch_open_orders() -> list[dict[str, Any]]:
    """
    체결이 아직 종료되지 않은 접수 주문을 조회한다.
    """
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM orders
            WHERE status = 'ACCEPTED'
              AND execution_status IN (
                  'PENDING',
                  'PARTIAL'
              )
              AND order_no IS NOT NULL
            ORDER BY id ASC
            """
        )

        return [
            dict(row)
            for row in cursor.fetchall()
        ]

    finally:
        conn.close()


def update_order_execution(
    order_no: str,
    filled_quantity: int,
    remaining_quantity: int,
    average_fill_price: float,
    execution_status: str,
) -> None:
    """
    orders 테이블의 체결 상태를 업데이트한다.

    status는 주문 접수 결과인 ACCEPTED/FAILED를 유지하고,
    execution_status만 체결 진행 상태로 변경한다.
    """
    order_no = str(order_no).strip()
    execution_status = str(execution_status).upper().strip()

    allowed_execution_statuses = {
        "NOT_APPLICABLE",
        "PENDING",
        "PARTIAL",
        "FILLED",
        "CANCELLED",
        "REJECTED",
    }

    if not order_no:
        raise ValueError("order_no는 비어 있을 수 없습니다.")

    if execution_status not in allowed_execution_statuses:
        raise ValueError(
            "지원하지 않는 execution_status입니다: "
            f"{execution_status}"
        )

    if filled_quantity < 0:
        raise ValueError(
            "filled_quantity는 0 이상이어야 합니다."
        )

    if remaining_quantity < 0:
        raise ValueError(
            "remaining_quantity는 0 이상이어야 합니다."
        )

    if average_fill_price < 0:
        raise ValueError(
            "average_fill_price는 0 이상이어야 합니다."
        )

    updated_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE orders
            SET
                updated_at = ?,
                execution_status = ?,
                filled_quantity = ?,
                remaining_quantity = ?,
                average_fill_price = ?
            WHERE order_no = ?
            """,
            (
                updated_at,
                execution_status,
                filled_quantity,
                remaining_quantity,
                average_fill_price,
                order_no,
            ),
        )

        if cursor.rowcount == 0:
            raise ValueError(
                f"주문번호 {order_no}에 해당하는 "
                "주문이 없습니다."
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def save_execution(
    order_id: int,
    order_no: str,
    stock_code: str,
    side: str,
    quantity: int,
    price: float,
    executed_at: str,
) -> int | None:
    """
    체결 이력 한 건을 executions 테이블에 저장한다.

    동일한 주문번호, 수량, 가격, 체결시각의 데이터가 이미 존재하면
    중복 저장하지 않고 None을 반환한다.

    Returns
    -------
    int | None
        새로 저장된 executions 테이블의 ID.
        중복 데이터이면 None.
    """
    if order_id <= 0:
        raise ValueError("order_id는 1 이상이어야 합니다.")

    if not order_no.strip():
        raise ValueError("order_no는 비어 있을 수 없습니다.")

    if not stock_code.strip():
        raise ValueError("stock_code는 비어 있을 수 없습니다.")

    normalized_side = side.upper()

    if normalized_side not in {"BUY", "SELL"}:
        raise ValueError("side는 BUY 또는 SELL이어야 합니다.")

    if quantity <= 0:
        raise ValueError("체결수량은 1 이상이어야 합니다.")

    if price < 0:
        raise ValueError("체결가격은 0 이상이어야 합니다.")

    if not executed_at.strip():
        raise ValueError("executed_at은 비어 있을 수 없습니다.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO executions (
                order_id,
                order_no,
                stock_code,
                side,
                quantity,
                price,
                executed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                order_no,
                stock_code,
                normalized_side,
                quantity,
                price,
                executed_at,
            ),
        )

        conn.commit()

        if cursor.rowcount == 0:
            return None

        return int(cursor.lastrowid)

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def fetch_executions_by_order_no(
    order_no: str,
) -> list[dict[str, Any]]:
    """
    특정 주문번호에 해당하는 체결내역을 조회한다.
    """
    if not order_no.strip():
        raise ValueError("order_no는 비어 있을 수 없습니다.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id,
                order_id,
                order_no,
                stock_code,
                side,
                quantity,
                price,
                executed_at,
                created_at
            FROM executions
            WHERE order_no = ?
            ORDER BY executed_at ASC, id ASC
            """,
            (order_no,),
        )

        return [
            dict(row)
            for row in cursor.fetchall()
        ]

    finally:
        conn.close()

def fetch_executions_by_order_id(
    order_id: int,
) -> list[dict[str, Any]]:
    """
    로컬 orders 테이블의 ID를 기준으로 체결내역을 조회한다.
    """
    if order_id <= 0:
        raise ValueError("order_id는 1 이상이어야 합니다.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id,
                order_id,
                order_no,
                stock_code,
                side,
                quantity,
                price,
                executed_at,
                created_at
            FROM executions
            WHERE order_id = ?
            ORDER BY executed_at ASC, id ASC
            """,
            (order_id,),
        )

        return [
            dict(row)
            for row in cursor.fetchall()
        ]

    finally:
        conn.close()

def fetch_executions(
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    최근 체결내역을 조회한다.
    """
    if limit <= 0:
        raise ValueError("limit은 1 이상이어야 합니다.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id,
                order_id,
                order_no,
                stock_code,
                side,
                quantity,
                price,
                executed_at,
                created_at
            FROM executions
            ORDER BY executed_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )

        return [
            dict(row)
            for row in cursor.fetchall()
        ]

    finally:
        conn.close()

def get_total_executed_quantity(
    order_no: str,
) -> int:
    """
    특정 주문번호의 executions 테이블 누적 체결수량을 반환한다.
    """
    if not order_no.strip():
        raise ValueError("order_no는 비어 있을 수 없습니다.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COALESCE(SUM(quantity), 0)
            FROM executions
            WHERE order_no = ?
            """,
            (order_no,),
        )

        result = cursor.fetchone()

        return int(result[0])

    finally:
        conn.close()

def get_average_execution_price(
    order_no: str,
) -> float:
    """
    특정 주문번호의 가중평균 체결가격을 반환한다.
    """
    if not order_no.strip():
        raise ValueError("order_no는 비어 있을 수 없습니다.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                COALESCE(SUM(quantity * price), 0),
                COALESCE(SUM(quantity), 0)
            FROM executions
            WHERE order_no = ?
            """,
            (order_no,),
        )

        total_amount, total_quantity = cursor.fetchone()

        if total_quantity == 0:
            return 0.0

        return float(total_amount) / int(total_quantity)

    finally:
        conn.close()