import pandas as pd

from indicator import (
    add_all_indicators,
    add_bollinger_bands,
    add_macd,
    add_rolling_mean,
    add_rsi,
)


def create_test_dataframe() -> pd.DataFrame:
    """
    지표 계산 테스트에 사용할 가상 일봉 데이터를 생성한다.
    """
    close_prices = list(range(100, 170))

    return pd.DataFrame({
        "stock_code": ["005930"] * len(close_prices),
        "date": pd.date_range(
            start="2026-01-01",
            periods=len(close_prices),
            freq="D",
        ).strftime("%Y%m%d"),
        "open": [price - 1 for price in close_prices],
        "high": [price + 2 for price in close_prices],
        "low": [price - 2 for price in close_prices],
        "close": close_prices,
        "volume": [
            1_000_000 + i * 10_000
            for i in range(len(close_prices))
        ],
    })


def test_rolling_mean() -> None:
    print("\n1. 이동평균 테스트")

    df = create_test_dataframe()

    result = add_rolling_mean(
        df=df,
        column="close",
        windows=[5, 20],
        prefix="ma",
    )

    print(
        result[
            ["date", "close", "ma5", "ma20"]
        ].tail()
    )

    assert "ma5" in result.columns
    assert "ma20" in result.columns

    # 첫 번째 5일 이동평균은 100~104의 평균인 102
    assert pd.isna(result.loc[3, "ma5"])
    assert result.loc[4, "ma5"] == 102.0

    # 원본 DataFrame에는 지표 컬럼이 생기지 않아야 한다.
    assert "ma5" not in df.columns

    print("이동평균 테스트 통과")


def test_rsi() -> None:
    print("\n2. RSI 테스트")

    df = create_test_dataframe()

    result = add_rsi(
        df=df,
        period=14,
    )

    print(
        result[
            ["date", "close", "rsi14"]
        ].tail()
    )

    assert "rsi14" in result.columns

    # 계속 상승하는 데이터이므로 충분한 기간 이후 RSI는 100
    assert pd.isna(result.loc[13, "rsi14"])
    assert result.iloc[-1]["rsi14"] == 100.0

    print("RSI 테스트 통과")


def test_flat_price_rsi() -> None:
    print("\n3. 가격 변동이 없는 경우 RSI 테스트")

    df = create_test_dataframe()
    df["close"] = 100

    result = add_rsi(
        df=df,
        period=14,
    )

    print(result[["date", "close", "rsi14"]].tail())

    # 상승도 하락도 없으므로 RSI는 50
    assert result.iloc[-1]["rsi14"] == 50.0

    print("고정 가격 RSI 테스트 통과")


def test_macd() -> None:
    print("\n4. MACD 테스트")

    df = create_test_dataframe()

    result = add_macd(
        df=df,
        short_window=12,
        long_window=26,
        signal_window=9,
    )

    print(
        result[
            [
                "date",
                "close",
                "macd",
                "macd_signal",
                "macd_hist",
            ]
        ].tail()
    )

    assert "macd" in result.columns
    assert "macd_signal" in result.columns
    assert "macd_hist" in result.columns

    # 장기 EMA 기간이 충족되기 전에는 MACD가 NaN
    assert pd.isna(result.loc[24, "macd"])

    # 충분한 데이터가 있으면 값이 계산되어야 한다.
    assert pd.notna(result.iloc[-1]["macd"])
    assert pd.notna(result.iloc[-1]["macd_signal"])
    assert pd.notna(result.iloc[-1]["macd_hist"])

    # 계속 상승하는 데이터이므로 MACD는 양수여야 한다.
    assert result.iloc[-1]["macd"] > 0

    print("MACD 테스트 통과")


def test_bollinger_bands() -> None:
    print("\n5. 볼린저밴드 테스트")

    df = create_test_dataframe()

    result = add_bollinger_bands(
        df=df,
        window=20,
        num_std=2.0,
    )

    print(
        result[
            [
                "date",
                "close",
                "bb_mid20",
                "bb_upper20",
                "bb_lower20",
            ]
        ].tail()
    )

    assert "bb_mid20" in result.columns
    assert "bb_upper20" in result.columns
    assert "bb_lower20" in result.columns

    assert pd.isna(result.loc[18, "bb_mid20"])
    assert pd.notna(result.loc[19, "bb_mid20"])

    latest = result.iloc[-1]

    assert latest["bb_upper20"] > latest["bb_mid20"]
    assert latest["bb_mid20"] > latest["bb_lower20"]

    print("볼린저밴드 테스트 통과")


def test_all_indicators() -> None:
    print("\n6. 전체 지표 일괄 생성 테스트")

    df = create_test_dataframe()

    result = add_all_indicators(df)

    expected_columns = {
        "ma5",
        "ma20",
        "ma60",
        "vol_ma5",
        "vol_ma20",
        "rsi14",
        "macd",
        "macd_signal",
        "macd_hist",
        "bb_mid20",
        "bb_upper20",
        "bb_lower20",
    }

    missing_columns = expected_columns - set(result.columns)

    assert not missing_columns, (
        f"생성되지 않은 컬럼이 있습니다: {missing_columns}"
    )

    print(
        result[
            [
                "date",
                "close",
                "ma5",
                "ma20",
                "ma60",
                "rsi14",
                "macd",
                "macd_signal",
                "bb_upper20",
                "bb_lower20",
            ]
        ].tail()
    )

    latest = result.iloc[-1]

    for column in expected_columns:
        assert pd.notna(latest[column]), (
            f"마지막 행의 {column} 값이 NaN입니다."
        )

    # 원본 DataFrame은 변경되지 않아야 한다.
    for column in expected_columns:
        assert column not in df.columns

    print("전체 지표 생성 테스트 통과")


def test_invalid_inputs() -> None:
    print("\n7. 잘못된 입력 예외 처리 테스트")

    df = create_test_dataframe()

    try:
        add_rolling_mean(
            df=df,
            column="not_existing_column",
            windows=[5],
            prefix="ma",
        )
        raise AssertionError(
            "존재하지 않는 컬럼인데 오류가 발생하지 않았습니다."
        )

    except KeyError as error:
        print(f"컬럼 검증 정상: {error}")

    try:
        add_rsi(
            df=df,
            period=0,
        )
        raise AssertionError(
            "period=0인데 오류가 발생하지 않았습니다."
        )

    except ValueError as error:
        print(f"RSI 기간 검증 정상: {error}")

    try:
        add_macd(
            df=df,
            short_window=30,
            long_window=20,
        )
        raise AssertionError(
            "단기 기간이 더 긴데 오류가 발생하지 않았습니다."
        )

    except ValueError as error:
        print(f"MACD 기간 검증 정상: {error}")

    try:
        add_bollinger_bands(
            df=df,
            window=20,
            num_std=0,
        )
        raise AssertionError(
            "num_std=0인데 오류가 발생하지 않았습니다."
        )

    except ValueError as error:
        print(f"볼린저밴드 입력 검증 정상: {error}")

    print("예외 처리 테스트 통과")


def run_all_tests() -> None:
    test_rolling_mean()
    test_rsi()
    test_flat_price_rsi()
    test_macd()
    test_bollinger_bands()
    test_all_indicators()
    test_invalid_inputs()

    print("\n모든 indicator.py 테스트 통과")


if __name__ == "__main__":
    run_all_tests()