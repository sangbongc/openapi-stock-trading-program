import pandas as pd

from strategies.rsi_strategy import RSIStrategy


data = pd.DataFrame({
    "close": [
        100, 99, 98, 97, 96,
        95, 94, 93, 92, 91,
        90, 89, 88, 87, 86,
        85, 84, 83, 82, 81
    ]
})

strategy = RSIStrategy()

signal = strategy.generate_signal(data)

print(signal)
print(signal.value)