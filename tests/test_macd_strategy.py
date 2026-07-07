import pandas as pd

from strategies.macd_strategy import MACDStrategy


data = pd.DataFrame({
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

strategy = MACDStrategy()

signal = strategy.generate_signal(data)

print(signal)
print(signal.value)