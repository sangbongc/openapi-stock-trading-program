from strategies.base_strategy import BaseStrategy
from strategies.signal import Signal
import pandas as pd
from strategies.result import StrategyResult

class MACrossStrategy(BaseStrategy):
    name = "MA Cross"

    def __init__(self, short_window: int = 5, long_window: int = 20):
        if short_window <= 0 or long_window <= 0:
            raise ValueError("이동평균 기간은 1 이상이어야 합니다.")

        if short_window >= long_window:
            raise ValueError(
                "short_window는 long_window보다 작아야 합니다."
            )

        self.short_window = short_window
        self.long_window = long_window

    def generate_signal(self, data: pd.DataFrame) -> StrategyResult:
        short_column = f"ma{self.short_window}"
        long_column = f"ma{self.long_window}"

        required_columns = {short_column, long_column}

        if not required_columns.issubset(data.columns):
            missing_columns = required_columns - set(data.columns)

            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason=(
                    "필요한 이동평균 컬럼이 없습니다: "
                    f"{', '.join(sorted(missing_columns))}"
                ),
            )

        if len(data) < 2:
            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason="교차 여부를 판단하기 위한 데이터가 부족합니다.",
            )

        previous = data.iloc[-2]
        current = data.iloc[-1]

        previous_short = previous[short_column]
        previous_long = previous[long_column]

        current_short = current[short_column]
        current_long = current[long_column]

        values = [
            previous_short,
            previous_long,
            current_short,
            current_long,
        ]

        if any(pd.isna(value) for value in values):
            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason="이동평균 계산 결과에 결측치가 있습니다.",
            )

        difference_rate = abs(
            current_short - current_long
        ) / current_long

        confidence = float(min(difference_rate * 10, 1.0))

        if (
            previous_short <= previous_long
            and current_short > current_long
        ):
            return StrategyResult(
                strategy=self.name,
                signal=Signal.BUY,
                confidence=confidence,
                reason=(
                    f"{self.short_window}일 이동평균선이 "
                    f"{self.long_window}일 이동평균선을 "
                    "상향 돌파했습니다."
                ),
            )

        if (
            previous_short >= previous_long
            and current_short < current_long
        ):
            return StrategyResult(
                strategy=self.name,
                signal=Signal.SELL,
                confidence=confidence,
                reason=(
                    f"{self.short_window}일 이동평균선이 "
                    f"{self.long_window}일 이동평균선을 "
                    "하향 돌파했습니다."
                ),
            )

        return StrategyResult(
            strategy=self.name,
            signal=Signal.HOLD,
            confidence=confidence,
            reason=(
                "최근 두 거래일 사이에 이동평균선 교차가 "
                "발생하지 않았습니다."
            ),
        )