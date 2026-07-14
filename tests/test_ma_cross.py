import pandas as pd
import pytest

from strategies.ma_cross import MACrossStrategy
from strategies.signal import Signal


@pytest.fixture
def strategy() -> MACrossStrategy:
    return MACrossStrategy(short_window=5, long_window=20)


def test_bullish_alignment_returns_buy(strategy: MACrossStrategy) -> None:
    result = strategy.generate_signal(pd.DataFrame({
        "ma5": [105.0],
        "ma20": [100.0],
    }))

    assert result.signal == Signal.BUY
    assert result.confidence == pytest.approx(0.5)


def test_bearish_alignment_returns_sell(strategy: MACrossStrategy) -> None:
    result = strategy.generate_signal(pd.DataFrame({
        "ma5": [95.0],
        "ma20": [100.0],
    }))

    assert result.signal == Signal.SELL
    assert result.confidence == pytest.approx(0.5)


def test_equal_averages_return_hold(strategy: MACrossStrategy) -> None:
    result = strategy.generate_signal(pd.DataFrame({
        "ma5": [100.0],
        "ma20": [100.0],
    }))

    assert result.signal == Signal.HOLD
    assert result.confidence == 0.0


def test_missing_nan_or_zero_long_average_returns_hold(
    strategy: MACrossStrategy,
) -> None:
    missing = strategy.generate_signal(pd.DataFrame({"ma5": [100.0]}))
    nan_value = strategy.generate_signal(pd.DataFrame({
        "ma5": [100.0],
        "ma20": [float("nan")],
    }))
    zero_value = strategy.generate_signal(pd.DataFrame({
        "ma5": [100.0],
        "ma20": [0.0],
    }))

    assert missing.signal == Signal.HOLD
    assert nan_value.signal == Signal.HOLD
    assert zero_value.signal == Signal.HOLD
