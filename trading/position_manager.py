from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable


class PositionManagerError(Exception):
    """PositionManager에서 발생하는 기본 예외."""


class BalanceResponseError(PositionManagerError):
    """계좌 잔고 응답 형식이 올바르지 않을 때 발생하는 예외."""


@dataclass(frozen=True)
class Position:
    """
    계좌에 보유 중인 하나의 종목을 표현한다.

    Attributes
    ----------
    stock_code:
        종목 코드

    stock_name:
        종목명

    quantity:
        현재 보유 수량

    available_quantity:
        매도 가능한 수량

    average_price:
        평균 매입 단가

    purchase_amount:
        총 매입 금액

    current_price:
        현재가

    evaluation_amount:
        평가 금액

    profit_loss:
        평가 손익 금액

    profit_loss_rate:
        평가 손익률
    """

    stock_code: str
    stock_name: str
    quantity: int
    available_quantity: int
    average_price: Decimal
    purchase_amount: int
    current_price: int
    evaluation_amount: int
    profit_loss: int
    profit_loss_rate: Decimal

    @property
    def is_profitable(self) -> bool:
        """현재 평가손익이 양수인지 반환한다."""
        return self.profit_loss > 0

    @property
    def is_loss(self) -> bool:
        """현재 평가손익이 음수인지 반환한다."""
        return self.profit_loss < 0

    @property
    def can_sell(self) -> bool:
        """현재 매도 가능한 수량이 있는지 반환한다."""
        return self.available_quantity > 0


class PositionManager:
    """
    한국투자증권 계좌의 현재 보유 종목을 관리한다.

    PositionManager는 자체적으로 보유 수량을 변경하지 않는다.
    계좌 잔고 조회 API의 응답을 기준으로 포지션을 갱신한다.

    Parameters
    ----------
    balance_fetcher:
        계좌 잔고를 조회하는 함수.

        다음 반환 형식을 지원한다.

        1. get_account_balance()의 정규화된 응답

            {
                "cash": 1000000,
                "total_evaluation_amount": 2000000,
                "position_count": 1,
                "positions": [
                    {
                        "stock_code": "005930",
                        "stock_name": "삼성전자",
                        "quantity": 10,
                        ...
                    }
                ]
            }

        2. KIS 원본 응답

            {
                "rt_cd": "0",
                "output1": [...],
                "output2": [...]
            }

        3. 보유 종목 목록

            [
                {
                    "stock_code": "005930",
                    "quantity": 10,
                    ...
                }
            ]
    """

    def __init__(
        self,
        balance_fetcher: Callable[
            [],
            dict[str, Any] | list[dict[str, Any]],
        ],
    ) -> None:
        if not callable(balance_fetcher):
            raise TypeError(
                "balance_fetcher는 호출 가능한 함수여야 합니다."
            )

        self._balance_fetcher = balance_fetcher
        self._positions: dict[str, Position] = {}
        self._account_summary: dict[str, Any] = {}

    def refresh(self) -> dict[str, Position]:
        """
        계좌 잔고 API를 호출하여 포지션을 갱신한다.

        기존 포지션은 최신 API 응답으로 완전히 교체된다.
        전량 매도된 종목은 다음 refresh 호출 시 제거된다.

        Returns
        -------
        dict[str, Position]
            종목 코드를 키로 가지는 최신 포지션 딕셔너리
        """
        response = self._balance_fetcher()

        holdings, account_summary = self._extract_balance_data(
            response
        )

        refreshed_positions: dict[str, Position] = {}

        for holding in holdings:
            position = self._parse_position(holding)

            if position.quantity <= 0:
                continue

            refreshed_positions[position.stock_code] = position

        self._positions = refreshed_positions
        self._account_summary = account_summary

        return self.get_all_positions()

    def get_position(
        self,
        stock_code: str,
    ) -> Position | None:
        """
        특정 종목의 포지션을 반환한다.

        보유하지 않은 종목이면 None을 반환한다.
        """
        normalized_code = self._normalize_stock_code(
            stock_code
        )

        return self._positions.get(normalized_code)

    def get_all_positions(self) -> dict[str, Position]:
        """
        현재 보유 중인 모든 포지션을 복사하여 반환한다.

        내부 딕셔너리를 직접 반환하지 않아 외부 코드가
        PositionManager의 상태를 임의로 변경하지 못하게 한다.
        """
        return dict(self._positions)

    def has_position(self, stock_code: str) -> bool:
        """특정 종목을 현재 보유하고 있는지 반환한다."""
        return self.get_quantity(stock_code) > 0

    def get_quantity(self, stock_code: str) -> int:
        """특정 종목의 보유 수량을 반환한다."""
        position = self.get_position(stock_code)

        if position is None:
            return 0

        return position.quantity

    def get_available_quantity(
        self,
        stock_code: str,
    ) -> int:
        """특정 종목의 매도 가능 수량을 반환한다."""
        position = self.get_position(stock_code)

        if position is None:
            return 0

        return position.available_quantity

    def can_sell(
        self,
        stock_code: str,
        quantity: int,
    ) -> bool:
        """
        요청한 수량만큼 매도 가능한지 확인한다.

        Parameters
        ----------
        stock_code:
            종목 코드

        quantity:
            매도하려는 수량
        """
        self._validate_quantity(quantity)

        available_quantity = self.get_available_quantity(
            stock_code
        )

        return available_quantity >= quantity

    def validate_sell_quantity(
        self,
        stock_code: str,
        quantity: int,
    ) -> None:
        """
        요청한 매도 수량이 유효한지 검사한다.

        매도 가능 수량보다 많은 수량을 요청하면
        ValueError를 발생시킨다.
        """
        self._validate_quantity(quantity)

        normalized_code = self._normalize_stock_code(
            stock_code
        )

        available_quantity = self.get_available_quantity(
            normalized_code
        )

        if available_quantity < quantity:
            raise ValueError(
                f"{normalized_code}의 매도 가능 수량이 부족합니다. "
                f"요청 수량={quantity}, "
                f"매도 가능 수량={available_quantity}"
            )

    def get_total_purchase_amount(self) -> int:
        """전체 보유 종목의 총 매입 금액을 반환한다."""
        return sum(
            position.purchase_amount
            for position in self._positions.values()
        )

    def get_total_evaluation_amount(self) -> int:
        """전체 보유 종목의 총 평가 금액을 반환한다."""
        return sum(
            position.evaluation_amount
            for position in self._positions.values()
        )

    def get_total_profit_loss(self) -> int:
        """전체 보유 종목의 총 평가 손익을 반환한다."""
        return sum(
            position.profit_loss
            for position in self._positions.values()
        )

    def get_account_summary(self) -> dict[str, Any]:
        """
        계좌 요약 정보를 복사하여 반환한다.

        get_account_balance()의 cash, 총평가금액,
        총손익 등의 값이 저장된다.
        """
        return dict(self._account_summary)

    def clear(self) -> None:
        """
        메모리에 저장된 포지션과 계좌 요약을 초기화한다.

        실제 증권 계좌의 보유 종목에는 영향을 주지 않는다.
        """
        self._positions.clear()
        self._account_summary.clear()

    @staticmethod
    def _extract_balance_data(
        response: dict[str, Any] | list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        잔고 조회 결과에서 보유 종목과 계좌 요약을 추출한다.

        다음 형식을 모두 지원한다.

        1. get_account_balance()가 반환하는 정규화된 형식
        2. 한국투자증권 API 원본 응답 형식
        3. 보유 종목 리스트만 전달되는 형식
        """
        if isinstance(response, list):
            if not all(
                isinstance(item, dict)
                for item in response
            ):
                raise BalanceResponseError(
                    "잔고 목록의 각 항목은 "
                    "딕셔너리여야 합니다."
                )

            return response, {}

        if not isinstance(response, dict):
            raise BalanceResponseError(
                "잔고 조회 결과는 딕셔너리 또는 "
                "리스트여야 합니다."
            )

        # get_account_balance()가 반환하는 정규화된 응답
        if "positions" in response:
            positions = response.get("positions") or []

            if not isinstance(positions, list):
                raise BalanceResponseError(
                    "positions는 리스트여야 합니다."
                )

            if not all(
                isinstance(item, dict)
                for item in positions
            ):
                raise BalanceResponseError(
                    "positions의 각 항목은 "
                    "딕셔너리여야 합니다."
                )

            account_summary = {
                key: value
                for key, value in response.items()
                if key not in {
                    "positions",
                    "position_count",
                }
            }

            return positions, account_summary

        # KIS 원본 응답
        rt_cd = response.get("rt_cd")

        if rt_cd is not None and str(rt_cd) != "0":
            message = (
                response.get("msg1")
                or response.get("msg_cd")
                or "알 수 없는 오류"
            )

            raise BalanceResponseError(
                f"계좌 잔고 조회에 실패했습니다: "
                f"{message}"
            )

        holdings = response.get("output1", [])

        if holdings is None:
            holdings = []

        if not isinstance(holdings, list):
            raise BalanceResponseError(
                "잔고 응답의 output1은 리스트여야 합니다."
            )

        if not all(
            isinstance(item, dict)
            for item in holdings
        ):
            raise BalanceResponseError(
                "output1의 각 항목은 "
                "딕셔너리여야 합니다."
            )

        account_summary = (
            PositionManager._parse_account_summary(
                response.get("output2")
            )
        )

        return holdings, account_summary

    @staticmethod
    def _parse_account_summary(
        output2: Any,
    ) -> dict[str, Any]:
        """KIS 원본 output2에서 계좌 요약 한 건을 추출한다."""
        if output2 is None:
            return {}

        if isinstance(output2, dict):
            return dict(output2)

        if isinstance(output2, list):
            if not output2:
                return {}

            first_item = output2[0]

            if not isinstance(first_item, dict):
                raise BalanceResponseError(
                    "output2의 첫 번째 항목은 "
                    "딕셔너리여야 합니다."
                )

            return dict(first_item)

        raise BalanceResponseError(
            "잔고 응답의 output2 형식이 "
            "올바르지 않습니다."
        )

    @classmethod
    def _parse_position(
        cls,
        holding: dict[str, Any],
    ) -> Position:
        """
        잔고 한 행을 Position 객체로 변환한다.

        KIS 원본 필드와 get_account_balance()에서
        정규화한 필드를 모두 지원한다.
        """
        stock_code = cls._normalize_stock_code(
            holding.get("pdno")
            or holding.get("stock_code")
            or ""
        )

        if not stock_code:
            raise BalanceResponseError(
                "보유 종목 데이터에 종목 코드가 없습니다."
            )

        quantity = cls._first_int(
            holding,
            "hldg_qty",
            "quantity",
            default=0,
        )

        available_quantity = cls._first_int(
            holding,
            "ord_psbl_qty",
            "sellable_quantity",
            "available_quantity",
            default=quantity,
        )

        return Position(
            stock_code=stock_code,
            stock_name=str(
                holding.get("prdt_name")
                or holding.get("stock_name")
                or ""
            ).strip(),
            quantity=quantity,
            available_quantity=available_quantity,
            average_price=cls._first_decimal(
                holding,
                "pchs_avg_pric",
                "avg_price",
                "average_price",
                default=Decimal("0"),
            ),
            purchase_amount=cls._first_int(
                holding,
                "pchs_amt",
                "purchase_amount",
                default=0,
            ),
            current_price=cls._first_int(
                holding,
                "prpr",
                "current_price",
                default=0,
            ),
            evaluation_amount=cls._first_int(
                holding,
                "evlu_amt",
                "evaluation_amount",
                default=0,
            ),
            profit_loss=cls._first_int(
                holding,
                "evlu_pfls_amt",
                "profit_loss",
                default=0,
            ),
            profit_loss_rate=cls._first_decimal(
                holding,
                "evlu_pfls_rt",
                "profit_rate",
                "profit_loss_rate",
                default=Decimal("0"),
            ),
        )

    @classmethod
    def _first_int(
        cls,
        data: dict[str, Any],
        *keys: str,
        default: int = 0,
    ) -> int:
        """
        여러 키 중 실제로 존재하는 첫 번째 값을 int로 변환한다.

        값이 0인 경우에도 누락된 값으로 처리하지 않는다.
        """
        for key in keys:
            if key not in data:
                continue

            value = data[key]

            if value is None or value == "":
                continue

            return cls._to_int(value)

        return default

    @classmethod
    def _first_decimal(
        cls,
        data: dict[str, Any],
        *keys: str,
        default: Decimal = Decimal("0"),
    ) -> Decimal:
        """
        여러 키 중 실제로 존재하는 첫 번째 값을 Decimal로 변환한다.

        값이 0인 경우에도 누락된 값으로 처리하지 않는다.
        """
        for key in keys:
            if key not in data:
                continue

            value = data[key]

            if value is None or value == "":
                continue

            return cls._to_decimal(value)

        return default

    @staticmethod
    def _normalize_stock_code(
        stock_code: Any,
    ) -> str:
        """
        종목 코드를 문자열로 정규화한다.

        숫자로 전달된 경우 앞자리를 0으로 채워
        6자리로 변환한다.
        """
        if stock_code is None:
            return ""

        normalized = str(stock_code).strip()

        if normalized.isdigit():
            return normalized.zfill(6)

        return normalized

    @staticmethod
    def _to_int(value: Any) -> int:
        """
        문자열 숫자를 int로 변환한다.

        쉼표와 소수점이 포함된 문자열도 처리한다.
        """
        if value is None or value == "":
            return 0

        try:
            normalized = (
                str(value)
                .replace(",", "")
                .strip()
            )

            return int(Decimal(normalized))

        except (
            InvalidOperation,
            ValueError,
            TypeError,
        ) as error:
            raise BalanceResponseError(
                f"정수로 변환할 수 없는 값입니다: "
                f"{value}"
            ) from error

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        """문자열 숫자를 Decimal로 변환한다."""
        if value is None or value == "":
            return Decimal("0")

        try:
            normalized = (
                str(value)
                .replace(",", "")
                .strip()
            )

            return Decimal(normalized)

        except (
            InvalidOperation,
            ValueError,
            TypeError,
        ) as error:
            raise BalanceResponseError(
                f"숫자로 변환할 수 없는 값입니다: "
                f"{value}"
            ) from error

    @staticmethod
    def _validate_quantity(quantity: int) -> None:
        """주문 수량이 양의 정수인지 검사한다."""
        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, int)
        ):
            raise TypeError(
                "수량은 정수여야 합니다."
            )

        if quantity <= 0:
            raise ValueError(
                "수량은 1 이상이어야 합니다."
            )