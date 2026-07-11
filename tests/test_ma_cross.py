import pandas as pd

from indicator import add_rolling_mean
from strategies.ma_cross import MACrossStrategy


df = pd.DataFrame({
    "close": [
        100, 100, 100, 100, 100,
        100, 100, 100, 100, 100,
        100, 100, 100, 100, 100,
        100, 100, 100, 100, 100,
        150,
    ]
})

df = add_rolling_mean(
    df,
    column="close",
    windows=[5, 20],
    prefix="ma",
)

strategy = MACrossStrategy(
    short_window=5,
    long_window=20,
)

result = strategy.generate_signal(df)

print(df[["close", "ma5", "ma20"]].tail())
print(result)
print(result.signal)
print(result.confidence)
print(result.reason)