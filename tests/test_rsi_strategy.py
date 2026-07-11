import pandas as pd

from strategies.rsi_strategy import RSIStrategy
from strategies.signal import Signal


strategy = RSIStrategy(
    oversold=30,
    overbought=70,
)


# BUY 테스트
buy_df = pd.DataFrame({
    "rsi": [45.0, 35.0, 25.0]
})

buy_result = strategy.generate_signal(buy_df)

print("=== BUY 테스트 ===")
print(buy_result)
print(buy_result.signal)
print(buy_result.confidence)
print(buy_result.reason)

assert buy_result.signal == Signal.BUY


# SELL 테스트
sell_df = pd.DataFrame({
    "rsi": [55.0, 65.0, 80.0]
})

sell_result = strategy.generate_signal(sell_df)

print("\n=== SELL 테스트 ===")
print(sell_result)
print(sell_result.signal)
print(sell_result.confidence)
print(sell_result.reason)

assert sell_result.signal == Signal.SELL


# HOLD 테스트
hold_df = pd.DataFrame({
    "rsi": [45.0, 50.0, 55.0]
})

hold_result = strategy.generate_signal(hold_df)

print("\n=== HOLD 테스트 ===")
print(hold_result)
print(hold_result.signal)
print(hold_result.confidence)
print(hold_result.reason)

assert hold_result.signal == Signal.HOLD


print("\n모든 RSI 전략 테스트를 통과했습니다.")