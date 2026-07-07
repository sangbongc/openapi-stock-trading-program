import pandas as pd

from strategies import (
    StrategyEngine,
    MACrossStrategy,
    RSIStrategy,
    BollingerBandStrategy,
    MACDStrategy,
)


df = pd.DataFrame({
    "close": [
        100, 99, 98, 97, 96,
        95, 94, 93, 92, 91,
        90, 89, 88, 87, 86,
        85, 86, 87, 88, 89,
        90, 91, 92, 93, 94,
        95, 96, 97, 98, 99,
        100, 101, 102, 103, 104,
        105, 106, 107, 108, 109
    ]
})

df["ma5"] = df["close"].rolling(window=5).mean()
df["ma20"] = df["close"].rolling(window=20).mean()

engine = StrategyEngine([
    MACrossStrategy(),
    RSIStrategy(),
    BollingerBandStrategy(),
    MACDStrategy(),
])

result = engine.run(df)

print("===== Strategy Analysis =====")

for strategy_name, signal in result["strategy_results"].items():
    print(f"{strategy_name:20} : {signal.value}")

print("-" * 35)
print(f"{'Final Decision':20} : {result['final_signal'].value}")