from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from strategies.signal import Signal

from .models import BacktestResult, BacktestTrade
from .performance import calculate_performance


class BacktestEngine:
    """
    단일 종목 일봉 기반 Long-only 백테스트 엔진.

    오늘 종가까지의 데이터로 만든 신호를 다음 거래일 시가에 체결하여
    미래 데이터 누출을 방지한다.
    """

    REQUIRED_COLUMNS = {"date", "open", "high", "low", "close", "volume"}

    def __init__(
        self,
        strategy_engine: Any,
        indicator_builder: Callable[[pd.DataFrame], pd.DataFrame],
        initial_cash: float = 100_000_000.0,
        minimum_data_length: int = 120,
        commission_rate: float = 0.00015,
        slippage_rate: float = 0.0005,
    ) -> None:
        if not callable(getattr(strategy_engine, "run", None)):
            raise TypeError("strategy_engine에는 호출 가능한 run() 메서드가 필요합니다.")
        if not callable(indicator_builder):
            raise TypeError("indicator_builder는 호출 가능한 함수여야 합니다.")
        if initial_cash <= 0:
            raise ValueError("initial_cash는 0보다 커야 합니다.")
        if minimum_data_length <= 0:
            raise ValueError("minimum_data_length는 1 이상이어야 합니다.")
        if commission_rate < 0 or slippage_rate < 0:
            raise ValueError("수수료율과 슬리피지는 0 이상이어야 합니다.")

        self.strategy_engine = strategy_engine
        self.indicator_builder = indicator_builder
        self.initial_cash = float(initial_cash)
        self.minimum_data_length = int(minimum_data_length)
        self.commission_rate = float(commission_rate)
        self.slippage_rate = float(slippage_rate)

    def run(self, stock_code: str, price_data: pd.DataFrame) -> BacktestResult:
        data = self._prepare_price_data(price_data)
        if len(data) <= self.minimum_data_length:
            raise ValueError(
                f"백테스트 데이터가 부족합니다. 현재 {len(data)}개, "
                f"최소 {self.minimum_data_length + 1}개가 필요합니다."
            )

        cash = self.initial_cash
        quantity = 0
        pending_signal: Signal | None = None
        trades: list[BacktestTrade] = []
        equity_curve: list[dict[str, Any]] = []

        for index, row in data.iterrows():
            current_date = str(row["date"])

            if pending_signal is not None:
                cash, quantity, trade = self._execute(
                    date=current_date,
                    open_price=float(row["open"]),
                    signal=pending_signal,
                    cash=cash,
                    quantity=quantity,
                )
                if trade is not None:
                    trades.append(trade)
                pending_signal = None

            close_price = float(row["close"])
            position_value = quantity * close_price
            equity_curve.append(
                {
                    "date": current_date,
                    "cash": cash,
                    "quantity": quantity,
                    "close": close_price,
                    "position_value": position_value,
                    "equity": cash + position_value,
                }
            )

            if index == len(data) - 1 or index + 1 < self.minimum_data_length:
                continue

            history = data.iloc[: index + 1].copy()
            indicator_data = self.indicator_builder(history)
            signal = self._extract_signal(self.strategy_engine.run(indicator_data))

            if signal == Signal.BUY and quantity == 0:
                pending_signal = Signal.BUY
            elif signal == Signal.SELL and quantity > 0:
                pending_signal = Signal.SELL

        last_close = float(data.iloc[-1]["close"])
        final_position_value = quantity * last_close
        final_equity = cash + final_position_value
        metrics = calculate_performance(
            equity_curve=equity_curve,
            trades=trades,
            initial_cash=self.initial_cash,
        )
        first_open = float(data.iloc[0]["open"])
        last_close = float(data.iloc[-1]["close"])

        buy_and_hold_return = (
            last_close / first_open - 1.0
        )

        metrics["buy_and_hold_return"] = (
            buy_and_hold_return
        )

        metrics["excess_return"] = (
            metrics["total_return"]
            - buy_and_hold_return
        )

        return BacktestResult(
            stock_code=stock_code,
            initial_cash=self.initial_cash,
            final_cash=cash,
            final_position_quantity=quantity,
            final_position_value=final_position_value,
            final_equity=final_equity,
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
        )

    def _execute(
        self,
        date: str,
        open_price: float,
        signal: Signal,
        cash: float,
        quantity: int,
    ) -> tuple[float, int, BacktestTrade | None]:
        if open_price <= 0:
            raise ValueError(f"{date}의 시가가 0 이하입니다.")

        if signal == Signal.BUY and quantity == 0:
            fill_price = open_price * (1.0 + self.slippage_rate)
            unit_cost = fill_price * (1.0 + self.commission_rate)
            buy_quantity = int(cash // unit_cost)
            if buy_quantity <= 0:
                return cash, quantity, None

            gross = fill_price * buy_quantity
            fee = gross * self.commission_rate
            cash_after = cash - gross - fee
            return cash_after, buy_quantity, BacktestTrade(
                date=date,
                side="BUY",
                price=fill_price,
                quantity=buy_quantity,
                gross_amount=gross,
                fee=fee,
                cash_after=cash_after,
                reason="전략 엔진 BUY 신호",
            )

        if signal == Signal.SELL and quantity > 0:
            fill_price = open_price * (1.0 - self.slippage_rate)
            gross = fill_price * quantity
            fee = gross * self.commission_rate
            cash_after = cash + gross - fee
            return cash_after, 0, BacktestTrade(
                date=date,
                side="SELL",
                price=fill_price,
                quantity=quantity,
                gross_amount=gross,
                fee=fee,
                cash_after=cash_after,
                reason="전략 엔진 SELL 신호",
            )

        return cash, quantity, None

    @classmethod
    def _prepare_price_data(cls, price_data: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(price_data, pd.DataFrame):
            raise TypeError("price_data는 pandas DataFrame이어야 합니다.")
        if price_data.empty:
            raise ValueError("price_data가 비어 있습니다.")

        missing = cls.REQUIRED_COLUMNS - set(price_data.columns)
        if missing:
            raise KeyError(f"필수 가격 컬럼이 없습니다: {sorted(missing)}")

        result = price_data.copy()
        result["date"] = result["date"].astype(str)
        for column in ("open", "high", "low", "close", "volume"):
            result[column] = pd.to_numeric(result[column], errors="raise")

        result = (
            result.sort_values("date")
            .drop_duplicates(subset=["date"], keep="last")
            .reset_index(drop=True)
        )
        if result[["open", "high", "low", "close"]].isna().any().any():
            raise ValueError("가격 데이터에 결측값이 있습니다.")
        return result

    @staticmethod
    def _extract_signal(strategy_result: Any) -> Signal:
        if isinstance(strategy_result, dict):
            raw_signal = strategy_result.get("final_signal")
        else:
            raw_signal = getattr(strategy_result, "final_signal", strategy_result)

        if isinstance(raw_signal, Signal):
            return raw_signal
        if isinstance(raw_signal, str):
            return Signal(raw_signal.upper())
        raise ValueError("전략 결과에서 final_signal을 확인할 수 없습니다.")
