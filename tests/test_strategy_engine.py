import pandas as pd

from strategies.base_strategy import BaseStrategy
from strategies.signal import Signal
from strategies.result import StrategyResult
from strategies.strategy_engine import StrategyEngine


class FakeStrategy(BaseStrategy):
    """
    테스트에서 지정한 StrategyResult를 그대로 반환하는 가짜 전략.
    """

    def __init__(
        self,
        name: str,
        signal: Signal,
        confidence: float,
        reason: str = "테스트 결과",
    ) -> None:
        self.name = name
        self._result = StrategyResult(
            strategy=name,
            signal=signal,
            confidence=confidence,
            reason=reason,
        )

    def generate_signal(
        self,
        data: pd.DataFrame,
    ) -> StrategyResult:
        return self._result


def create_test_dataframe() -> pd.DataFrame:
    """
    StrategyEngine에 전달할 최소 테스트 데이터.
    """
    return pd.DataFrame({
        "close": [100, 101, 102],
    })


def test_engine_returns_buy() -> None:
    strategies = [
        FakeStrategy("MA", Signal.BUY, 0.8),
        FakeStrategy("RSI", Signal.BUY, 0.7),
        FakeStrategy("MACD", Signal.HOLD, 0.5),
    ]

    engine = StrategyEngine(
        strategies=strategies,
        buy_threshold=0.3,
        sell_threshold=-0.3,
    )

    result = engine.run(create_test_dataframe())

    expected_score = (0.8 + 0.7 + 0.0) / 3

    assert result.final_signal == Signal.BUY
    assert result.confidence_score == expected_score
    assert result.final_confidence == expected_score
    assert len(result.strategy_results) == 3


def test_engine_returns_sell() -> None:
    strategies = [
        FakeStrategy("MA", Signal.SELL, 0.9),
        FakeStrategy("RSI", Signal.SELL, 0.6),
        FakeStrategy("MACD", Signal.HOLD, 0.5),
    ]

    engine = StrategyEngine(
        strategies=strategies,
        buy_threshold=0.3,
        sell_threshold=-0.3,
    )

    result = engine.run(create_test_dataframe())

    expected_score = (-0.9 - 0.6 + 0.0) / 3

    assert result.final_signal == Signal.SELL
    assert result.confidence_score == expected_score
    assert result.final_confidence == abs(expected_score)


def test_engine_returns_hold_when_signals_conflict() -> None:
    strategies = [
        FakeStrategy("MA", Signal.BUY, 0.8),
        FakeStrategy("RSI", Signal.SELL, 0.7),
        FakeStrategy("MACD", Signal.HOLD, 0.5),
    ]

    engine = StrategyEngine(
        strategies=strategies,
        buy_threshold=0.3,
        sell_threshold=-0.3,
    )

    result = engine.run(create_test_dataframe())

    expected_score = (0.8 - 0.7 + 0.0) / 3
    expected_confidence = 1.0 - abs(expected_score)

    assert result.final_signal == Signal.HOLD
    assert result.confidence_score == expected_score
    assert result.final_confidence == expected_confidence


def test_engine_rejects_empty_strategy_list() -> None:
    try:
        StrategyEngine(strategies=[])

    except ValueError as error:
        assert str(error) == "최소 하나 이상의 전략이 필요합니다."

    else:
        raise AssertionError(
            "전략 목록이 비어 있으면 ValueError가 발생해야 합니다."
        )


def test_engine_rejects_empty_dataframe() -> None:
    strategy = FakeStrategy(
        "MA",
        Signal.BUY,
        0.8,
    )

    engine = StrategyEngine([strategy])

    try:
        engine.run(pd.DataFrame())

    except ValueError as error:
        assert str(error) == "전략을 실행할 데이터가 비어 있습니다."

    else:
        raise AssertionError(
            "빈 DataFrame이면 ValueError가 발생해야 합니다."
        )


def test_engine_rejects_invalid_confidence() -> None:
    strategy = FakeStrategy(
        "Invalid",
        Signal.BUY,
        1.5,
    )

    engine = StrategyEngine([strategy])

    try:
        engine.run(create_test_dataframe())

    except ValueError as error:
        assert "confidence는" in str(error)

    else:
        raise AssertionError(
            "confidence가 범위를 벗어나면 "
            "ValueError가 발생해야 합니다."
        )


def test_engine_rejects_duplicate_strategy_names() -> None:
    strategies = [
        FakeStrategy("MA", Signal.BUY, 0.8),
        FakeStrategy("MA", Signal.SELL, 0.7),
    ]

    engine = StrategyEngine(strategies)

    try:
        engine.run(create_test_dataframe())

    except ValueError as error:
        assert "중복된 전략 이름" in str(error)

    else:
        raise AssertionError(
            "전략 이름이 중복되면 ValueError가 발생해야 합니다."
        )


if __name__ == "__main__":
    test_engine_returns_buy()
    test_engine_returns_sell()
    test_engine_returns_hold_when_signals_conflict()
    test_engine_rejects_empty_strategy_list()
    test_engine_rejects_empty_dataframe()
    test_engine_rejects_invalid_confidence()
    test_engine_rejects_duplicate_strategy_names()

    print("모든 StrategyEngine 테스트를 통과했습니다.")