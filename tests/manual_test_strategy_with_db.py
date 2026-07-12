from indicator import (
    add_bollinger_bands,
    add_macd,
    add_rolling_mean,
    add_rsi,
    get_daily_price_df,
)
from strategies.strategy_engine import StrategyEngine
from strategies.strategy_factory import StrategyFactory


STOCKS = [
    ("005930", "삼성전자"),
    ("000660", "SK하이닉스"),
    ("035420", "NAVER"),
    ("035720", "카카오"),
    ("005380", "현대차"),
]


def prepare_indicator_data(stock_code: str):
    """
    trading.db에서 일봉 데이터를 불러오고
    각 전략에 필요한 기술적 지표를 계산한다.
    """
    df = get_daily_price_df(
        stock_code=stock_code,
        limit=120,
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


def main():
    factory = StrategyFactory()

    strategies = factory.create_strategies(
        [
            "ma_cross",
            "rsi",
            "macd",
            "bollinger",
        ]
    )

    engine = StrategyEngine(
    strategies=strategies,
    buy_threshold=0.2,
    sell_threshold=-0.2,
)

    for stock_code, stock_name in STOCKS:
        print("=" * 70)
        print(f"{stock_name} ({stock_code})")
        print("=" * 70)

        df = prepare_indicator_data(stock_code)

        if df.empty:
            print("DB에 일봉 데이터가 없습니다.")
            print()
            continue

        print(f"데이터 개수: {len(df)}")
        print(f"시작일: {df.iloc[0]['date']}")
        print(f"종료일: {df.iloc[-1]['date']}")
        print()

        columns_to_show = [
            "date",
            "close",
            "ma5",
            "ma20",
            "rsi",
            "macd",
            "macd_signal",
            "bb_upper",
            "bb_lower",
        ]

        existing_columns = [
            column
            for column in columns_to_show
            if column in df.columns
        ]

        print("[최근 지표]")
        print(
            df[existing_columns]
            .tail(3)
            .to_string(index=False)
        )
        print()

        print("[개별 전략 결과]")

        for strategy in strategies:
            result = strategy.generate_signal(df)

            print(f"전략: {strategy.name}")
            print(f"신호: {result.signal.value}")
            print(f"신뢰도: {result.confidence:.4f}")
            print(f"사유: {result.reason}")
            print("-" * 40)

        engine_result = engine.run(df)

        print()
        print("[StrategyEngine 최종 결과]")
        print(f"최종 신호: {engine_result.final_signal.value}")
        print(
    f"종합 점수: "
    f"{engine_result.confidence_score:.4f}"
)
        print(
    f"최종 신뢰도: "
    f"{engine_result.final_confidence:.4f}"
)
        print()


if __name__ == "__main__":
    main()