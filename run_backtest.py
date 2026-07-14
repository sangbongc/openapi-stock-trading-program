from backtesting import BacktestEngine
from indicator import add_all_indicators, get_daily_price_df
from strategies import StrategyEngine, StrategyFactory

STOCK_CODE = "005930"
DATA_LIMIT = 1000
STRATEGY_NAMES = ["ma_cross", "rsi", "macd", "bollinger"]


def main() -> None:
    price_data = get_daily_price_df(STOCK_CODE, limit=DATA_LIMIT)
    strategies = StrategyFactory.create_strategies(STRATEGY_NAMES)
    strategy_engine = StrategyEngine(
        strategies=strategies,
        buy_threshold=0.2,
        sell_threshold=-0.2,
    )
    engine = BacktestEngine(
        strategy_engine=strategy_engine,
        indicator_builder=add_all_indicators,
        initial_cash=100_000_000,
        minimum_data_length=120,
    )
    result = engine.run(STOCK_CODE, price_data)

    print("=" * 50)
    print(f"백테스트 결과: {result.stock_code}")
    print("=" * 50)
    print(f"초기 자금: {result.initial_cash:,.0f}원")
    print(f"최종 자산: {result.final_equity:,.0f}원")
    print(f"총수익률: {result.metrics['total_return'] * 100:.2f}%")
    print(f"연환산 수익률: {result.metrics['annualized_return'] * 100:.2f}%")
    print(f"최대 낙폭(MDD): {result.metrics['max_drawdown'] * 100:.2f}%")
    print(f"샤프지수: {result.metrics['sharpe_ratio']:.4f}")
    print(f"완료 거래 수: {result.metrics['completed_trade_count']}회")
    print(f"승률: {result.metrics['win_rate'] * 100:.2f}%")
    print(
    "Buy & Hold 수익률: "
    f"{result.metrics['buy_and_hold_return'] * 100:.2f}%"
)

    print(
    "초과수익률: "
    f"{result.metrics['excess_return'] * 100:.2f}%"
)

    print("\n[체결 내역]")
    for trade in result.trades:
        print(
            f"{trade.date} | {trade.side} | {trade.quantity}주 | "
            f"{trade.price:,.2f}원 | 수수료 {trade.fee:,.2f}원"
        )


if __name__ == "__main__":
    main()
