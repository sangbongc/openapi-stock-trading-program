import pandas as pd
import pytest

from strategies.macd_strategy import MACDStrategy
from strategies.signal import Signal


@pytest.fixture
def strategy() -> MACDStrategy:
    return MACDStrategy()


def test_macd_above_signal_returns_buy(strategy: MACDStrategy) -> None:
    data = pd.DataFrame({
        "macd": [0.5],
        "macd_signal": [0.2],
    })

    result = strategy.generate_signal(data)

    assert result.signal == Signal.BUY
    assert result.confidence == pytest.approx(0.3)


def test_macd_below_signal_returns_sell(strategy: MACDStrategy) -> None:
    data = pd.DataFrame({
        "macd": [-0.4],
        "macd_signal": [-0.2],
    })

    result = strategy.generate_signal(data)

    assert result.signal == Signal.SELL
    assert result.confidence == pytest.approx(0.2)


def test_equal_macd_and_signal_returns_hold(strategy: MACDStrategy) -> None:
    data = pd.DataFrame({
        "macd": [0.5],
        "macd_signal": [0.5],
    })

    result = strategy.generate_signal(data)

    assert result.signal == Signal.HOLD
    assert result.confidence == 0.0


def test_missing_or_nan_macd_returns_hold(strategy: MACDStrategy) -> None:
    missing = strategy.generate_signal(pd.DataFrame({"close": [100]}))
    nan_value = strategy.generate_signal(pd.DataFrame({
        "macd": [float("nan")],
        "macd_signal": [0.2],
    }))

    assert missing.signal == Signal.HOLD
    assert nan_value.signal == Signal.HOLD
