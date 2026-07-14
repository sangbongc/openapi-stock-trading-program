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
        stop_loss_rate: float | None = 0.08,
        trailing_stop_rate: float | None = 0.10,
        stop_reentry_cooldown_days: int = 5,
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
        for name, rate in (
            ("stop_loss_rate", stop_loss_rate),
            ("trailing_stop_rate", trailing_stop_rate),
        ):
            if rate is not None and not 0 < rate < 1:
                raise ValueError(f"{name}는 None 또는 0과 1 사이여야 합니다.")
        if (
            not isinstance(stop_reentry_cooldown_days, int)
            or isinstance(stop_reentry_cooldown_days, bool)
            or stop_reentry_cooldown_days < 0
        ):
            raise ValueError("stop_reentry_cooldown_days는 0 이상의 정수여야 합니다.")

        self.strategy_engine = strategy_engine
        self.indicator_builder = indicator_builder
        self.initial_cash = float(initial_cash)
        self.minimum_data_length = int(minimum_data_length)
        self.commission_rate = float(commission_rate)
        self.slippage_rate = float(slippage_rate)
        self.stop_loss_rate = stop_loss_rate
        self.trailing_stop_rate = trailing_stop_rate
        self.stop_reentry_cooldown_days = stop_reentry_cooldown_days

    def run(self, stock_code: str, price_data: pd.DataFrame) -> BacktestResult:
        data = self._prepare_price_data(price_data)
        if len(data) <= self.minimum_data_length:
            raise ValueError(
                f"백테스트 데이터가 부족합니다. 현재 {len(data)}개, "
                f"최소 {self.minimum_data_length + 1}개가 필요합니다."
            )

        # 모든 지표는 과거와 현재 행만 사용하는 rolling/ewm 계산이므로
        # 전체 기간에 대해 한 번 계산해도 미래 데이터 누출이 발생하지 않는다.
        # 기존처럼 거래일마다 처음부터 재계산하면 데이터 길이가 늘어날수록
        # 계산량이 O(n²)에 가까워지므로 백테스트가 급격히 느려진다.
        indicator_data = self.indicator_builder(data)
        if not isinstance(indicator_data, pd.DataFrame):
            raise TypeError("indicator_builder는 pandas DataFrame을 반환해야 합니다.")
        if len(indicator_data) != len(data):
            raise ValueError(
                "indicator_builder는 입력 데이터의 행 개수를 변경할 수 없습니다."
            )

        cash = self.initial_cash
        quantity = 0
        entry_price: float | None = None
        highest_price: float | None = None
        reentry_allowed_index = 0
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
                    if trade.side == "BUY":
                        entry_price = trade.price
                        highest_price = trade.price
                    else:
                        entry_price = None
                        highest_price = None
                pending_signal = None

            # 전일까지 확정된 최고가로 보호 손절선을 먼저 계산한다.
            # 당일 고가를 먼저 반영하면 실제 장중에 저가가 고가보다 먼저
            # 발생했을 가능성을 무시하게 되므로 미래 정보가 섞일 수 있다.
            if quantity > 0 and entry_price is not None:
                stop_price, stop_reason = self._get_protective_stop(
                    entry_price=entry_price,
                    highest_price=highest_price or entry_price,
                )
                if stop_price is not None and float(row["low"]) <= stop_price:
                    execution_price = min(float(row["open"]), stop_price)
                    cash, quantity, trade = self._execute(
                        date=current_date,
                        open_price=execution_price,
                        signal=Signal.SELL,
                        cash=cash,
                        quantity=quantity,
                        reason=stop_reason,
                    )
                    if trade is not None:
                        trades.append(trade)
                        reentry_allowed_index = (
                            index + self.stop_reentry_cooldown_days
                        )
                    entry_price = None
                    highest_price = None

            if quantity > 0:
                day_high = float(row["high"])
                highest_price = max(highest_price or day_high, day_high)

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

            # 현재 거래일까지의 행만 전략에 전달하여 미래 데이터 접근을 막는다.
            history_with_indicators = indicator_data.iloc[: index + 1]
            signal = self._extract_signal(
                self.strategy_engine.run(history_with_indicators)
            )

            if (
                signal == Signal.BUY
                and quantity == 0
                and index >= reentry_allowed_index
            ):
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
        reason: str | None = None,
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
                reason=reason or "전략 엔진 BUY 신호",
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
                reason=reason or "전략 엔진 SELL 신호",
            )

        return cash, quantity, None

    def _get_protective_stop(
        self,
        entry_price: float,
        highest_price: float,
    ) -> tuple[float | None, str]:
        """고정 손절선과 추적 손절선 중 더 높은 가격을 반환한다."""
        candidates: list[tuple[float, str]] = []

        if self.stop_loss_rate is not None:
            candidates.append(
                (
                    entry_price * (1.0 - self.stop_loss_rate),
                    f"고정 손절(-{self.stop_loss_rate * 100:.1f}%)",
                )
            )

        if self.trailing_stop_rate is not None:
            candidates.append(
                (
                    highest_price * (1.0 - self.trailing_stop_rate),
                    f"추적 손절(-{self.trailing_stop_rate * 100:.1f}%)",
                )
            )

        if not candidates:
            return None, ""

        return max(candidates, key=lambda item: item[0])

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