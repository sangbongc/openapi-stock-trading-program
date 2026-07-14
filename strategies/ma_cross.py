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

        if data.empty:
            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason="이동평균 추세를 판단할 데이터가 없습니다.",
            )

        current = data.iloc[-1]
        current_short = current[short_column]
        current_long = current[long_column]

        if pd.isna(current_short) or pd.isna(current_long):
            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason="최근 이동평균 계산 결과에 결측치가 있습니다.",
            )

        current_short = float(current_short)
        current_long = float(current_long)

        if current_long == 0:
            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason="장기 이동평균 값이 0이어서 추세를 판단할 수 없습니다.",
            )

        difference_rate = abs(
            current_short - current_long
        ) / abs(current_long)
        confidence = float(min(difference_rate * 10, 1.0))

        if current_short > current_long:
            return StrategyResult(
                strategy=self.name,
                signal=Signal.BUY,
                confidence=confidence,
                reason=(
                    f"{self.short_window}일 이동평균선이 "
                    f"{self.long_window}일 이동평균선보다 위에 있어 "
                    "상승 배열이 유지되고 있습니다."
                ),
            )

        if current_short < current_long:
            return StrategyResult(
                strategy=self.name,
                signal=Signal.SELL,
                confidence=confidence,
                reason=(
                    f"{self.short_window}일 이동평균선이 "
                    f"{self.long_window}일 이동평균선보다 아래에 있어 "
                    "하락 배열이 유지되고 있습니다."
                ),
            )

        return StrategyResult(
            strategy=self.name,
            signal=Signal.HOLD,
            confidence=0.0,
            reason=(
                f"{self.short_window}일 이동평균선과 "
                f"{self.long_window}일 이동평균선이 같아 "
                "방향성이 확인되지 않습니다."
            ),
        )