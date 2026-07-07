import pandas as pd

from strategies.base_strategy import BaseStrategy
from strategies.signal import Signal


class MACDStrategy(BaseStrategy):
    def __init__(self, short_period: int = 12, long_period: int = 26, signal_period: int = 9):
        self.short_period = short_period
        self.long_period = long_period
        self.signal_period = signal_period

    def generate_signal(self, df: pd.DataFrame) -> Signal:
        if "close" not in df.columns:
            raise ValueError("df must contain 'close' column")

        if len(df) < self.long_period + self.signal_period:
            return Signal.HOLD

        close = df["close"]

        short_ema = close.ewm(span=self.short_period, adjust=False).mean()
        long_ema = close.ewm(span=self.long_period, adjust=False).mean()

        macd = short_ema - long_ema
        signal_line = macd.ewm(span=self.signal_period, adjust=False).mean()

        prev_macd = macd.iloc[-2]
        prev_signal = signal_line.iloc[-2]

        latest_macd = macd.iloc[-1]
        latest_signal = signal_line.iloc[-1]

        if prev_macd <= prev_signal and latest_macd > latest_signal:
            return Signal.BUY
        elif prev_macd >= prev_signal and latest_macd < latest_signal:
            return Signal.SELL
        else:
            return Signal.HOLD