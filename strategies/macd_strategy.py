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

        if len(data) < 2:
            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason="MACD 교차를 판단하기 위한 데이터가 부족합니다.",
            )

        previous = data.iloc[-2]
        current = data.iloc[-1]

        previous_macd = previous["macd"]
        previous_signal = previous["macd_signal"]

        current_macd = current["macd"]
        current_signal = current["macd_signal"]

        values = [
            previous_macd,
            previous_signal,
            current_macd,
            current_signal,
        ]

        if any(pd.isna(value) for value in values):
            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason="MACD 계산 결과에 결측치가 있습니다.",
            )

        previous_macd = float(previous_macd)
        previous_signal = float(previous_signal)
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

        if (
            previous_macd <= previous_signal
            and current_macd > current_signal
        ):
            return StrategyResult(
                strategy=self.name,
                signal=Signal.BUY,
                confidence=confidence,
                reason=(
                    f"MACD({current_macd:.2f})가 "
                    f"시그널선({current_signal:.2f})을 "
                    "상향 돌파했습니다."
                ),
            )

        if (
            previous_macd >= previous_signal
            and current_macd < current_signal
        ):
            return StrategyResult(
                strategy=self.name,
                signal=Signal.SELL,
                confidence=confidence,
                reason=(
                    f"MACD({current_macd:.2f})가 "
                    f"시그널선({current_signal:.2f})을 "
                    "하향 돌파했습니다."
                ),
            )

        return StrategyResult(
            strategy=self.name,
            signal=Signal.HOLD,
            confidence=0.0,
            reason=(
                f"MACD({current_macd:.2f})와 "
                f"시그널선({current_signal:.2f}) 사이에 "
                "최근 교차가 발생하지 않았습니다."
            ),
        )