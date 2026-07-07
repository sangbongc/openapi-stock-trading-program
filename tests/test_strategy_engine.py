import pandas as pd

from strategies import (
    StrategyEngine,
    MACrossStrategy,
    RSIStrategy,
    BollingerBandStrategy,
    MACDStrategy,
)
from indicator import ( get_daily_price_df, add_rolling_mean,  add_bollinger_bands, add_macd, add_rsi, )
from tests.test_strategy_factory import create_strategies

df = get_daily_price_df("005930", limit=120)

# Indicator 계산
df = add_rolling_mean(
    df,
    column="close",
    windows=[5, 20],
    prefix="ma"
)
df = add_rsi(df)
df = add_macd(df)
df = add_bollinger_bands(df)

engine = StrategyEngine(create_strategies([
    "ma_cross",
    "rsi",
    "macd"
]))

result = engine.run(df)



print("===== Strategy Analysis =====")

for strategy_name, signal in result["strategy_results"].items():
    print(f"{strategy_name:20} : {signal.value}")

print("-" * 35)
print(f"{'Final Decision':20} : {result['final_signal'].value}")