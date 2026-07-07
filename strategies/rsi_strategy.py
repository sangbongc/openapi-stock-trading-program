import pandas as pd

from strategies.signal import Signal


class RSIStrategy:
    def __init__(self, period: int = 14, buy_threshold: float = 30, sell_threshold: float = 70):
        self.period = period
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def generate_signal(self, df: pd.DataFrame) -> Signal:
        if "close" not in df.columns:
            raise ValueError("df must contain 'close' column")

        if len(df) < self.period + 1:
            return Signal.HOLD

        delta = df["close"].diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(window=self.period).mean()
        avg_loss = loss.rolling(window=self.period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        latest_rsi = rsi.iloc[-1]

        if latest_rsi < self.buy_threshold:
            return Signal.BUY
        elif latest_rsi > self.sell_threshold:
            return Signal.SELL
        else:
            return Signal.HOLD