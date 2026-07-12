from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from strategies.base_strategy import BaseStrategy
from strategies.signal import Signal
from strategies.result import StrategyResult


@dataclass(frozen=True)
class EngineResult:
    """
    여러 전략의 결과를 종합한 최종 판단 결과.

    Attributes
    ----------
    final_signal : Signal
        전략 결과를 종합하여 결정한 최종 매매 신호

    confidence_score : float
        BUY는 양수, SELL은 음수로 환산하여 합산한 신뢰도 점수

    final_confidence : float
        최종 신호에 대한 신뢰도. 0.0 이상 1.0 이하

    strategy_results : dict[str, StrategyResult]
        전략별 상세 판단 결과
    """

    final_signal: Signal
    confidence_score: float
    final_confidence: float
    strategy_results: dict[str, StrategyResult]


class StrategyEngine:
    """
    여러 전략을 실행하고 각 전략의 신호와 confidence를
    종합하여 최종 매매 신호를 결정한다.
    """

    def __init__(
        self,
        strategies: Iterable[BaseStrategy],
        buy_threshold: float = 0.3,
        sell_threshold: float = -0.3,
    ) -> None:
        """
        Parameters
        ----------
        strategies : Iterable[BaseStrategy]
            실행할 전략 객체 목록

        buy_threshold : float, default=0.3
            평균 신뢰도 점수가 이 값 이상이면 BUY

        sell_threshold : float, default=-0.3
            평균 신뢰도 점수가 이 값 이하이면 SELL
        """
        self.strategies = list(strategies)

        if not self.strategies:
            raise ValueError("최소 하나 이상의 전략이 필요합니다.")

        if not isinstance(buy_threshold, (int, float)):
            raise TypeError("buy_threshold는 숫자여야 합니다.")

        if not isinstance(sell_threshold, (int, float)):
            raise TypeError("sell_threshold는 숫자여야 합니다.")

        if not -1.0 <= sell_threshold <= 1.0:
            raise ValueError(
                "sell_threshold는 -1.0 이상 1.0 이하여야 합니다."
            )

        if not -1.0 <= buy_threshold <= 1.0:
            raise ValueError(
                "buy_threshold는 -1.0 이상 1.0 이하여야 합니다."
            )

        if sell_threshold >= buy_threshold:
            raise ValueError(
                "sell_threshold는 buy_threshold보다 작아야 합니다."
            )

        self.buy_threshold = float(buy_threshold)
        self.sell_threshold = float(sell_threshold)

    def run(self, data: pd.DataFrame) -> EngineResult:
        """
        등록된 모든 전략을 실행하고 최종 매매 신호를 반환한다.

        Parameters
        ----------
        data : pd.DataFrame
            전략 판단에 사용할 가격 및 지표 데이터

        Returns
        -------
        EngineResult
            최종 신호, 신뢰도 점수, 최종 신뢰도, 전략별 결과
        """
        if not isinstance(data, pd.DataFrame):
            raise TypeError("data는 pandas DataFrame이어야 합니다.")

        if data.empty:
            raise ValueError("전략을 실행할 데이터가 비어 있습니다.")

        strategy_results: dict[str, StrategyResult] = {}
        weighted_confidence_sum = 0.0
        active_signal_count = 0

        for strategy in self.strategies:
            result = strategy.generate_signal(data)

            self._validate_strategy_result(strategy, result)

            strategy_name = getattr(
                strategy,
                "name",
                strategy.__class__.__name__,
            )

            if strategy_name in strategy_results:
                raise ValueError(
                    f"중복된 전략 이름이 존재합니다: {strategy_name}"
                )

            strategy_results[strategy_name] = result

            weighted_confidence_sum += (
                self._convert_to_signed_confidence(result)
            )

            if result.signal != Signal.HOLD:
                active_signal_count += 1

        if active_signal_count == 0:
            confidence_score = 0.0
        else:
            confidence_score = (
                weighted_confidence_sum / active_signal_count
            )
        final_signal = self._determine_final_signal(confidence_score)

        final_confidence = self._calculate_final_confidence(
            final_signal=final_signal,
            confidence_score=confidence_score,
        )

        return EngineResult(
            final_signal=final_signal,
            confidence_score=confidence_score,
            final_confidence=final_confidence,
            strategy_results=strategy_results,
        )

    @staticmethod
    def _validate_strategy_result(
        strategy: BaseStrategy,
        result: StrategyResult,
    ) -> None:
        """
        전략이 반환한 StrategyResult의 타입과 값을 검증한다.
        """
        strategy_name = getattr(
            strategy,
            "name",
            strategy.__class__.__name__,
        )

        if not isinstance(result, StrategyResult):
            raise TypeError(
                f"{strategy_name}.generate_signal()은 "
                "StrategyResult를 반환해야 합니다."
            )

        if not isinstance(result.signal, Signal):
            raise TypeError(
                f"{strategy_name}의 signal은 Signal 타입이어야 합니다."
            )

        if not isinstance(result.confidence, (int, float)):
            raise TypeError(
                f"{strategy_name}의 confidence는 숫자여야 합니다."
            )

        if not 0.0 <= result.confidence <= 1.0:
            raise ValueError(
                f"{strategy_name}의 confidence는 "
                "0.0 이상 1.0 이하여야 합니다."
            )

        if not isinstance(result.reason, str):
            raise TypeError(
                f"{strategy_name}의 reason은 문자열이어야 합니다."
            )

    @staticmethod
    def _convert_to_signed_confidence(
        result: StrategyResult,
    ) -> float:
        """
        전략 신호를 방향성이 포함된 confidence 값으로 변환한다.

        BUY  -> 양수
        SELL -> 음수
        HOLD -> 0
        """
        if result.signal == Signal.BUY:
            return result.confidence

        if result.signal == Signal.SELL:
            return -result.confidence

        return 0.0

    def _determine_final_signal(
        self,
        confidence_score: float,
    ) -> Signal:
        """
        평균 신뢰도 점수를 기준으로 최종 신호를 결정한다.
        """
        if confidence_score >= self.buy_threshold:
            return Signal.BUY

        if confidence_score <= self.sell_threshold:
            return Signal.SELL

        return Signal.HOLD

    @staticmethod
    def _calculate_final_confidence(
        final_signal: Signal,
        confidence_score: float,
    ) -> float:
        """
        최종 신호에 대한 신뢰도를 계산한다.

        BUY 또는 SELL이면 평균 점수의 절댓값을 사용한다.
        HOLD이면 매수·매도 방향성이 약한 정도를 신뢰도로 표현한다.
        """
        if final_signal in {Signal.BUY, Signal.SELL}:
            return abs(confidence_score)

        return 1.0 - abs(confidence_score)