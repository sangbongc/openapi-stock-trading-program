from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BacktestTrade:
    date: str
    side: str
    price: float
    quantity: int
    gross_amount: float
    fee: float
    cash_after: float
    reason: str = ""


@dataclass
class BacktestResult:
    stock_code: str
    initial_cash: float
    final_cash: float
    final_position_quantity: int
    final_position_value: float
    final_equity: float
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, float | int] = field(default_factory=dict)
