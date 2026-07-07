import pandas as pd

from strategies.ma_cross import MACrossStrategy
from strategies.signal import Signal
from indicator import get_daily_price_df, add_rolling_mean

# 테스트용
df = get_daily_price_df("005930", limit=120)
df = add_rolling_mean(df, "close", [5, 20], "ma")

strategy = MACrossStrategy()
signal = strategy.generate_signal(df)
print(signal)
print(signal.value)

if signal == Signal.BUY:
    print("매수 신호 발생")
elif signal == Signal.SELL:
    print("매도 신호 발생")
else:
    print("관망")