import pandas as pd

from strategies.bollinger_strategy import BollingerBandStrategy


data = pd.DataFrame({
    "close": [
        100, 101, 102, 101, 100,
        99, 98, 99, 100, 101,
        102, 103, 102, 101, 100,
        99, 98, 97, 96, 80
    ]
})

strategy = BollingerBandStrategy()

signal = strategy.generate_signal(data)

print(signal)
print(signal.value)