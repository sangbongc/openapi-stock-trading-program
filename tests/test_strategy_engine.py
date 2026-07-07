import pandas as pd

from strategies.strategy_engine import StrategyEngine
from strategies.signal import Signal


class BuyStrategy:
    def generate_signal(self, df):
        return Signal.BUY


class SellStrategy:
    def generate_signal(self, df):
        return Signal.SELL


class HoldStrategy:
    def generate_signal(self, df):
        return Signal.HOLD


df = pd.DataFrame({"close": [100, 101, 102]})

engine = StrategyEngine([
    BuyStrategy(),
    SellStrategy(),
])

result = engine.run(df)

print(result["strategy_results"])
print(result["final_signal"])
print(result["final_signal"].value)