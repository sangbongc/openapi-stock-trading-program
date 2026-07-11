import pandas as pd

from database import fetch_daily_prices_by_stock


REQUIRED_PRICE_COLUMNS = {
    "stock_code",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
}

NUMERIC_PRICE_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
]


def _validate_dataframe_columns(
    df: pd.DataFrame,
    required_columns: set[str],
) -> None:
    """
    데이터프레임에 필요한 컬럼이 존재하는지 확인한다.

    Parameters
    ----------
    df : pd.DataFrame
        검사할 데이터프레임

    required_columns : set[str]
        반드시 존재해야 하는 컬럼명 집합

    Raises
    ------
    ValueError
        데이터프레임이 비어 있는 경우

    KeyError
        필요한 컬럼이 없는 경우
    """
    if df.empty:
        raise ValueError("지표를 계산할 데이터가 없습니다.")

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise KeyError(
            f"필수 컬럼이 없습니다: {sorted(missing_columns)}"
        )


def _validate_positive_integer(
    value: int,
    parameter_name: str,
) -> None:
    """
    입력값이 1 이상의 정수인지 확인한다.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(
            f"{parameter_name}은 정수여야 합니다."
        )

    if value <= 0:
        raise ValueError(
            f"{parameter_name}은 1 이상의 정수여야 합니다."
        )


# 데이터프레임 생성
def get_daily_price_df(
    stock_code: str,
    limit: int = 120,
) -> pd.DataFrame:
    """
    DB에서 특정 종목의 일봉 데이터를 조회하여 DataFrame으로 반환한다.

    DB 조회 결과는 최근 날짜부터 내림차순으로 반환되므로,
    지표 계산을 위해 날짜 오름차순으로 다시 정렬한다.

    Parameters
    ----------
    stock_code : str
        조회할 종목 코드

    limit : int, default=120
        조회할 최대 일봉 데이터 개수

    Returns
    -------
    pd.DataFrame
        날짜 오름차순으로 정렬된 일봉 데이터프레임

        저장된 데이터가 없으면 빈 데이터프레임을 반환한다.
    """
    if not stock_code or not stock_code.strip():
        raise ValueError("stock_code는 비어 있을 수 없습니다.")

    _validate_positive_integer(limit, "limit")

    rows = fetch_daily_prices_by_stock(
        stock_code=stock_code,
        limit=limit,
    )

    if not rows:
        return pd.DataFrame(columns=sorted(REQUIRED_PRICE_COLUMNS))

    df = pd.DataFrame(rows)

    _validate_dataframe_columns(
        df,
        REQUIRED_PRICE_COLUMNS,
    )

    # 날짜를 문자열로 통일한다.
    df["date"] = df["date"].astype(str)

    # 가격과 거래량 컬럼을 숫자형으로 변환한다.
    for column in NUMERIC_PRICE_COLUMNS:
        df[column] = pd.to_numeric(
            df[column],
            errors="raise",
        )

    df = (
        df.sort_values("date")
        .reset_index(drop=True)
    )

    return df


# 이동평균 컬럼 생성
def add_rolling_mean(
    df: pd.DataFrame,
    column: str,
    windows: list[int],
    prefix: str,
) -> pd.DataFrame:
    """
    특정 컬럼에 대해 이동평균 컬럼을 추가한다.

    Parameters
    ----------
    df : pd.DataFrame
        원본 데이터프레임

    column : str
        이동평균을 계산할 컬럼명
        예: "close", "volume"

    windows : list[int]
        이동평균 기간
        예: [5, 20, 60]

    prefix : str
        생성될 컬럼명 접두사
        예: "ma", "vol_ma"

    Returns
    -------
    pd.DataFrame
        이동평균 컬럼이 추가된 새로운 데이터프레임
    """
    _validate_dataframe_columns(df, {column})

    if not windows:
        raise ValueError("windows에는 하나 이상의 기간이 필요합니다.")

    if not prefix or not prefix.strip():
        raise ValueError("prefix는 비어 있을 수 없습니다.")

    if len(windows) != len(set(windows)):
        raise ValueError("windows에 중복된 기간이 있습니다.")

    for window in windows:
        _validate_positive_integer(window, "window")

    result = df.copy()

    numeric_series = pd.to_numeric(
        result[column],
        errors="raise",
    )

    for window in windows:
        result[f"{prefix}{window}"] = (
            numeric_series
            .rolling(
                window=window,
                min_periods=window,
            )
            .mean()
        )

    return result


# RSI 컬럼 생성
def add_rsi(
    df: pd.DataFrame,
    period: int = 14,
) -> pd.DataFrame:
    """
    종가를 기준으로 RSI 지표를 계산한다.

    Parameters
    ----------
    df : pd.DataFrame
        close 컬럼을 포함한 데이터프레임

    period : int, default=14
        RSI 계산 기간

    Returns
    -------
    pd.DataFrame
        RSI 컬럼이 추가된 새로운 데이터프레임
    """
    _validate_dataframe_columns(df, {"close"})
    _validate_positive_integer(period, "period")

    result = df.copy()

    close = pd.to_numeric(
        result["close"],
        errors="raise",
    )

    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(
        window=period,
        min_periods=period,
    ).mean()

    avg_loss = loss.rolling(
        window=period,
        min_periods=period,
    ).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    # 상승만 존재하여 평균 손실이 0인 경우 RSI를 100으로 처리
    rsi = rsi.mask(
        (avg_loss == 0) & (avg_gain > 0),
        100.0,
    )

    # 가격 변화가 전혀 없는 경우 중립값인 50으로 처리
    rsi = rsi.mask(
        (avg_loss == 0) & (avg_gain == 0),
        50.0,
    )

    result[f"rsi{period}"] = rsi

    return result


# MACD 컬럼 생성
def add_macd(
    df: pd.DataFrame,
    short_window: int = 12,
    long_window: int = 26,
    signal_window: int = 9,
) -> pd.DataFrame:
    """
    종가를 기준으로 MACD 지표를 계산한다.

    Parameters
    ----------
    df : pd.DataFrame
        close 컬럼을 포함한 데이터프레임

    short_window : int, default=12
        단기 지수이동평균 기간

    long_window : int, default=26
        장기 지수이동평균 기간

    signal_window : int, default=9
        MACD 시그널 지수이동평균 기간

    Returns
    -------
    pd.DataFrame
        macd, macd_signal, macd_hist 컬럼이 추가된 데이터프레임
    """
    _validate_dataframe_columns(df, {"close"})

    _validate_positive_integer(
        short_window,
        "short_window",
    )
    _validate_positive_integer(
        long_window,
        "long_window",
    )
    _validate_positive_integer(
        signal_window,
        "signal_window",
    )

    if short_window >= long_window:
        raise ValueError(
            "short_window는 long_window보다 작아야 합니다."
        )

    result = df.copy()

    close = pd.to_numeric(
        result["close"],
        errors="raise",
    )

    ema_short = close.ewm(
        span=short_window,
        adjust=False,
        min_periods=short_window,
    ).mean()

    ema_long = close.ewm(
        span=long_window,
        adjust=False,
        min_periods=long_window,
    ).mean()

    result["macd"] = ema_short - ema_long

    result["macd_signal"] = result["macd"].ewm(
        span=signal_window,
        adjust=False,
        min_periods=signal_window,
    ).mean()

    result["macd_hist"] = (
        result["macd"]
        - result["macd_signal"]
    )

    return result


# 볼린저밴드 컬럼 생성
def add_bollinger_bands(
    df: pd.DataFrame,
    window: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    """
    종가를 기준으로 볼린저밴드를 계산한다.

    Parameters
    ----------
    df : pd.DataFrame
        close 컬럼을 포함한 데이터프레임

    window : int, default=20
        이동평균과 표준편차 계산 기간

    num_std : float, default=2.0
        상단·하단 밴드에 적용할 표준편차 배수

    Returns
    -------
    pd.DataFrame
        볼린저밴드 중앙선, 상단선, 하단선이 추가된 데이터프레임
    """
    _validate_dataframe_columns(df, {"close"})
    _validate_positive_integer(window, "window")

    if not isinstance(num_std, (int, float)):
        raise TypeError("num_std는 숫자여야 합니다.")

    if num_std <= 0:
        raise ValueError("num_std는 0보다 커야 합니다.")

    result = df.copy()

    close = pd.to_numeric(
        result["close"],
        errors="raise",
    )

    middle = close.rolling(
        window=window,
        min_periods=window,
    ).mean()

    std = close.rolling(
        window=window,
        min_periods=window,
    ).std()

    result[f"bb_mid{window}"] = middle
    result[f"bb_upper{window}"] = (
        middle + num_std * std
    )
    result[f"bb_lower{window}"] = (
        middle - num_std * std
    )

    return result


def add_all_indicators(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    전략 엔진에서 사용하는 주요 기술적 지표를 한 번에 추가한다.

    추가되는 지표
    ------------
    - 5일, 20일, 60일 종가 이동평균
    - 5일, 20일 거래량 이동평균
    - RSI 14
    - MACD 12, 26, 9
    - 볼린저밴드 20일, 표준편차 2배

    Returns
    -------
    pd.DataFrame
        모든 기술적 지표가 추가된 데이터프레임
    """
    result = add_rolling_mean(
        df=df,
        column="close",
        windows=[5, 20, 60],
        prefix="ma",
    )

    result = add_rolling_mean(
        df=result,
        column="volume",
        windows=[5, 20],
        prefix="vol_ma",
    )

    result = add_rsi(
        df=result,
        period=14,
    )

    result = add_macd(
        df=result,
        short_window=12,
        long_window=26,
        signal_window=9,
    )

    result = add_bollinger_bands(
        df=result,
        window=20,
        num_std=2.0,
    )

    return result