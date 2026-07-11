import pandas as pd

from .base_strategy import BaseStrategy
from .result import StrategyResult
from .signal import Signal


class RSIStrategy(BaseStrategy):
    name = "RSI"

    def __init__(
        self,
        oversold: float = 30.0,
        overbought: float = 70.0,
    ):
        if not 0 <= oversold < overbought <= 100:
            raise ValueError(
                "RSI 기준값은 0 이상 100 이하이며, "
                "oversold는 overbought보다 작아야 합니다."
            )

        self.oversold = oversold
        self.overbought = overbought

    def generate_signal(self, data: pd.DataFrame) -> StrategyResult:
        if "rsi14" not in data.columns:
            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason="RSI 컬럼이 없습니다.",
            )

        if data.empty:
            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason="RSI를 판단할 데이터가 없습니다.",
            )

        current_rsi = data.iloc[-1]["rsi14"]

        if pd.isna(current_rsi):
            return StrategyResult(
                strategy=self.name,
                signal=Signal.HOLD,
                confidence=0.0,
                reason="최근 RSI(14) 값이 결측치입니다.",
            )

        current_rsi = float(current_rsi)

        if current_rsi <= self.oversold:
            confidence = min(
                (self.oversold - current_rsi) / self.oversold,
                1.0,
            )

            return StrategyResult(
                strategy=self.name,
                signal=Signal.BUY,
                confidence=float(confidence),
                reason=(
                    f"RSI가 {current_rsi:.2f}로 "
                    f"과매도 기준 {self.oversold:.2f} 이하입니다."
                ),
            )

        if current_rsi >= self.overbought:
            confidence = min(
                (current_rsi - self.overbought)
                / (100 - self.overbought),
                1.0,
            )

            return StrategyResult(
                strategy=self.name,
                signal=Signal.SELL,
                confidence=float(confidence),
                reason=(
                    f"RSI가 {current_rsi:.2f}로 "
                    f"과매수 기준 {self.overbought:.2f} 이상입니다."
                ),
            )

        distance_from_neutral = abs(current_rsi - 50) / 50

        return StrategyResult(
            strategy=self.name,
            signal=Signal.HOLD,
            confidence=0.0,
            reason=(
                f"RSI가 {current_rsi:.2f}로 "
                "과매수·과매도 구간에 해당하지 않습니다."
            ),
        )