import pandas as pd

from strategies.macd_strategy import MACDStrategy
from strategies.signal import Signal


strategy = MACDStrategy()


# ----------------------------
# BUY 테스트
# ----------------------------
buy_df = pd.DataFrame({
    "macd": [-1.0, 0.5],
    "macd_signal": [-0.5, 0.2]
})

buy_result = strategy.generate_signal(buy_df)

print("===== BUY TEST =====")
print(buy_result)

assert buy_result.signal == Signal.BUY


# ----------------------------
# SELL 테스트
# ----------------------------
sell_df = pd.DataFrame({
    "macd": [0.8, -0.4],
    "macd_signal": [0.5, -0.2]
})

sell_result = strategy.generate_signal(sell_df)

print("\n===== SELL TEST =====")
print(sell_result)

assert sell_result.signal == Signal.SELL


# ----------------------------
# HOLD 테스트
# ----------------------------
hold_df = pd.DataFrame({
    "macd": [0.5, 0.8],
    "macd_signal": [0.2, 0.5]
})

hold_result = strategy.generate_signal(hold_df)

print("\n===== HOLD TEST =====")
print(hold_result)

assert hold_result.signal == Signal.HOLD


print("\n모든 MACD 전략 테스트를 통과했습니다.")