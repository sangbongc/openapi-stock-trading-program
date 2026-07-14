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
        buy_threshold: float = 0.2,
        sell_threshold: float = -0.2,
        buy_trend_filter_column: str | None = None,
        strategy_weights: dict[str, float] | None = None,
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

        if buy_trend_filter_column is not None:
            if not isinstance(buy_trend_filter_column, str):
                raise TypeError("buy_trend_filter_column은 문자열 또는 None이어야 합니다.")
            if not buy_trend_filter_column.strip():
                raise ValueError("buy_trend_filter_column은 빈 문자열일 수 없습니다.")

        self.strategy_weights = self._validate_strategy_weights(
            strategy_weights
        )

        self.buy_threshold = float(buy_threshold)
        self.sell_threshold = float(sell_threshold)
        self.buy_trend_filter_column = buy_trend_filter_column

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

            signed_confidence = self._convert_to_signed_confidence(result)
            if self.strategy_weights is None:
                weighted_confidence_sum += signed_confidence
            else:
                weighted_confidence_sum += (
                    signed_confidence * self.strategy_weights[strategy_name]
                )

            if result.signal != Signal.HOLD:
                active_signal_count += 1

        if self.strategy_weights is not None:
            # HOLD는 0점으로 포함한다. 따라서 일부 보조 전략만 신호를
            # 내는 경우 전체 가중치가 분모에 남아 단독 주문을 억제한다.
            confidence_score = weighted_confidence_sum / sum(
                self.strategy_weights.values()
            )
        elif active_signal_count == 0:
            confidence_score = 0.0
        else:
            confidence_score = (
                weighted_confidence_sum / active_signal_count
            )
        final_signal = self._determine_final_signal(confidence_score)
        final_signal = self._apply_buy_trend_filter(
            final_signal=final_signal,
            data=data,
        )

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

    def _validate_strategy_weights(
        self,
        strategy_weights: dict[str, float] | None,
    ) -> dict[str, float] | None:
        """전략 객체 이름과 일치하는 양수 가중치인지 검증한다."""
        if strategy_weights is None:
            return None
        if not isinstance(strategy_weights, dict):
            raise TypeError("strategy_weights는 딕셔너리 또는 None이어야 합니다.")

        strategy_names = [
            getattr(strategy, "name", strategy.__class__.__name__)
            for strategy in self.strategies
        ]
        if len(strategy_names) != len(set(strategy_names)):
            raise ValueError("전략 이름은 중복될 수 없습니다.")

        expected = set(strategy_names)
        received = set(strategy_weights)
        if expected != received:
            missing = sorted(expected - received)
            unknown = sorted(received - expected)
            raise ValueError(
                "strategy_weights의 전략 이름이 일치하지 않습니다. "
                f"누락={missing}, 알 수 없음={unknown}"
            )

        validated: dict[str, float] = {}
        for name, weight in strategy_weights.items():
            if (
                not isinstance(weight, (int, float))
                or isinstance(weight, bool)
                or weight <= 0
            ):
                raise ValueError(f"{name}의 가중치는 0보다 큰 숫자여야 합니다.")
            validated[name] = float(weight)

        return validated

    def _apply_buy_trend_filter(
        self,
        final_signal: Signal,
        data: pd.DataFrame,
    ) -> Signal:
        """지정된 추세선 아래에서는 신규 BUY 신호를 차단한다."""
        if final_signal != Signal.BUY or self.buy_trend_filter_column is None:
            return final_signal

        column = self.buy_trend_filter_column
        if "close" not in data.columns:
            raise KeyError("매수 추세 필터 적용에 필요한 close 컬럼이 없습니다.")
        if column not in data.columns:
            raise KeyError(f"매수 추세 필터 컬럼이 없습니다: {column}")

        close = data.iloc[-1]["close"]
        trend_value = data.iloc[-1][column]

        # 추세선이 아직 계산되지 않은 초기 구간도 신규 매수를 허용하지 않는다.
        if pd.isna(close) or pd.isna(trend_value):
            return Signal.HOLD

        if float(close) <= float(trend_value):
            return Signal.HOLD

        return Signal.BUY

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