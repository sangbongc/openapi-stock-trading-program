import pandas as pd

from .base_strategy import BaseStrategy
from .result import StrategyResult
from .signal import Signal


class MACDStrategy(BaseStrategy):
    name = "MACD"

    def generate_signal(self, data: pd.DataFrame) -> StrategyResult:
        required_columns = {"macd", "macd_signal"}

        if not required_columns.issubset(data.columns):
            missing_columns = required_columns - set(data.columns)

            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason=(
                    "필요한 MACD 컬럼이 없습니다: "
                    f"{', '.join(sorted(missing_columns))}"
                ),
            )

        if data.empty:
            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason="MACD 방향을 판단할 데이터가 없습니다.",
            )

        current = data.iloc[-1]

        current_macd = current["macd"]
        current_signal = current["macd_signal"]

        if pd.isna(current_macd) or pd.isna(current_signal):
            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason="최근 MACD 계산 결과에 결측치가 있습니다.",
            )

        current_macd = float(current_macd)
        current_signal = float(current_signal)

        difference = abs(current_macd - current_signal)
        base_value = max(
            abs(current_macd),
            abs(current_signal),
            1.0,
        )

        confidence = float(
            min(difference / base_value, 1.0)
        )

        if current_macd > current_signal:
            return StrategyResult(
                strategy=self.name,
                signal=Signal.BUY,
                confidence=confidence,
                reason=(
                    f"MACD({current_macd:.2f})가 "
                    f"시그널선({current_signal:.2f})보다 위에 있어 "
                    "상승 모멘텀이 유지되고 있습니다."
                ),
            )

        if current_macd < current_signal:
            return StrategyResult(
                strategy=self.name,
                signal=Signal.SELL,
                confidence=confidence,
                reason=(
                    f"MACD({current_macd:.2f})가 "
                    f"시그널선({current_signal:.2f})보다 아래에 있어 "
                    "하락 모멘텀이 유지되고 있습니다."
                ),
            )

        return StrategyResult(
            strategy=self.name,
            signal=Signal.HOLD,
            confidence=0.0,
            reason=(
                f"MACD({current_macd:.2f})와 "
                f"시그널선({current_signal:.2f})이 같아 "
                "방향성이 확인되지 않습니다."
            ),
        )