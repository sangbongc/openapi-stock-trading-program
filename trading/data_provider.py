import pandas as pd

from indicator import (
    add_bollinger_bands,
    add_macd,
    add_rolling_mean,
    add_rsi,
    get_daily_price_df,
)


def prepare_strategy_data(
    stock_code: str,
    limit: int = 250,
) -> pd.DataFrame:
    """
    DB에서 일봉 데이터를 조회하고
    전략 실행에 필요한 지표를 계산한다.
    """
    df = get_daily_price_df(
        stock_code=stock_code,
        limit=limit,
    )

    if df.empty:
        return df

    df = add_rolling_mean(
        df=df,
        column="close",
        windows=[5, 20],
        prefix="ma",
    )

    df = add_rsi(df)
    df = add_macd(df)
    df = add_bollinger_bands(df)

    return df