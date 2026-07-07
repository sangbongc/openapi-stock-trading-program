import pandas as pd

from database import fetch_daily_prices_by_stock

#데이터프레임 생성
def get_daily_price_df(stock_code: str, limit: int = 120) -> pd.DataFrame:
    rows = fetch_daily_prices_by_stock(stock_code, limit=limit)

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df = df.sort_values("date").reset_index(drop=True)

    return df

#이동평균 컬럼 생성(가격&거래량)
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
    df : DataFrame
        원본 데이터프레임
    column : str
        이동평균을 계산할 컬럼명
        예) "close", "volume"
    windows : list[int]
        이동평균 기간
        예) [5, 20, 60]
    prefix : str
        생성될 컬럼명 접두사
        예) "ma", "vol_ma"
    """

    df = df.copy()

    for window in windows:
        df[f"{prefix}{window}"] = (
            df[column]
            .rolling(window=window)
            .mean()
        )

    return df
#rsi 칼럼 생성
def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    df = df.copy()

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss

    df[f"rsi{period}"] = 100 - (100 / (1 + rs))

    return df
#macd 칼럼 생성
def add_macd(
    df: pd.DataFrame,
    short_window: int = 12,
    long_window: int = 26,
    signal_window: int = 9,
) -> pd.DataFrame:
    df = df.copy()

    ema_short = df["close"].ewm(span=short_window, adjust=False).mean()
    ema_long = df["close"].ewm(span=long_window, adjust=False).mean()

    df["macd"] = ema_short - ema_long
    df["macd_signal"] = df["macd"].ewm(span=signal_window, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    return df
#볼린저밴드
def add_bollinger_bands(
    df: pd.DataFrame,
    window: int = 20,
    num_std: int = 2,
) -> pd.DataFrame:
    df = df.copy()

    middle = df["close"].rolling(window=window).mean()
    std = df["close"].rolling(window=window).std()

    df[f"bb_mid{window}"] = middle
    df[f"bb_upper{window}"] = middle + (num_std * std)
    df[f"bb_lower{window}"] = middle - (num_std * std)

    return df