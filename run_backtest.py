from backtesting import BacktestEngine
from indicator import (
    add_all_indicators,
    get_daily_price_df,
)
from strategies import (
    StrategyEngine,
    StrategyFactory,
)
from universe import STOCK_UNIVERSE


DATA_LIMIT = 1000

STRATEGY_NAMES = [
    "ma_cross",
    "rsi",
    "macd",
    "bollinger",
]


def main() -> None:
    strategies = (
        StrategyFactory.create_strategies(
            STRATEGY_NAMES
        )
    )

    strategy_engine = StrategyEngine(
        strategies=strategies,
        buy_threshold=0.2,
        sell_threshold=-0.2,
        buy_trend_filter_column="ma60",
        strategy_weights={
            "MA Cross": 0.40,
            "MACD": 0.30,
            "RSI": 0.15,
            "Bollinger Band": 0.15,
        },
    )

    engine = BacktestEngine(
        strategy_engine=strategy_engine,
        indicator_builder=add_all_indicators,
        initial_cash=100_000_000,
        minimum_data_length=120,
    )

    results = []

    for stock in STOCK_UNIVERSE:
        stock_code = stock["code"]
        stock_name = stock["name"]

        print()
        print(
            f"{stock_name}({stock_code}) "
            "백테스트 중..."
        )

        price_data = get_daily_price_df(
            stock_code,
            limit=DATA_LIMIT,
        )

        result = engine.run(
            stock_code,
            price_data,
        )

        results.append(
            {
                "stock_name": stock_name,
                "stock_code": stock_code,
                "total_return": (
                    result.metrics["total_return"]
                ),
                "annualized_return": (
                    result.metrics[
                        "annualized_return"
                    ]
                ),
                "buy_and_hold_return": (
                    result.metrics[
                        "buy_and_hold_return"
                    ]
                ),
                "excess_return": (
                    result.metrics[
                        "excess_return"
                    ]
                ),
                "max_drawdown": (
                    result.metrics[
                        "max_drawdown"
                    ]
                ),
                "sharpe_ratio": (
                    result.metrics[
                        "sharpe_ratio"
                    ]
                ),
                "completed_trade_count": (
                    result.metrics[
                        "completed_trade_count"
                    ]
                ),
                "win_rate": (
                    result.metrics["win_rate"]
                ),
            }
        )

    print()
    print("=" * 110)
    print("다종목 백테스트 결과")
    print("=" * 110)

    header = (
        f"{'종목':<12}"
        f"{'전략수익률':>12}"
        f"{'Buy&Hold':>12}"
        f"{'초과수익률':>12}"
        f"{'MDD':>10}"
        f"{'Sharpe':>10}"
        f"{'거래':>8}"
        f"{'승률':>10}"
    )
    print(header)
    print("-" * 110)

    for row in results:
        print(
            f"{row['stock_name']:<12}"
            f"{row['total_return'] * 100:>11.2f}%"
            f"{row['buy_and_hold_return'] * 100:>11.2f}%"
            f"{row['excess_return'] * 100:>11.2f}%"
            f"{row['max_drawdown'] * 100:>9.2f}%"
            f"{row['sharpe_ratio']:>10.4f}"
            f"{row['completed_trade_count']:>8}"
            f"{row['win_rate'] * 100:>9.2f}%"
        )


if __name__ == "__main__":
    main()