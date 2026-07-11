import pandas as pd

from strategies.bollinger_strategy import BollingerBandStrategy
from strategies.signal import Signal


strategy = BollingerBandStrategy()


# BUY 테스트
buy_df = pd.DataFrame({
    "close": [100.0, 85.0],
    "bb_upper20": [110.0, 110.0],
    "bb_mid20": [100.0, 100.0],
    "bb_lower20": [90.0, 90.0],
})

buy_result = strategy.generate_signal(buy_df)

print("===== BUY TEST =====")
print(buy_result)
print(buy_result.signal)
print(buy_result.confidence)
print(buy_result.reason)

assert buy_result.signal == Signal.BUY


# SELL 테스트
sell_df = pd.DataFrame({
    "close": [100.0, 115.0],
    "bb_upper20": [110.0, 110.0],
    "bb_mid20": [100.0, 100.0],
    "bb_lower20": [90.0, 90.0],
})

sell_result = strategy.generate_signal(sell_df)

print("\n===== SELL TEST =====")
print(sell_result)
print(sell_result.signal)
print(sell_result.confidence)
print(sell_result.reason)

assert sell_result.signal == Signal.SELL


# HOLD 테스트
hold_df = pd.DataFrame({
    "close": [100.0, 102.0],
    "bb_upper20": [110.0, 110.0],
    "bb_mid20": [100.0, 100.0],
    "bb_lower20": [90.0, 90.0],
})

hold_result = strategy.generate_signal(hold_df)

print("\n===== HOLD TEST =====")
print(hold_result)
print(hold_result.signal)
print(hold_result.confidence)
print(hold_result.reason)

assert hold_result.signal == Signal.HOLD


print("\n모든 볼린저 밴드 전략 테스트를 통과했습니다.")