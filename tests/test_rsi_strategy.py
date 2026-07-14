import pandas as pd
import pytest

from strategies.rsi_strategy import RSIStrategy
from strategies.signal import Signal


@pytest.fixture
def strategy() -> RSIStrategy:
    return RSIStrategy(oversold=30, overbought=70)


def test_oversold_rsi_returns_buy(strategy: RSIStrategy) -> None:
    result = strategy.generate_signal(pd.DataFrame({"rsi14": [25.0]}))

    assert result.signal == Signal.BUY
    assert result.confidence == pytest.approx((30 - 25) / 30)


def test_overbought_rsi_returns_sell(strategy: RSIStrategy) -> None:
    result = strategy.generate_signal(pd.DataFrame({"rsi14": [80.0]}))

    assert result.signal == Signal.SELL
    assert result.confidence == pytest.approx((80 - 70) / 30)


def test_neutral_rsi_returns_hold(strategy: RSIStrategy) -> None:
    result = strategy.generate_signal(pd.DataFrame({"rsi14": [55.0]}))

    assert result.signal == Signal.HOLD
    assert result.confidence == 0.0


def test_missing_or_nan_rsi_returns_hold(strategy: RSIStrategy) -> None:
    missing = strategy.generate_signal(pd.DataFrame({"rsi": [25.0]}))
    nan_value = strategy.generate_signal(pd.DataFrame({"rsi14": [float("nan")]}))

    assert missing.signal == Signal.HOLD
    assert nan_value.signal == Signal.HOLD
