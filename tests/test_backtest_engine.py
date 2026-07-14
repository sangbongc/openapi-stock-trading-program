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


def test_indicator_builder_runs_once_for_entire_backtest() -> None:
    calls = 0

    def counting_builder(data: pd.DataFrame) -> pd.DataFrame:
        nonlocal calls
        calls += 1
        return data.copy()

    engine = BacktestEngine(
        strategy_engine=SequenceStrategyEngine({}),
        indicator_builder=counting_builder,
        minimum_data_length=1,
    )

    engine.run("005930", prices())

    assert calls == 1


def test_fixed_stop_loss_executes_at_stop_price() -> None:
    data = pd.DataFrame([
        {"date": "20260101", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
        {"date": "20260102", "open": 100, "high": 101, "low": 90, "close": 95, "volume": 1000},
        {"date": "20260103", "open": 96, "high": 97, "low": 95, "close": 96, "volume": 1000},
    ])
    engine = BacktestEngine(
        strategy_engine=SequenceStrategyEngine({"20260101": Signal.BUY}),
        indicator_builder=passthrough,
        initial_cash=1_000,
        minimum_data_length=1,
        commission_rate=0.0,
        slippage_rate=0.0,
        stop_loss_rate=0.08,
        trailing_stop_rate=None,
    )

    result = engine.run("005930", data)

    assert [trade.side for trade in result.trades] == ["BUY", "SELL"]
    assert result.trades[1].price == pytest.approx(92.0)
    assert result.trades[1].reason.startswith("고정 손절")


def test_stop_loss_uses_open_price_after_gap_down() -> None:
    data = pd.DataFrame([
        {"date": "20260101", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
        {"date": "20260102", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
        {"date": "20260103", "open": 85, "high": 86, "low": 84, "close": 85, "volume": 1000},
        {"date": "20260104", "open": 86, "high": 87, "low": 85, "close": 86, "volume": 1000},
    ])
    engine = BacktestEngine(
        strategy_engine=SequenceStrategyEngine({"20260101": Signal.BUY}),
        indicator_builder=passthrough,
        initial_cash=1_000,
        minimum_data_length=1,
        commission_rate=0.0,
        slippage_rate=0.0,
        stop_loss_rate=0.08,
        trailing_stop_rate=None,
    )

    result = engine.run("005930", data)

    assert result.trades[1].price == 85


def test_trailing_stop_uses_previous_confirmed_high() -> None:
    data = pd.DataFrame([
        {"date": "20260101", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
        {"date": "20260102", "open": 100, "high": 120, "low": 99, "close": 118, "volume": 1000},
        {"date": "20260103", "open": 115, "high": 116, "low": 107, "close": 109, "volume": 1000},
        {"date": "20260104", "open": 110, "high": 111, "low": 109, "close": 110, "volume": 1000},
    ])
    engine = BacktestEngine(
        strategy_engine=SequenceStrategyEngine({"20260101": Signal.BUY}),
        indicator_builder=passthrough,
        initial_cash=1_000,
        minimum_data_length=1,
        commission_rate=0.0,
        slippage_rate=0.0,
        stop_loss_rate=None,
        trailing_stop_rate=0.10,
    )

    result = engine.run("005930", data)

    assert result.trades[1].price == pytest.approx(108.0)
    assert result.trades[1].reason.startswith("추적 손절")


def test_stop_reentry_cooldown_blocks_buy_for_five_days() -> None:
    rows = []
    signals = {}
    for index in range(8):
        date = f"202601{index + 1:02d}"
        rows.append({
            "date": date,
            "open": 100,
            "high": 101,
            "low": 90 if index == 1 else 99,
            "close": 100,
            "volume": 1000,
        })
        signals[date] = Signal.BUY

    engine = BacktestEngine(
        strategy_engine=SequenceStrategyEngine(signals),
        indicator_builder=passthrough,
        initial_cash=1_000,
        minimum_data_length=1,
        commission_rate=0.0,
        slippage_rate=0.0,
        stop_loss_rate=0.08,
        trailing_stop_rate=None,
        stop_reentry_cooldown_days=5,
    )

    result = engine.run("005930", pd.DataFrame(rows))

    assert [(trade.side, trade.date) for trade in result.trades[:3]] == [
        ("BUY", "20260102"),
        ("SELL", "20260102"),
        ("BUY", "20260108"),
    ]
