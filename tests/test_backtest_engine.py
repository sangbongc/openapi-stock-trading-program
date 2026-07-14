from dataclasses import dataclass

import pandas as pd
import pytest

from backtesting import BacktestEngine
from strategies.signal import Signal


@dataclass
class FakeResult:
    final_signal: Signal


class SequenceStrategyEngine:
    def __init__(self, signals: dict[str, Signal]) -> None:
        self.signals = signals

    def run(self, data: pd.DataFrame) -> FakeResult:
        date = str(data.iloc[-1]["date"])
        return FakeResult(self.signals.get(date, Signal.HOLD))


def passthrough(data: pd.DataFrame) -> pd.DataFrame:
    return data.copy()


def prices() -> pd.DataFrame:
    return pd.DataFrame([
        {"date": "20260101", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
        {"date": "20260102", "open": 101, "high": 103, "low": 100, "close": 102, "volume": 1000},
        {"date": "20260103", "open": 105, "high": 107, "low": 104, "close": 106, "volume": 1000},
        {"date": "20260104", "open": 110, "high": 112, "low": 109, "close": 111, "volume": 1000},
    ])


def test_signal_is_filled_at_next_day_open() -> None:
    engine = BacktestEngine(
        strategy_engine=SequenceStrategyEngine({
            "20260101": Signal.BUY,
            "20260103": Signal.SELL,
        }),
        indicator_builder=passthrough,
        initial_cash=1_000,
        minimum_data_length=1,
        commission_rate=0.0,
        slippage_rate=0.0,
    )
    result = engine.run("005930", prices())

    assert len(result.trades) == 2
    assert result.trades[0].date == "20260102"
    assert result.trades[0].price == 101
    assert result.trades[0].quantity == 9
    assert result.trades[1].date == "20260104"
    assert result.trades[1].price == 110
    assert result.final_equity == 1_081


def test_does_not_buy_twice_while_holding() -> None:
    engine = BacktestEngine(
        strategy_engine=SequenceStrategyEngine({
            "20260101": Signal.BUY,
            "20260102": Signal.BUY,
        }),
        indicator_builder=passthrough,
        initial_cash=1_000,
        minimum_data_length=1,
        commission_rate=0.0,
        slippage_rate=0.0,
    )
    result = engine.run("005930", prices())
    assert sum(trade.side == "BUY" for trade in result.trades) == 1


def test_missing_required_column_raises_error() -> None:
    engine = BacktestEngine(
        strategy_engine=SequenceStrategyEngine({}),
        indicator_builder=passthrough,
        minimum_data_length=1,
    )
    with pytest.raises(KeyError):
        engine.run("005930", prices().drop(columns=["open"]))
