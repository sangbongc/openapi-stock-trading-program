import pandas as pd

from .base_strategy import BaseStrategy
from .result import StrategyResult
from .signal import Signal


class BollingerBandStrategy(BaseStrategy):
    name = "Bollinger Band"

    def __init__(self, window: int = 20):
        if window <= 0:
            raise ValueError("window는 1 이상이어야 합니다.")

        self.window = window

    def generate_signal(self, data: pd.DataFrame) -> StrategyResult:
        middle_column = f"bb_mid{self.window}"
        upper_column = f"bb_upper{self.window}"
        lower_column = f"bb_lower{self.window}"

        required_columns = {
            "close",
            middle_column,
            upper_column,
            lower_column,
        }

        if not required_columns.issubset(data.columns):
            missing_columns = required_columns - set(data.columns)

            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason=(
                    "필요한 볼린저 밴드 컬럼이 없습니다: "
                    f"{', '.join(sorted(missing_columns))}"
                ),
            )

        if data.empty:
            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason="볼린저 밴드를 판단할 데이터가 없습니다.",
            )

        current = data.iloc[-1]

        close = current["close"]
        middle = current[middle_column]
        upper = current[upper_column]
        lower = current[lower_column]

        values = [close, middle, upper, lower]

        if any(pd.isna(value) for value in values):
            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason="볼린저 밴드 계산 결과에 결측치가 있습니다.",
            )

        close = float(close)
        middle = float(middle)
        upper = float(upper)
        lower = float(lower)

        band_width = upper - lower

        if band_width <= 0:
            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason="볼린저 밴드 폭이 0 이하입니다.",
            )

        if close <= lower:
            confidence = float(
                min((lower - close) / band_width, 1.0)
            )

            return StrategyResult(
                strategy=self.name,
                signal=Signal.BUY,
                confidence=confidence,
                reason=(
                    f"종가({close:.2f})가 "
                    f"하단 밴드({lower:.2f}) 아래에 있습니다."
                ),
            )

        if close >= upper:
            confidence = float(
                min((close - upper) / band_width, 1.0)
            )

            return StrategyResult(
                strategy=self.name,
                signal=Signal.SELL,
                confidence=confidence,
                reason=(
                    f"종가({close:.2f})가 "
                    f"상단 밴드({upper:.2f}) 위에 있습니다."
                ),
            )

        return StrategyResult(
            strategy=self.name,
            signal=Signal.HOLD,
            confidence=0.0,
            reason=(
                f"종가({close:.2f})가 "
                "볼린저 밴드 내부에 있습니다."
            ),
        )