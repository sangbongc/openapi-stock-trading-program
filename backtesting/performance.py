from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .models import BacktestTrade


def calculate_performance(
    equity_curve: list[dict[str, Any]],
    trades: list[BacktestTrade],
    initial_cash: float,
    trading_days_per_year: int = 252,
) -> dict[str, float | int]:
    if not equity_curve:
        return {
            "total_return": 0.0,
            "annualized_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "trade_count": 0,
            "completed_trade_count": 0,
            "win_rate": 0.0,
        }

    equity = pd.to_numeric(
        pd.DataFrame(equity_curve)["equity"],
        errors="raise",
    )
    final_equity = float(equity.iloc[-1])
    total_return = final_equity / initial_cash - 1.0
    periods = max(len(equity) - 1, 1)
    annualized_return = (
        (1.0 + total_return) ** (trading_days_per_year / periods) - 1.0
        if 1.0 + total_return > 0
        else -1.0
    )

    drawdown = equity / equity.cummax() - 1.0
    max_drawdown = float(drawdown.min())

    daily_returns = equity.pct_change().dropna()
    std = float(daily_returns.std(ddof=1)) if not daily_returns.empty else 0.0
    sharpe_ratio = (
        float(daily_returns.mean() / std * math.sqrt(trading_days_per_year))
        if std and not math.isnan(std)
        else 0.0
    )

    completed_returns = _completed_trade_returns(trades)
    completed_count = len(completed_returns)
    win_rate = (
        sum(value > 0 for value in completed_returns) / completed_count
        if completed_count
        else 0.0
    )

    return {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
        "trade_count": len(trades),
        "completed_trade_count": completed_count,
        "win_rate": win_rate,
    }


def _completed_trade_returns(trades: list[BacktestTrade]) -> list[float]:
    results: list[float] = []
    buy_trade: BacktestTrade | None = None

    for trade in trades:
        if trade.side == "BUY":
            buy_trade = trade
        elif trade.side == "SELL" and buy_trade is not None:
            buy_cost = buy_trade.gross_amount + buy_trade.fee
            sell_proceeds = trade.gross_amount - trade.fee
            if buy_cost > 0:
                results.append(sell_proceeds / buy_cost - 1.0)
            buy_trade = None

    return results
