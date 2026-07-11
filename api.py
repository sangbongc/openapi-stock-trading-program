import json
import os
from datetime import datetime, timedelta
from json import JSONDecodeError
from typing import Any

import requests
from requests import Response
from requests.exceptions import RequestException

from config import APP_KEY, APP_SECRET, BASE_URL, TOKEN_PATH


REQUEST_TIMEOUT = 10

# 서버가 알려준 만료 시각보다 조금 일찍 토큰을 교체한다.
TOKEN_EXPIRY_BUFFER_MINUTES = 5


class KISAPIError(Exception):
    """한국투자증권 API 호출 과정에서 발생하는 오류."""

    pass


def validate_api_config() -> None:
    """
    API 호출에 필요한 설정값이 존재하는지 확인한다.
    """
    missing_values = []

    if not APP_KEY:
        missing_values.append("KIS_APP_KEY")

    if not APP_SECRET:
        missing_values.append("KIS_APP_SECRET")

    if not BASE_URL:
        missing_values.append("KIS_BASE_URL")

    if missing_values:
        raise ValueError(
            "필수 환경변수가 설정되지 않았습니다: "
            + ", ".join(missing_values)
        )


def build_headers(
    token: str,
    tr_id: str,
) -> dict[str, str]:
    """
    일반적인 한국투자증권 API 요청에 사용할 헤더를 생성한다.
    """
    return {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": tr_id,
    }


def save_token(
    access_token: str,
    token_type: str,
    expires_at: datetime,
) -> None:
    """
    토큰과 서버가 반환한 만료 시각을 JSON 파일에 저장한다.

    Args:
        access_token:
            서버가 발급한 접근토큰

        token_type:
            토큰 유형. 일반적으로 Bearer

        expires_at:
            서버 응답의 access_token_token_expired를
            datetime으로 변환한 값
    """
    token_directory = os.path.dirname(TOKEN_PATH)

    if token_directory:
        os.makedirs(
            token_directory,
            exist_ok=True,
        )

    token_data = {
        "access_token": access_token,
        "token_type": token_type,
        "expires_at": expires_at.isoformat(),
    }

    with open(
        TOKEN_PATH,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            token_data,
            file,
            ensure_ascii=False,
            indent=4,
        )


def delete_cached_token() -> None:
    """
    로컬 토큰 캐시 파일을 삭제한다.
    """
    if not os.path.exists(TOKEN_PATH):
        return

    try:
        os.remove(TOKEN_PATH)

    except OSError as error:
        print(
            f"토큰 캐시 파일을 삭제하지 못했습니다: {error}"
        )


def load_token() -> str | None:
    """
    저장된 접근토큰을 읽는다.

    서버가 알려준 만료 시각보다 5분 이상 남은 경우에만
    저장된 토큰을 반환한다.

    Returns:
        사용할 수 있는 접근토큰 또는 None
    """
    if not os.path.exists(TOKEN_PATH):
        return None

    try:
        with open(
            TOKEN_PATH,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        access_token = data.get("access_token")
        expires_at_text = data.get("expires_at")

        if not access_token or not expires_at_text:
            print("토큰 캐시에 필요한 정보가 없습니다.")
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
        print(f"토큰 캐시를 읽지 못했습니다: {error}")
        delete_cached_token()
        return None

    refresh_threshold = expires_at - timedelta(
        minutes=TOKEN_EXPIRY_BUFFER_MINUTES
    )

    if datetime.now() >= refresh_threshold:
        print(
            "저장된 토큰의 만료가 임박했거나 "
            "이미 만료되었습니다."
        )
        delete_cached_token()
        return None

    return access_token


def parse_json_response(
    response: Response,
) -> dict[str, Any]:
    """
    서버 응답을 JSON 딕셔너리로 변환한다.
    """
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

    토큰 발급 응답에는 rt_cd가 없으므로,
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
            f"API 요청 실패 "
            f"[{message_code}]: {message}"
        )


def _get_safe_response_text(
    response: Response | None,
    max_length: int = 500,
) -> str:
    """
    HTTP 오류 응답을 지나치게 길지 않은 문자열로 변환한다.
    """
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

    Returns:
        토큰 만료 시각
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

    참고:
        한국투자증권은 신규 토큰 발급 후 6시간 이내에
        발급 API를 다시 호출하면 기존 토큰을 반환한다.
        따라서 force_refresh=True라고 해도 서버가 반드시
        새로운 문자열의 토큰을 발급하는 것은 아니다.
    """
    validate_api_config()

    if not force_refresh:
        cached_token = load_token()

        if cached_token:
            print("저장된 토큰 사용")
            return cached_token

    url = f"{BASE_URL}/oauth2/tokenP"

    headers = {
        "content-type": "application/json; charset=utf-8"
    }

    body = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
    }

    try:
        response = requests.post(
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

    if token_type != "Bearer":
        raise KISAPIError(
            "예상하지 못한 토큰 유형을 받았습니다: "
            f"{token_type}"
        )

    expires_at = _parse_token_expiration(data)

    save_token(
        access_token=access_token,
        token_type=token_type,
        expires_at=expires_at,
    )

    print(
        "접근토큰 발급 완료 "
        f"(만료 시각: {expires_at:%Y-%m-%d %H:%M:%S})"
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
) -> dict[str, Any]:
    """
    한국투자증권 API에 공통 HTTP 요청을 보낸다.
    """
    validate_api_config()

    url = f"{BASE_URL}{endpoint}"

    try:
        response = requests.request(
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
            print(
                "토큰 인증에 실패하여 "
                "토큰 발급 API를 한 번 다시 호출합니다."
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
    """
    특정 국내주식 종목의 현재가 정보를 조회한다.
    """
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
    """
    특정 국내주식 종목의 기간별 일봉 데이터를 조회한다.
    """
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
    """
    국내주식 종목 코드가 6자리 숫자 문자열인지 검사한다.
    """
    if not isinstance(stock_code, str):
        raise ValueError(
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
    """
    날짜가 YYYYMMDD 형식인지 검사한다.
    """
    if not isinstance(date_text, str):
        raise ValueError(
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
    """
    조회 시작일과 종료일의 형식 및 순서를 검사한다.
    """
    start_datetime = _validate_date(start_date)
    end_datetime = _validate_date(end_date)

    if start_datetime > end_datetime:
        raise ValueError(
            "조회 시작일은 종료일보다 늦을 수 없습니다."
        )