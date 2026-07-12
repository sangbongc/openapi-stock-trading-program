
from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any, Iterable

from api import get_access_token, get_daily_price
from config import REQUEST_INTERVAL
from database import (
    fetch_daily_prices_by_stock,
    save_daily_prices,
)
from parser import parse_daily_price


DEFAULT_TARGET_ROWS = 250
DEFAULT_LOOKBACK_DAYS = 400
DEFAULT_MAX_REQUESTS = 5
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY = 2.0

def collect_daily_prices(
    stock_universe: Iterable[str | dict[str, Any]],
    target_rows: int = DEFAULT_TARGET_ROWS,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_requests_per_stock: int = DEFAULT_MAX_REQUESTS,
) -> list[dict[str, Any]]:
    """
    여러 종목의 과거 일봉을 수집하여 DB에 저장한다.

    API가 한 번에 목표 개수보다 적은 데이터를 반환할 수
    있으므로, 응답의 가장 오래된 날짜 이전으로 조회 종료일을
    이동하며 반복 조회한다.

    Parameters
    ----------
    stock_universe
        종목 코드 문자열 또는 종목 정보 딕셔너리 목록

    target_rows
        종목별로 확보할 목표 일봉 개수

    lookback_days
        한 API 요청의 조회 기간

    max_requests_per_stock
        종목별 최대 API 요청 횟수

    Returns
    -------
    list[dict[str, Any]]
        종목별 수집 결과
    """
    _validate_positive_integer(
        target_rows,
        "target_rows",
    )
    _validate_positive_integer(
        lookback_days,
        "lookback_days",
    )
    _validate_positive_integer(
        max_requests_per_stock,
        "max_requests_per_stock",
    )

    if stock_universe is None:
        raise ValueError(
            "stock_universe는 None일 수 없습니다."
        )

    if isinstance(stock_universe, (str, bytes)):
        raise TypeError(
            "stock_universe에는 종목 목록을 전달해야 합니다."
        )

    stocks = list(stock_universe)

    token = get_access_token()
    results: list[dict[str, Any]] = []

    for index, stock in enumerate(stocks):
        stock_code, stock_name = _extract_stock_info(stock)

        try:
            result = collect_stock_daily_prices(
                token=token,
                stock_code=stock_code,
                stock_name=stock_name,
                target_rows=target_rows,
                lookback_days=lookback_days,
                max_requests=max_requests_per_stock,
            )

        except Exception as error:
            result = {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "success": False,
                "fetched_count": 0,
                "saved_count": 0,
                "total_count": _get_saved_count(
                    stock_code
                ),
                "request_count": 0,
                "message": (
                    "일봉 수집 중 오류가 발생했습니다."
                ),
                "error": str(error),
            }

        results.append(result)

        # 마지막 종목 뒤에는 불필요하게 기다리지 않는다.
        if index < len(stocks) - 1:
            time.sleep(REQUEST_INTERVAL)

    return results


def collect_stock_daily_prices(
    token: str,
    stock_code: str,
    stock_name: str = "",
    target_rows: int = DEFAULT_TARGET_ROWS,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_requests: int = DEFAULT_MAX_REQUESTS,
) -> dict[str, Any]:
    """
    한 종목의 과거 일봉을 목표 개수까지 반복 수집한다.
    """
    _validate_stock_code(stock_code)
    _validate_positive_integer(
        target_rows,
        "target_rows",
    )
    _validate_positive_integer(
        lookback_days,
        "lookback_days",
    )
    _validate_positive_integer(
        max_requests,
        "max_requests",
    )
    existing_count = _get_saved_count(
    stock_code=stock_code,
    limit=max(target_rows, 1000),
    )

    if existing_count >= target_rows:
        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "success": True,
            "skipped": True,
            "fetched_count": 0,
            "saved_count": 0,
            "total_count": existing_count,
            "request_count": 0,
            "message": (
                f"이미 목표 일봉 {target_rows}개 이상이 "
                "저장되어 있어 수집을 건너뛰었습니다."
            ),
            "error": None,
        }

    # 같은 날짜가 여러 요청에 중복 포함되더라도
    # 종목코드와 날짜 기준으로 한 건만 유지한다.
    collected_by_date: dict[str, dict[str, Any]] = {}

    cursor_end = datetime.now()
    request_count = 0

    while (
        len(collected_by_date) < target_rows
        and request_count < max_requests
    ):
        request_count += 1

        end_date = cursor_end.strftime("%Y%m%d")
        start_date = (
            cursor_end
            - timedelta(days=lookback_days)
        ).strftime("%Y%m%d")

        response = _request_daily_price_with_retry(
            token=token,
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
        )

        rows = parse_daily_price(
            data=response,
            stock_code=stock_code,
            stock_name=stock_name,
        )

        if not rows:
            break

        for row in rows:
            date = str(row["date"])
            collected_by_date[date] = row

        oldest_date_text = min(
            str(row["date"])
            for row in rows
        )

        oldest_date = datetime.strptime(
            oldest_date_text,
            "%Y%m%d",
        )

        next_cursor_end = (
            oldest_date - timedelta(days=1)
        )

        # API가 동일한 가장 오래된 날짜를 계속 반환할 경우
        # 무한 반복되는 것을 방지한다.
        if next_cursor_end >= cursor_end:
            break

        cursor_end = next_cursor_end

        if len(collected_by_date) < target_rows:
            time.sleep(REQUEST_INTERVAL)

    sorted_rows = sorted(
        collected_by_date.values(),
        key=lambda row: row["date"],
        reverse=True,
    )

    # 목표 개수를 초과했으면 가장 최근 데이터부터 남긴다.
    rows_to_save = sorted_rows[:target_rows]

    saved_count = save_daily_prices(rows_to_save)
    total_count = _get_saved_count(
        stock_code=stock_code,
        limit=max(target_rows, 1000),
    )

    success = total_count >= target_rows

    if success:
        message = (
            f"목표 일봉 {target_rows}개 이상을 "
            "확보했습니다."
        )
    else:
        message = (
            f"현재 {total_count}개의 일봉을 확보했습니다. "
            f"목표는 {target_rows}개입니다."
        )

    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "success": success,
        "fetched_count": len(collected_by_date),
        "saved_count": saved_count,
        "total_count": total_count,
        "request_count": request_count,
        "message": message,
        "error": None,
    }


def _get_saved_count(
    stock_code: str,
    limit: int = 1000,
) -> int:
    """
    DB에 저장된 특정 종목의 일봉 개수를 반환한다.
    """
    rows = fetch_daily_prices_by_stock(
        stock_code=stock_code,
        limit=limit,
    )

    return len(rows)


def _extract_stock_info(
    stock: str | dict[str, Any],
) -> tuple[str, str]:
    """
    종목 코드 문자열 또는 딕셔너리에서
    종목 코드와 종목명을 추출한다.
    """
    if isinstance(stock, str):
        _validate_stock_code(stock)
        return stock, ""

    if not isinstance(stock, dict):
        raise TypeError(
            "각 종목은 종목 코드 문자열 또는 "
            "딕셔너리여야 합니다."
        )

    stock_code = (
        stock.get("stock_code")
        or stock.get("code")
    )

    stock_name = (
        stock.get("stock_name")
        or stock.get("name")
        or ""
    )

    if stock_code is None:
        raise ValueError(
            "종목 정보에 stock_code 또는 "
            "code가 없습니다."
        )

    normalized_code = str(stock_code).strip()
    _validate_stock_code(normalized_code)

    return normalized_code, str(stock_name).strip()


def _validate_stock_code(
    stock_code: str,
) -> None:
    if not isinstance(stock_code, str):
        raise TypeError(
            "stock_code는 문자열이어야 합니다."
        )

    if len(stock_code) != 6:
        raise ValueError(
            "stock_code는 6자리여야 합니다."
        )

    if not stock_code.isdigit():
        raise ValueError(
            "stock_code는 숫자로만 구성되어야 합니다."
        )


def _validate_positive_integer(
    value: Any,
    name: str,
) -> None:
    if isinstance(value, bool) or not isinstance(
        value,
        int,
    ):
        raise TypeError(
            f"{name}은 정수여야 합니다."
        )

    if value <= 0:
        raise ValueError(
            f"{name}은 1 이상이어야 합니다."
        )

def _request_daily_price_with_retry(
    token: str,
    stock_code: str,
    start_date: str,
    end_date: str,
    retry_count: int = DEFAULT_RETRY_COUNT,
    retry_delay: float = DEFAULT_RETRY_DELAY,
) -> dict[str, Any]:
    """
    일시적인 연결 실패나 호출 제한 발생 시
    대기 후 일봉 API를 재호출한다.
    """
    last_error: Exception | None = None

    for attempt in range(1, retry_count + 1):
        try:
            return get_daily_price(
                token=token,
                stock_code=stock_code,
                start_date=start_date,
                end_date=end_date,
            )

        except Exception as error:
            last_error = error
            error_message = str(error)

            retryable = (
                "EGW00201" in error_message
                or "초당 거래건수" in error_message
                or "서버에 연결할 수 없습니다"
                in error_message
                or "Connection" in error_message
                or "Timeout" in error_message
            )

            if not retryable:
                raise

            if attempt >= retry_count:
                break

            wait_seconds = retry_delay * attempt

            print(
                f"[{stock_code}] API 요청 실패. "
                f"{wait_seconds:.1f}초 후 재시도합니다. "
                f"({attempt}/{retry_count})"
            )

            time.sleep(wait_seconds)

    if last_error is not None:
        raise last_error

    raise RuntimeError(
        "일봉 API 요청에 실패했습니다."
    )
