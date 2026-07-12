from json import JSONDecodeError
from pathlib import Path
from typing import Any
import json
import requests
from requests import Response, Session
from requests.exceptions import RequestException
import logging
from datetime import datetime, timedelta
import os
from config import (
    ACCOUNT_NO,
    ACCOUNT_PRODUCT_CODE,
    APP_KEY,
    APP_SECRET,
    BASE_URL,
    REQUEST_INTERVAL,
    TOKEN_PATH,
    IS_VIRTUAL
)
REQUEST_TIMEOUT = 10
TOKEN_EXPIRY_BUFFER_MINUTES = 5

logger = logging.getLogger(__name__)

# TCP 연결을 재사용해 반복 호출 비용을 줄인다.
_SESSION = requests.Session()


class KISAPIError(Exception):
    """한국투자증권 API 호출 과정에서 발생하는 오류."""


def validate_api_config() -> None:
    """API 호출에 필요한 설정값이 존재하는지 확인한다."""
    required_values = {
        "KIS_APP_KEY": APP_KEY,
        "KIS_APP_SECRET": APP_SECRET,
        "KIS_BASE_URL": BASE_URL,
        "TOKEN_PATH": TOKEN_PATH,
    }

    missing_values = [
        name
        for name, value in required_values.items()
        if not value
    ]

    if missing_values:
        raise ValueError(
            "필수 설정값이 존재하지 않습니다: "
            + ", ".join(missing_values)
        )


def build_headers(
    token: str,
    tr_id: str,
) -> dict[str, str]:
    """일반적인 한국투자증권 API 요청 헤더를 생성한다."""
    if not token:
        raise ValueError("접근토큰이 비어 있습니다.")

    if not tr_id:
        raise ValueError("TR ID가 비어 있습니다.")

    return {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": tr_id,
        "custtype": "P",
    }


def _build_url(endpoint: str) -> str:
    """BASE_URL과 endpoint 사이의 슬래시를 안전하게 결합한다."""
    if not endpoint:
        raise ValueError("API endpoint가 비어 있습니다.")

    return f"{BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"


def save_token(
    access_token: str,
    token_type: str,
    expires_at: datetime,
) -> None:
    """
    토큰 정보를 JSON 파일에 저장한다.

    임시 파일에 먼저 기록한 뒤 교체하여 저장 도중 파일이
    손상될 가능성을 줄인다.
    """
    token_path = Path(TOKEN_PATH)
    token_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    token_data = {
        "access_token": access_token,
        "token_type": token_type,
        "expires_at": expires_at.isoformat(),
    }

    temporary_path = token_path.with_suffix(
        token_path.suffix + ".tmp"
    )

    try:
        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                token_data,
                file,
                ensure_ascii=False,
                indent=4,
            )

        os.replace(
            temporary_path,
            token_path,
        )

    except OSError as error:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass

        raise KISAPIError(
            f"토큰 캐시 저장에 실패했습니다: {error}"
        ) from error


def delete_cached_token() -> None:
    """로컬 토큰 캐시 파일을 삭제한다."""
    token_path = Path(TOKEN_PATH)

    try:
        token_path.unlink(missing_ok=True)

    except OSError as error:
        logger.warning(
            "토큰 캐시 파일을 삭제하지 못했습니다: %s",
            error,
        )


def load_token() -> str | None:
    """
    저장된 접근토큰을 읽는다.

    서버가 알려준 만료 시각보다 5분 이상 남은 경우에만
    저장된 토큰을 반환한다.
    """
    token_path = Path(TOKEN_PATH)

    if not token_path.exists():
        return None

    try:
        with token_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        access_token = data.get("access_token")
        expires_at_text = data.get("expires_at")

        if not access_token or not expires_at_text:
            logger.warning(
                "토큰 캐시에 필요한 정보가 없습니다."
            )
            delete_cached_token()
            return None

        expires_at = datetime.fromisoformat(
            expires_at_text
        )

    except (
        OSError,
        JSONDecodeError,
        TypeError,
        ValueError,
    ) as error:
        logger.warning(
            "토큰 캐시를 읽지 못했습니다: %s",
            error,
        )
        delete_cached_token()
        return None

    refresh_threshold = expires_at - timedelta(
        minutes=TOKEN_EXPIRY_BUFFER_MINUTES
    )

    if datetime.now() >= refresh_threshold:
        logger.info(
            "저장된 토큰의 만료가 임박했거나 "
            "이미 만료되었습니다."
        )
        delete_cached_token()
        return None

    return access_token


def parse_json_response(
    response: Response,
) -> dict[str, Any]:
    """서버 응답을 JSON 딕셔너리로 변환한다."""
    try:
        data = response.json()

    except (JSONDecodeError, ValueError) as error:
        raise KISAPIError(
            "API 서버가 올바른 JSON을 반환하지 않았습니다."
        ) from error

    if not isinstance(data, dict):
        raise KISAPIError(
            "API 응답이 딕셔너리 형식이 아닙니다."
        )

    return data


def validate_business_response(
    data: dict[str, Any],
) -> None:
    """
    응답 본문의 rt_cd를 이용해 업무 처리 성공 여부를 확인한다.

    토큰 발급 응답에는 rt_cd가 없을 수 있으므로,
    rt_cd가 존재하는 응답만 검사한다.
    """
    rt_cd = data.get("rt_cd")

    if rt_cd is None:
        return

    if str(rt_cd) != "0":
        message_code = data.get(
            "msg_cd",
            "UNKNOWN",
        )
        message = data.get(
            "msg1",
            "알 수 없는 API 오류가 발생했습니다.",
        )

        raise KISAPIError(
            f"API 요청 실패 [{message_code}]: {message}"
        )


def _get_safe_response_text(
    response: Response | None,
    max_length: int = 500,
) -> str:
    """HTTP 오류 응답을 제한된 길이의 문자열로 변환한다."""
    if response is None:
        return ""

    text = response.text.strip()

    if not text:
        return ""

    if len(text) > max_length:
        text = text[:max_length] + "..."

    return f"서버 응답: {text}"


def _parse_token_expiration(
    data: dict[str, Any],
) -> datetime:
    """
    토큰 응답에서 만료 시각을 추출한다.

    우선순위:
    1. access_token_token_expired
    2. expires_in을 이용한 계산
    """
    expiration_text = data.get(
        "access_token_token_expired"
    )

    if expiration_text:
        try:
            return datetime.strptime(
                expiration_text,
                "%Y-%m-%d %H:%M:%S",
            )

        except ValueError as error:
            raise KISAPIError(
                "토큰 만료 시각의 형식이 올바르지 않습니다: "
                f"{expiration_text}"
            ) from error

    expires_in_raw = data.get("expires_in")

    if expires_in_raw is None:
        raise KISAPIError(
            "토큰 응답에 만료시간 정보가 없습니다."
        )

    try:
        expires_in = int(expires_in_raw)

    except (TypeError, ValueError) as error:
        raise KISAPIError(
            "expires_in 값이 올바른 숫자가 아닙니다."
        ) from error

    if expires_in <= 0:
        raise KISAPIError(
            "expires_in 값은 0보다 커야 합니다."
        )

    return datetime.now() + timedelta(
        seconds=expires_in
    )


def get_access_token(
    force_refresh: bool = False,
) -> str:
    """
    한국투자증권 접근토큰을 반환한다.

    저장된 토큰이 유효하면 재사용하고,
    토큰이 없거나 만료가 임박한 경우 서버에 발급을 요청한다.
    """
    validate_api_config()

    if not force_refresh:
        cached_token = load_token()

        if cached_token:
            logger.info("저장된 접근토큰을 사용합니다.")
            return cached_token

    url = _build_url("/oauth2/tokenP")

    headers = {
        "content-type": "application/json; charset=utf-8"
    }

    body = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
    }

    try:
        response = _SESSION.post(
            url=url,
            headers=headers,
            json=body,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

    except requests.Timeout as error:
        raise KISAPIError(
            "접근토큰 발급 요청 시간이 초과되었습니다."
        ) from error

    except requests.ConnectionError as error:
        raise KISAPIError(
            "한국투자증권 서버에 연결할 수 없습니다."
        ) from error

    except requests.HTTPError as error:
        response_text = _get_safe_response_text(
            error.response
        )

        raise KISAPIError(
            "접근토큰 발급 과정에서 HTTP 오류가 "
            f"발생했습니다. {response_text}"
        ) from error

    except RequestException as error:
        raise KISAPIError(
            f"접근토큰 발급 요청에 실패했습니다: {error}"
        ) from error

    data = parse_json_response(response)

    access_token = data.get("access_token")
    token_type = data.get("token_type")

    if not access_token:
        error_message = data.get(
            "error_description",
            data.get(
                "msg1",
                "응답에 access_token이 없습니다.",
            ),
        )

        raise KISAPIError(
            f"접근토큰 발급 실패: {error_message}"
        )

    if not token_type:
        raise KISAPIError(
            "응답에 token_type이 없습니다."
        )

    if str(token_type).lower() != "bearer":
        raise KISAPIError(
            "예상하지 못한 토큰 유형을 받았습니다: "
            f"{token_type}"
        )

    expires_at = _parse_token_expiration(data)

    save_token(
        access_token=access_token,
        token_type=str(token_type),
        expires_at=expires_at,
    )

    logger.info(
        "접근토큰 발급 완료 (만료 시각: %s)",
        expires_at.strftime("%Y-%m-%d %H:%M:%S"),
    )

    return access_token


def request_json(
    method: str,
    endpoint: str,
    token: str,
    tr_id: str,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    retry_on_unauthorized: bool = True,
    session: Session | None = None,
) -> dict[str, Any]:
    """한국투자증권 API에 공통 HTTP 요청을 보낸다."""
    validate_api_config()

    request_session = session or _SESSION
    url = _build_url(endpoint)

    try:
        response = request_session.request(
            method=method.upper(),
            url=url,
            headers=build_headers(token, tr_id),
            params=params,
            json=json_body,
            timeout=REQUEST_TIMEOUT,
        )

        if (
            response.status_code == 401
            and retry_on_unauthorized
        ):
            logger.warning(
                "토큰 인증에 실패하여 토큰을 한 번 갱신합니다."
            )

            delete_cached_token()

            refreshed_token = get_access_token(
                force_refresh=True
            )

            return request_json(
                method=method,
                endpoint=endpoint,
                token=refreshed_token,
                tr_id=tr_id,
                params=params,
                json_body=json_body,
                retry_on_unauthorized=False,
                session=request_session,
            )

        response.raise_for_status()

    except requests.Timeout as error:
        raise KISAPIError(
            f"API 요청 시간이 초과되었습니다: {endpoint}"
        ) from error

    except requests.ConnectionError as error:
        raise KISAPIError(
            "한국투자증권 서버에 연결할 수 없습니다."
        ) from error

    except requests.HTTPError as error:
        status_code = (
            error.response.status_code
            if error.response is not None
            else "UNKNOWN"
        )

        response_text = _get_safe_response_text(
            error.response
        )

        raise KISAPIError(
            f"API HTTP 오류 [{status_code}]: "
            f"{endpoint}. {response_text}"
        ) from error

    except RequestException as error:
        raise KISAPIError(
            f"API 요청에 실패했습니다: {error}"
        ) from error

    data = parse_json_response(response)
    validate_business_response(data)

    return data


def get_current_price(
    token: str,
    stock_code: str,
) -> dict[str, Any]:
    """특정 국내주식 종목의 현재가 정보를 조회한다."""
    _validate_stock_code(stock_code)

    endpoint = (
        "/uapi/domestic-stock/v1/quotations/"
        "inquire-price"
    )

    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code,
    }

    return request_json(
        method="GET",
        endpoint=endpoint,
        token=token,
        tr_id="FHKST01010100",
        params=params,
    )


def get_daily_price(
    token: str,
    stock_code: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """특정 국내주식 종목의 기간별 일봉 데이터를 조회한다."""
    _validate_stock_code(stock_code)
    _validate_date_range(start_date, end_date)

    endpoint = (
        "/uapi/domestic-stock/v1/quotations/"
        "inquire-daily-itemchartprice"
    )

    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code,
        "FID_INPUT_DATE_1": start_date,
        "FID_INPUT_DATE_2": end_date,
        "FID_PERIOD_DIV_CODE": "D",
        "FID_ORG_ADJ_PRC": "1",
    }

    return request_json(
        method="GET",
        endpoint=endpoint,
        token=token,
        tr_id="FHKST03010100",
        params=params,
    )


def _validate_stock_code(
    stock_code: str,
) -> None:
    """국내주식 종목 코드가 6자리 숫자 문자열인지 검사한다."""
    if not isinstance(stock_code, str):
        raise TypeError(
            "종목 코드는 문자열로 입력해야 합니다."
        )

    if len(stock_code) != 6:
        raise ValueError(
            "종목 코드는 6자리여야 합니다."
        )

    if not stock_code.isdigit():
        raise ValueError(
            "종목 코드는 숫자로만 구성되어야 합니다."
        )


def _validate_date(
    date_text: str,
) -> datetime:
    """날짜가 YYYYMMDD 형식인지 검사한다."""
    if not isinstance(date_text, str):
        raise TypeError(
            "날짜는 문자열로 입력해야 합니다."
        )

    try:
        return datetime.strptime(
            date_text,
            "%Y%m%d",
        )

    except ValueError as error:
        raise ValueError(
            "날짜는 YYYYMMDD 형식이어야 합니다. "
            "예: '20260711'"
        ) from error


def _validate_date_range(
    start_date: str,
    end_date: str,
) -> None:
    """조회 시작일과 종료일의 형식 및 순서를 검사한다."""
    start_datetime = _validate_date(start_date)
    end_datetime = _validate_date(end_date)

    if start_datetime > end_datetime:
        raise ValueError(
            "조회 시작일은 종료일보다 늦을 수 없습니다."
        )


def _place_cash_order(
    stock_code: str,
    quantity: int,
    price: int = 0,
    side: str = "BUY",
    order_type: str = "MARKET",
) -> dict[str, Any]:
    """
    국내주식 현금 주문을 요청한다.

    Parameters
    ----------
    stock_code : str
        6자리 종목코드

    quantity : int
        주문 수량

    price : int, default=0
        주문 가격.
        시장가 주문은 0을 사용한다.

    side : str, default="BUY"
        BUY 또는 SELL

    order_type : str, default="MARKET"
        MARKET 또는 LIMIT

    Returns
    -------
    dict
        한국투자증권 주문 API 응답

    Raises
    ------
    ValueError
        잘못된 종목코드, 수량, 가격, 주문 방향 또는 주문 유형인 경우

    RuntimeError
        API가 주문을 거절한 경우

    requests.RequestException
        네트워크 요청에 실패한 경우
    """
    stock_code = str(stock_code).strip()
    side = side.upper().strip()
    order_type = order_type.upper().strip()

    if len(stock_code) != 6 or not stock_code.isdigit():
        raise ValueError(
            "stock_code는 숫자로 된 6자리 종목코드여야 합니다."
        )

    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise TypeError("quantity는 정수여야 합니다.")

    if quantity <= 0:
        raise ValueError("quantity는 1 이상이어야 합니다.")

    if isinstance(price, bool) or not isinstance(price, int):
        raise TypeError("price는 정수여야 합니다.")

    if price < 0:
        raise ValueError("price는 0 이상이어야 합니다.")

    if side not in {"BUY", "SELL"}:
        raise ValueError("side는 BUY 또는 SELL이어야 합니다.")

    if order_type not in {"MARKET", "LIMIT"}:
        raise ValueError(
            "order_type은 MARKET 또는 LIMIT이어야 합니다."
        )

    if order_type == "LIMIT" and price <= 0:
        raise ValueError(
            "지정가 주문의 price는 1 이상이어야 합니다."
        )

    if order_type == "MARKET":
        order_division = "01"
        order_price = "0"
    else:
        order_division = "00"
        order_price = str(price)

    # 모의투자용 TR ID
    tr_id = (
        "VTTC0802U"
        if side == "BUY"
        else "VTTC0801U"
    )

    access_token = get_access_token()

    url = (
        f"{BASE_URL}"
        "/uapi/domestic-stock/v1/trading/order-cash"
    )

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": tr_id,
        "custtype": "P",
    }

    body = {
        "CANO": ACCOUNT_NO,
        "ACNT_PRDT_CD": ACCOUNT_PRODUCT_CODE,
        "PDNO": stock_code,
        "ORD_DVSN": order_division,
        "ORD_QTY": str(quantity),
        "ORD_UNPR": order_price,
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=body,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

    except requests.Timeout as exc:
        raise requests.Timeout(
            "주문 요청 시간이 초과되었습니다."
        ) from exc

    except requests.ConnectionError as exc:
        raise requests.ConnectionError(
            "한국투자증권 주문 서버에 연결할 수 없습니다."
        ) from exc

    except requests.HTTPError as exc:
        raise requests.HTTPError(
            f"주문 API HTTP 오류: "
            f"{response.status_code} {response.text}"
        ) from exc

    result = response.json()

    if result.get("rt_cd") != "0":
        message_code = result.get("msg_cd", "UNKNOWN")
        message = result.get(
            "msg1",
            "알 수 없는 주문 오류",
        )

        raise RuntimeError(
            f"주문 실패 [{message_code}]: {message}"
        )

    return result

def buy_stock(
    stock_code: str,
    quantity: int,
    price: int = 0,
    order_type: str = "MARKET",
) -> dict[str, Any]:
    """
    국내주식을 현금 매수한다.

    Parameters
    ----------
    stock_code : str
        6자리 종목코드

    quantity : int
        매수 수량

    price : int, default=0
        지정가 주문 가격.
        시장가 주문에서는 사용하지 않는다.

    order_type : str, default="MARKET"
        MARKET 또는 LIMIT

    Returns
    -------
    dict
        주문 API 응답
    """
    return _place_cash_order(
        stock_code=stock_code,
        quantity=quantity,
        price=price,
        side="BUY",
        order_type=order_type,
    )

def sell_stock(
    stock_code: str,
    quantity: int,
    price: int = 0,
    order_type: str = "MARKET",
) -> dict[str, Any]:
    """
    국내주식을 현금 매도한다.

    Parameters
    ----------
    stock_code : str
        6자리 종목코드

    quantity : int
        매도 수량

    price : int, default=0
        지정가 주문 가격.
        시장가 주문에서는 사용하지 않는다.

    order_type : str, default="MARKET"
        MARKET 또는 LIMIT

    Returns
    -------
    dict
        주문 API 응답
    """
    return _place_cash_order(
        stock_code=stock_code,
        quantity=quantity,
        price=price,
        side="SELL",
        order_type=order_type,
    )

def _to_int(value: Any, default: int = 0) -> int:
    """
    API 응답값을 정수로 변환한다.
    """
    if value in (None, ""):
        return default

    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    """
    API 응답값을 실수로 변환한다.
    """
    if value in (None, ""):
        return default

    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default
    
def get_account_balance(
    include_zero_quantity: bool = False,
    max_pages: int = 10,
) -> dict[str, Any]:
    """
    국내주식 계좌의 보유 종목과 계좌 평가 정보를 조회한다.

    Parameters
    ----------
    include_zero_quantity : bool, default=False
        보유수량이 0인 종목도 결과에 포함할지 여부

    max_pages : int, default=10
        연속조회 최대 횟수

    Returns
    -------
    dict
        현금, 평가금액, 손익 및 보유종목 목록

    Raises
    ------
    TypeError
        입력값의 자료형이 잘못된 경우

    ValueError
        입력값이 허용 범위를 벗어난 경우

    RuntimeError
        한국투자증권 API가 조회 요청을 거절한 경우

    requests.RequestException
        네트워크 또는 HTTP 요청에 실패한 경우
    """
    if not isinstance(include_zero_quantity, bool):
        raise TypeError(
            "include_zero_quantity는 bool이어야 합니다."
        )

    if isinstance(max_pages, bool) or not isinstance(max_pages, int):
        raise TypeError("max_pages는 정수여야 합니다.")

    if max_pages <= 0:
        raise ValueError("max_pages는 1 이상이어야 합니다.")

    access_token = get_access_token()

    url = (
        f"{BASE_URL}"
        "/uapi/domestic-stock/v1/trading/inquire-balance"
    )

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "VTTC8434R",
        "custtype": "P",
    }

    positions: list[dict[str, Any]] = []
    account_summary: dict[str, Any] = {}

    ctx_area_fk100 = ""
    ctx_area_nk100 = ""
    tr_cont = ""

    for _ in range(max_pages):
        params = {
            "CANO": ACCOUNT_NO,
            "ACNT_PRDT_CD": ACCOUNT_PRODUCT_CODE,

            # N: 기본 KRX 기준 조회
            "AFHR_FLPR_YN": "N",

            # 공식 샘플에도 포함되는 필드
            "OFL_YN": "",

            # 02: 종목별 조회
            "INQR_DVSN": "02",

            # 단가 구분
            "UNPR_DVSN": "01",

            # 펀드 결제분 포함 여부
            "FUND_STTL_ICLD_YN": "N",

            # 융자금액 자동상환 여부
            "FNCG_AMT_AUTO_RDPT_YN": "N",

            # 00: 전일 매매 포함
            "PRCS_DVSN": "00",

            # 연속조회용 값
            "CTX_AREA_FK100": ctx_area_fk100,
            "CTX_AREA_NK100": ctx_area_nk100,
        }

        request_headers = headers.copy()

        if tr_cont:
            request_headers["tr_cont"] = tr_cont

        try:
            response = requests.get(
                url,
                headers=request_headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

        except requests.Timeout as exc:
            raise requests.Timeout(
                "계좌 잔고 조회 요청 시간이 초과되었습니다."
            ) from exc

        except requests.ConnectionError as exc:
            raise requests.ConnectionError(
                "한국투자증권 잔고 조회 서버에 "
                "연결할 수 없습니다."
            ) from exc

        except requests.HTTPError as exc:
            raise requests.HTTPError(
                "계좌 잔고 조회 HTTP 오류: "
                f"{response.status_code} {response.text}"
            ) from exc

        try:
            result = response.json()
        except ValueError as exc:
            raise RuntimeError(
                "계좌 잔고 조회 응답을 JSON으로 "
                "변환할 수 없습니다."
            ) from exc

        if result.get("rt_cd") != "0":
            message_code = result.get("msg_cd", "UNKNOWN")
            message = result.get(
                "msg1",
                "알 수 없는 잔고 조회 오류",
            )

            raise RuntimeError(
                f"계좌 잔고 조회 실패 "
                f"[{message_code}]: {message}"
            )

        output1 = result.get("output1") or []
        output2 = result.get("output2") or []

        for item in output1:
            quantity = _to_int(item.get("hldg_qty"))

            if quantity == 0 and not include_zero_quantity:
                continue

            positions.append(
                {
                    "stock_code": str(
                        item.get("pdno", "")
                    ).strip(),
                    "stock_name": str(
                        item.get("prdt_name", "")
                    ).strip(),
                    "quantity": quantity,
                    "sellable_quantity": _to_int(
                        item.get("ord_psbl_qty")
                    ),
                    "avg_price": _to_float(
                        item.get("pchs_avg_pric")
                    ),
                    "purchase_amount": _to_int(
                        item.get("pchs_amt")
                    ),
                    "current_price": _to_int(
                        item.get("prpr")
                    ),
                    "evaluation_amount": _to_int(
                        item.get("evlu_amt")
                    ),
                    "profit_loss": _to_int(
                        item.get("evlu_pfls_amt")
                    ),
                    "profit_rate": _to_float(
                        item.get("evlu_pfls_rt")
                    ),
                    "today_buy_quantity": _to_int(
                        item.get("thdt_buyqty")
                    ),
                    "today_sell_quantity": _to_int(
                        item.get("thdt_sll_qty")
                    ),
                }
            )

        if output2:
            summary = output2[0]

            account_summary = {
                "cash": _to_int(
                    summary.get("dnca_tot_amt")
                ),
                "d1_cash": _to_int(
                    summary.get("nxdy_excc_amt")
                ),
                "d2_cash": _to_int(
                    summary.get("prvs_rcdl_excc_amt")
                ),
                "stock_evaluation_amount": _to_int(
                    summary.get("scts_evlu_amt")
                ),
                "total_evaluation_amount": _to_int(
                    summary.get("tot_evlu_amt")
                ),
                "total_profit_loss": _to_int(
                    summary.get("evlu_pfls_smtl_amt")
                ),
                "previous_buy_amount": _to_int(
                    summary.get("bfdy_buy_amt")
                ),
                "today_buy_amount": _to_int(
                    summary.get("thdt_buy_amt")
                ),
                "previous_sell_amount": _to_int(
                    summary.get("bfdy_sll_amt")
                ),
                "today_sell_amount": _to_int(
                    summary.get("thdt_sll_amt")
                ),
            }

        response_tr_cont = (
            response.headers.get("tr_cont")
            or response.headers.get("TR_CONT")
            or ""
        )

        ctx_area_fk100 = str(
            result.get("ctx_area_fk100")
            or result.get("CTX_AREA_FK100")
            or ""
        ).strip()

        ctx_area_nk100 = str(
            result.get("ctx_area_nk100")
            or result.get("CTX_AREA_NK100")
            or ""
        ).strip()

        if response_tr_cont not in {"M", "F"}:
            break

        if not ctx_area_fk100 and not ctx_area_nk100:
            break

        tr_cont = "N"

    return {
        **account_summary,
        "position_count": len(positions),
        "positions": positions,
    }

def inquire_daily_orders(
    start_date: str | None = None,
    end_date: str | None = None,
    order_no: str = "",
    stock_code: str = "",
    side: str = "ALL",
    executed_only: bool = False,
) -> dict[str, Any]:
    """
    한국투자증권 주식일별주문체결조회 API를 호출한다.

    Parameters
    ----------
    start_date
        조회 시작일. YYYYMMDD 형식.
        None이면 당일 날짜를 사용한다.

    end_date
        조회 종료일. YYYYMMDD 형식.
        None이면 당일 날짜를 사용한다.

    order_no
        특정 주문번호만 조회할 때 사용한다.
        전체 주문을 조회하려면 빈 문자열을 전달한다.

    stock_code
        특정 종목만 조회할 때 사용한다.
        전체 종목을 조회하려면 빈 문자열을 전달한다.

    side
        ALL, BUY, SELL 중 하나.

    executed_only
        True이면 체결 주문만 조회하고,
        False이면 미체결 주문까지 포함한다.

    Returns
    -------
    dict
        한국투자증권 API의 원본 JSON 응답.
    """
    today = datetime.now().strftime("%Y%m%d")

    start_date = start_date or today
    end_date = end_date or today

    side_code_map = {
        "ALL": "00",
        "SELL": "01",
        "BUY": "02",
    }

    normalized_side = side.upper()

    if normalized_side not in side_code_map:
        raise ValueError("side는 ALL, BUY, SELL 중 하나여야 합니다.")

    if len(start_date) != 8 or not start_date.isdigit():
        raise ValueError("start_date는 YYYYMMDD 형식이어야 합니다.")

    if len(end_date) != 8 or not end_date.isdigit():
        raise ValueError("end_date는 YYYYMMDD 형식이어야 합니다.")

    access_token = get_access_token()

    url = f"{BASE_URL}/uapi/domestic-stock/v1/trading/inquire-daily-ccld"

    # 실전투자 기준 TR ID.
    # 모의투자를 사용하는 경우 config에서 별도로 관리하는 것이 좋다.
    if IS_VIRTUAL:
        tr_id = "VTTC8001R"
    else:
        tr_id = "TTTC8001R"

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": tr_id,
        "custtype": "P",
    }

    params = {
        "CANO": ACCOUNT_NO,
        "ACNT_PRDT_CD": ACCOUNT_PRODUCT_CODE,
        "INQR_STRT_DT": start_date,
        "INQR_END_DT": end_date,
        "SLL_BUY_DVSN_CD": side_code_map[normalized_side],
        "INQR_DVSN": "00",
        "PDNO": stock_code,
        "CCLD_DVSN": "01" if executed_only else "00",
        "ORD_GNO_BRNO": "",
        "ODNO": order_no,
        "INQR_DVSN_3": "00",
        "INQR_DVSN_1": "",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=10,
        )
        response.raise_for_status()

    except requests.Timeout as exc:
        raise RuntimeError(
            "주문체결 조회 요청 시간이 초과되었습니다."
        ) from exc

    except requests.RequestException as exc:
        raise RuntimeError(
            f"주문체결 조회 API 요청에 실패했습니다: {exc}"
        ) from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "주문체결 조회 응답을 JSON으로 변환하지 못했습니다."
        ) from exc

    if result.get("rt_cd") != "0":
        message_code = result.get("msg_cd", "")
        message = result.get("msg1", "알 수 없는 API 오류")

        raise RuntimeError(
            f"주문체결 조회 실패: [{message_code}] {message}"
        )

    return result