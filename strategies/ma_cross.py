from strategies.base_strategy import BaseStrategy
from strategies.signal import Signal


class MACrossStrategy(BaseStrategy):
    name = "MA Cross"
    def __init__(self, short_col: str = "ma5", long_col: str = "ma20"):
        self.short_col = short_col
        self.long_col = long_col

    def generate_signal(self, data):
        """
        이동평균선 교차 전략

        BUY  : 단기 이동평균선이 장기 이동평균선을 상향 돌파
        SELL : 단기 이동평균선이 장기 이동평균선을 하향 돌파
        HOLD : 그 외
        """

        if len(data) < 2:
            return Signal.HOLD

        if self.short_col not in data.columns or self.long_col not in data.columns:
            return Signal.HOLD

        prev_short = data[self.short_col].iloc[-2]
        prev_long = data[self.long_col].iloc[-2]

        curr_short = data[self.short_col].iloc[-1]
        curr_long = data[self.long_col].iloc[-1]

        if prev_short <= prev_long and curr_short > curr_long:
            return Signal.BUY

        elif prev_short >= prev_long and curr_short < curr_long:
            return Signal.SELL

        return Signal.HOLD