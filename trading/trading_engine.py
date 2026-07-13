from __future__ import annotations

from typing import Any, Callable, Iterable

import pandas as pd

from strategies.signal import Signal


class TradingEngine:
    """
    전략 신호와 현재 포지션을 바탕으로
    실제 주문 여부를 결정하는 최상위 매매 조정자다.

    TradingEngine의 책임
    --------------------
    1. 종목의 가격 및 지표 데이터 준비
    2. StrategyEngine 실행
    3. 현재 포지션 확인
    4. BUY / SELL / HOLD 처리
    5. OrderManager를 통한 주문 요청

    체결 확인과 포지션 갱신은 ExecutionManager와
    PositionManager가 담당한다.
    """

    def __init__(
        self,
        strategy_engine: Any,
        order_manager: Any,
        position_manager: Any,
        data_provider: Callable[[str], pd.DataFrame],
        default_buy_quantity: int = 1,
        pending_order_checker: Callable[[str], bool] | None = None,
        minimum_data_length: int = 120,
        dry_run: bool = True,
    ):
        if not isinstance(dry_run, bool):
            raise TypeError("dry_run은 bool 타입이어야 합니다.")

        self.dry_run = dry_run
        
        if not isinstance(default_buy_quantity, int):
            raise TypeError(
                "default_buy_quantity는 정수여야 합니다."
            )

        if default_buy_quantity <= 0:
            raise ValueError(
                "default_buy_quantity는 1 이상이어야 합니다."
            )

        if not isinstance(minimum_data_length, int):
            raise TypeError(
                "minimum_data_length는 정수여야 합니다."
            )

        if minimum_data_length <= 0:
            raise ValueError(
                "minimum_data_length는 1 이상이어야 합니다."
            )

        if not callable(data_provider):
            raise TypeError(
                "data_provider는 호출 가능한 함수여야 합니다."
            )

        if (
            pending_order_checker is not None
            and not callable(pending_order_checker)
        ):
            raise TypeError(
                "pending_order_checker는 호출 가능한 함수여야 합니다."
            )

        self.strategy_engine = strategy_engine
        self.order_manager = order_manager
        self.position_manager = position_manager
        self.data_provider = data_provider

        self.default_buy_quantity = default_buy_quantity
        self.pending_order_checker = pending_order_checker
        self.minimum_data_length = minimum_data_length

    def run_stock(self, stock_code: str) -> dict[str, Any]:
        """
        한 종목에 대해 전략을 실행하고 주문 여부를 결정한다.

        Parameters
        ----------
        stock_code : str
            종목 코드

        Returns
        -------
        dict
            전략 결과, 주문 여부, 처리 사유 등을 포함한 결과
        """
        self._validate_stock_code(stock_code)

        try:
            data = self.data_provider(stock_code)
        except Exception as error:
            return self._build_result(
                stock_code=stock_code,
                signal=Signal.HOLD,
                action="ERROR",
                ordered=False,
                reason=(
                    "가격 데이터를 준비하는 중 오류가 "
                    f"발생했습니다: {error}"
                ),
            )

        data_error = self._validate_data(data)

        if data_error is not None:
            return self._build_result(
                stock_code=stock_code,
                signal=Signal.HOLD,
                action="SKIP",
                ordered=False,
                reason=data_error,
            )

        if self._has_pending_order(stock_code):
            return self._build_result(
                stock_code=stock_code,
                signal=Signal.HOLD,
                action="SKIP",
                ordered=False,
                reason=(
                    "현재 처리 중인 주문이 있어 "
                    "새 주문을 생성하지 않았습니다."
                ),
            )

        try:
            strategy_result = self.strategy_engine.run(data)
        except Exception as error:
            return self._build_result(
                stock_code=stock_code,
                signal=Signal.HOLD,
                action="ERROR",
                ordered=False,
                reason=(
                    "전략을 실행하는 중 오류가 "
                    f"발생했습니다: {error}"
                ),
            )

        signal = self._extract_signal(strategy_result)

        try:
            quantity = self._get_position_quantity(stock_code)
        except Exception as error:
            return self._build_result(
                stock_code=stock_code,
                signal=signal,
                action="ERROR",
                ordered=False,
                reason=(
                    "현재 포지션을 조회하는 중 오류가 "
                    f"발생했습니다: {error}"
                ),
                strategy_result=strategy_result,
            )

        if signal == Signal.BUY:
            return self._handle_buy(
                stock_code=stock_code,
                current_quantity=quantity,
                strategy_result=strategy_result,
            )

        if signal == Signal.SELL:
            return self._handle_sell(
                stock_code=stock_code,
                current_quantity=quantity,
                strategy_result=strategy_result,
            )

        return self._build_result(
            stock_code=stock_code,
            signal=Signal.HOLD,
            action="HOLD",
            ordered=False,
            reason="최종 전략 신호가 HOLD입니다.",
            strategy_result=strategy_result,
        )
    def run_all(
            self,
            stocks: Iterable[str | dict[str, Any]],
        ) -> list[dict[str, Any]]:
            """
            여러 종목을 순차적으로 실행한다.

            하나의 종목에서 오류가 발생하더라도
            나머지 종목은 계속 처리한다.

            Parameters
            ----------
            stocks : Iterable[str | dict]
                종목 코드 문자열 또는 종목 정보를 담은 딕셔너리 목록

                문자열 예시:
                [
                    "005930",
                    "000660",
                ]

                딕셔너리 예시:
                [
                    {
                        "stock_code": "005930",
                        "name": "삼성전자",
                    },
                    {
                        "stock_code": "000660",
                        "name": "SK하이닉스",
                    },
                ]

            Returns
            -------
            list[dict]
                각 종목의 TradingEngine 실행 결과
            """
            if stocks is None:
                raise TypeError(
                    "stocks는 None일 수 없습니다."
                )

            if isinstance(stocks, (str, bytes)):
                raise TypeError(
                    "stocks에는 종목 목록을 전달해야 합니다."
                )

            results: list[dict[str, Any]] = []

            for stock in stocks:
                stock_code, stock_name = (
                    self._extract_stock_info(stock)
                )

                try:
                    result = self.run_stock(stock_code)

                except Exception as error:
                    result = self._build_result(
                        stock_code=stock_code,
                        signal=Signal.HOLD,
                        action="ERROR",
                        ordered=False,
                        reason=(
                            "종목을 실행하는 중 예상하지 못한 "
                            f"오류가 발생했습니다: {error}"
                        ),
                    )

                if stock_name is not None:
                    result["stock_name"] = stock_name

                results.append(result)

            return results
    
    def _handle_buy(
        self,
        stock_code: str,
        current_quantity: int,
        strategy_result: Any,
    ) -> dict[str, Any]:
        """
        BUY 신호를 처리한다.
        """
        if current_quantity > 0:
            return self._build_result(
                stock_code=stock_code,
                signal=Signal.BUY,
                action="SKIP",
                ordered=False,
                reason=(
                    f"이미 {current_quantity}주를 보유하고 있어 "
                    "추가 매수하지 않았습니다."
                ),
                strategy_result=strategy_result,
            )
        if self.dry_run:
            return self._build_result(
                stock_code=stock_code,
                signal=Signal.BUY,
                action="BUY_SIMULATED",
                ordered=False,
                reason=(
                    f"Dry-run 모드입니다. "
                    f"{self.default_buy_quantity}주 매수 주문을 "
                    "실제로 전송하지 않았습니다."
                ),
                strategy_result=strategy_result,
            )

        try:
            order_result = self.order_manager.buy(
                stock_code=stock_code,
                quantity=self.default_buy_quantity,
                order_type="MARKET",
            )
        except Exception as error:
            return self._build_result(
                stock_code=stock_code,
                signal=Signal.BUY,
                action="BUY_ERROR",
                ordered=False,
                reason=f"매수 주문 중 오류가 발생했습니다: {error}",
                strategy_result=strategy_result,
            )

        accepted = self._is_order_accepted(order_result)

        if not accepted:
            return self._build_result(
                stock_code=stock_code,
                signal=Signal.BUY,
                action="BUY_REJECTED",
                ordered=False,
                reason="매수 주문이 접수되지 않았습니다.",
                order_result=order_result,
                strategy_result=strategy_result,
            )

        return self._build_result(
            stock_code=stock_code,
            signal=Signal.BUY,
            action="BUY_ORDER",
            ordered=True,
            reason=(
                f"{self.default_buy_quantity}주 매수 주문이 "
                "정상적으로 접수되었습니다."
            ),
            order_result=order_result,
            strategy_result=strategy_result,
        )

    def _handle_sell(
        self,
        stock_code: str,
        current_quantity: int,
        strategy_result: Any,
    ) -> dict[str, Any]:
        """
        SELL 신호를 처리한다.
        """
        if current_quantity <= 0:
            return self._build_result(
                stock_code=stock_code,
                signal=Signal.SELL,
                action="SKIP",
                ordered=False,
                reason=(
                    "현재 보유 수량이 없어 "
                    "매도 주문을 생성하지 않았습니다."
                ),
                strategy_result=strategy_result,
            )
        if self.dry_run:
            return self._build_result(
                stock_code=stock_code,
                signal=Signal.SELL,
                action="SELL_SIMULATED",
                ordered=False,
                reason=(
                    f"Dry-run 모드입니다. "
                    f"보유 수량 {current_quantity}주의 매도 주문을 "
                    "실제로 전송하지 않았습니다."
                ),
                strategy_result=strategy_result,
            )
        try:
            order_result = self.order_manager.sell(
                stock_code=stock_code,
                quantity=current_quantity,
                order_type="MARKET",
            )
        except Exception as error:
            return self._build_result(
                stock_code=stock_code,
                signal=Signal.SELL,
                action="SELL_ERROR",
                ordered=False,
                reason=f"매도 주문 중 오류가 발생했습니다: {error}",
                strategy_result=strategy_result,
            )

        accepted = self._is_order_accepted(order_result)

        if not accepted:
            return self._build_result(
                stock_code=stock_code,
                signal=Signal.SELL,
                action="SELL_REJECTED",
                ordered=False,
                reason="매도 주문이 접수되지 않았습니다.",
                order_result=order_result,
                strategy_result=strategy_result,
            )

        return self._build_result(
            stock_code=stock_code,
            signal=Signal.SELL,
            action="SELL_ORDER",
            ordered=True,
            reason=(
                f"보유 수량 {current_quantity}주의 매도 주문이 "
                "정상적으로 접수되었습니다."
            ),
            order_result=order_result,
            strategy_result=strategy_result,
        )

    def _validate_data(
        self,
        data: Any,
    ) -> str | None:
        """
        전략 실행 전에 데이터 상태를 검증한다.
        """
        if not isinstance(data, pd.DataFrame):
            return "data_provider가 DataFrame을 반환하지 않았습니다."

        if data.empty:
            return "가격 데이터가 존재하지 않습니다."

        if len(data) < self.minimum_data_length:
            return (
                "전략 계산에 필요한 데이터가 부족합니다. "
                f"현재 {len(data)}개, "
                f"최소 {self.minimum_data_length}개가 필요합니다."
            )

        if "close" not in data.columns:
            return "가격 데이터에 close 컬럼이 존재하지 않습니다."

        if data["close"].isna().any():
            return "종가 데이터에 결측값이 존재합니다."

        return None

    def _get_position_quantity(
        self,
        stock_code: str,
    ) -> int:
        """
        PositionManager에서 현재 보유 수량을 가져온다.

        반환값이 None이면 미보유로 간주한다.
        """
        position = self.position_manager.get_position(stock_code)

        if position is None:
            return 0

        if isinstance(position, dict):
            quantity = position.get("quantity", 0)
        else:
            quantity = getattr(position, "quantity", 0)

        if quantity is None:
            return 0

        quantity = int(quantity)

        if quantity < 0:
            raise ValueError(
                "포지션 보유 수량은 음수일 수 없습니다."
            )

        return quantity

    def _has_pending_order(
        self,
        stock_code: str,
    ) -> bool:
        """
        처리 중인 주문이 있는지 확인한다.

        첫 버전에서는 검사 함수가 전달되지 않은 경우
        미체결 주문이 없는 것으로 간주한다.
        """
        if self.pending_order_checker is None:
            return False

        return bool(
            self.pending_order_checker(stock_code)
        )

    @staticmethod
    def _extract_signal(
        strategy_result: Any,
    ) -> Signal:
        """
        StrategyEngine 결과에서 최종 신호를 추출한다.

        지원 형식
        ---------
        1. EngineResult처럼 final_signal 속성을 가진 객체
        2. final_signal 키를 가진 딕셔너리
        3. Signal 객체
        4. BUY / SELL / HOLD 문자열
        """
        if hasattr(strategy_result, "final_signal"):
            signal = strategy_result.final_signal

        elif isinstance(strategy_result, dict):
            signal = strategy_result.get("final_signal")

        else:
            signal = strategy_result

        if isinstance(signal, Signal):
            return signal

        if isinstance(signal, str):
            try:
                return Signal(signal.upper())

            except ValueError as error:
                raise ValueError(
                    f"지원하지 않는 전략 신호입니다: {signal}"
                ) from error

        raise ValueError(
            "전략 결과에서 final_signal을 확인할 수 없습니다."
        )
    @staticmethod
    def _is_order_accepted(
        order_result: Any,
    ) -> bool:
        """
        OrderManager 결과에서 주문 접수 성공 여부를 확인한다.
        """
        if not isinstance(order_result, dict):
            return False

        return (
            order_result.get("success") is True
            and order_result.get("status") == "ACCEPTED"
        )

    @staticmethod
    def _validate_stock_code(
        stock_code: str,
    ) -> None:
        """
        국내 주식 종목 코드 형식을 검증한다.
        """
        if not isinstance(stock_code, str):
            raise TypeError("stock_code는 문자열이어야 합니다.")

        if len(stock_code) != 6 or not stock_code.isdigit():
            raise ValueError(
                "stock_code는 숫자로 이루어진 "
                "6자리 문자열이어야 합니다."
            )

    @staticmethod
    def _build_result(
        stock_code: str,
        signal: Signal,
        action: str,
        ordered: bool,
        reason: str,
        order_result: Any = None,
        strategy_result: Any = None,
    ) -> dict[str, Any]:
        """
        TradingEngine의 반환 형식을 통일한다.
        """
        return {
            "stock_code": stock_code,
            "signal": signal,
            "action": action,
            "ordered": ordered,
            "reason": reason,
            "order_result": order_result,
            "strategy_result": strategy_result,
        }
    @staticmethod
    def _extract_stock_info(
        stock: str | dict[str, Any],
    ) -> tuple[str, str | None]:
        """
        종목 코드 문자열 또는 종목 정보 딕셔너리에서
        종목 코드와 종목명을 추출한다.
        """
        if isinstance(stock, str):
            return stock, None

        if not isinstance(stock, dict):
            raise TypeError(
                "각 종목은 종목 코드 문자열 또는 "
                "딕셔너리여야 합니다."
            )

        stock_code = stock.get("stock_code")

        if stock_code is None:
            stock_code = stock.get("code")

        stock_name = stock.get("name")

        if stock_code is None:
            raise ValueError(
                "종목 정보에 stock_code 또는 "
                "code가 존재하지 않습니다."
            )

        return str(stock_code), stock_name