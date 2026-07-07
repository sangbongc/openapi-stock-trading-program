import pandas as pd

from strategies.base_strategy import BaseStrategy
from strategies.signal import Signal


class BollingerBandStrategy(BaseStrategy):
    name = "Bollinger Band"
    def __init__(self, period: int = 20, num_std: float = 2.0):
        self.period = period
        self.num_std = num_std

    def generate_signal(self, df: pd.DataFrame) -> Signal:
        if "close" not in df.columns:
            raise ValueError("df must contain 'close' column")

        if len(df) < self.period:
            return Signal.HOLD

        close = df["close"]

        middle_band = close.rolling(window=self.period).mean()
        std = close.rolling(window=self.period).std()

        upper_band = middle_band + self.num_std * std
        lower_band = middle_band - self.num_std * std

        latest_close = close.iloc[-1]
        latest_upper = upper_band.iloc[-1]
        latest_lower = lower_band.iloc[-1]

        if latest_close < latest_lower:
            return Signal.BUY
        elif latest_close > latest_upper:
            return Signal.SELL
        else:
            return Signal.HOLD