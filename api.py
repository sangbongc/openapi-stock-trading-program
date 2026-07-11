from json import JSONDecodeError
from pathlib import Path
from typing import Any
import json
import requests
from requests import Response, Session
from requests.exceptions import RequestException
import logging
from config import APP_KEY, APP_SECRET, BASE_URL, TOKEN_PATH
from datetime import datetime, timedelta
import os

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