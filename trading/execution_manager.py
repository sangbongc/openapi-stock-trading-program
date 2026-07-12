from __future__ import annotations
from datetime import datetime
from dataclasses import dataclass
from typing import Any,Callable
from trading.position_manager import PositionManager

from api import inquire_daily_orders
from database import (
    fetch_open_orders,
    fetch_order_by_order_no,
    update_order_execution,
    save_execution
)


@dataclass(frozen=True)
class ExecutionResult:
    """
    체결 동기화 결과를 표현하는 객체.
    """

    order_no: str
    stock_code: str
    side: str
    ordered_quantity: int
    filled_quantity: int
    remaining_quantity: int
    average_price: float
    status: str
    changed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_no": self.order_no,
            "stock_code": self.stock_code,
            "side": self.side,
            "ordered_quantity": self.ordered_quantity,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "average_price": self.average_price,
            "status": self.status,
            "changed": self.changed,
        }


class ExecutionManager:
    """
    한국투자증권 서버의 주문체결 내역과
    로컬 orders 테이블을 동기화한다.
    """
    def __init__(
        self,
        position_refresher: Callable[[], Any] | None = None, position_manager: PositionManager | None = None,
    ) -> None:
        if (
            position_refresher is not None
            and not callable(position_refresher)
        ):
            raise TypeError(
                "position_refresher는 호출 가능한 함수여야 합니다."
            )

        self._position_refresher = position_refresher
        self.position_manager = position_manager
    FINAL_STATUSES = {
        "FILLED",
        "CANCELLED",
        "REJECTED",
    }

    def sync_order(
        self,
        order_no: str,
    ) -> dict[str, Any]:
        """
        주문 한 건의 최신 누적 체결 상태를 조회한다.

        이전 누적 체결수량보다 증가한 수량만 executions
        테이블에 새 체결로 저장하고 orders 테이블을 갱신한다.
        """
        local_order = fetch_order_by_order_no(order_no)

        if local_order is None:
            raise ValueError(
                f"로컬 DB에서 주문번호 {order_no}를 "
                "찾을 수 없습니다."
            )

        if local_order["status"] != "ACCEPTED":
            raise ValueError(
                "증권사에 접수된 주문만 체결 조회할 수 있습니다."
            )

        response = inquire_daily_orders(
            order_no=order_no,
            stock_code=local_order["stock_code"],
            side=local_order["side"],
            executed_only=False,
        )

        rows = response.get("output1") or []

        matched_rows = [
            row
            for row in rows
            if self._normalize_order_no(
                row.get("odno")
                or row.get("ODNO")
                or ""
            )
            == self._normalize_order_no(order_no)
        ]

        if not matched_rows:
            return self._build_not_found_result(local_order)

        execution_data = self._aggregate_execution_rows(
            rows=matched_rows,
            local_order=local_order,
        )

        previous_filled_quantity = int(
            local_order.get("filled_quantity") or 0
        )

        previous_average_fill_price = float(
            local_order.get("average_fill_price") or 0
        )

        previous_execution_status = str(
            local_order.get("execution_status") or "PENDING"
        )

        current_filled_quantity = int(
            execution_data["filled_quantity"]
        )

        current_average_fill_price = float(
            execution_data["average_fill_price"]
        )

        current_execution_status = str(
            execution_data["execution_status"]
        )

        remaining_quantity = int(
            execution_data["remaining_quantity"]
        )

        newly_filled_quantity = (
            current_filled_quantity
            - previous_filled_quantity
        )

        if newly_filled_quantity < 0:
            raise RuntimeError(
                "증권사 누적 체결수량이 로컬 DB보다 작습니다. "
                "주문 데이터를 확인해야 합니다."
            )

        execution_id = None
        new_fill_price = 0.0

        if newly_filled_quantity > 0:
            new_fill_price = self._calculate_new_fill_price(
                previous_filled_quantity=(
                    previous_filled_quantity
                ),
                previous_average_fill_price=(
                    previous_average_fill_price
                ),
                current_filled_quantity=(
                    current_filled_quantity
                ),
                current_average_fill_price=(
                    current_average_fill_price
                ),
            )

            executed_at = self._extract_executed_at(
                matched_rows
            )

            execution_id = save_execution(
                order_id=int(local_order["id"]),
                order_no=str(local_order["order_no"]),
                stock_code=str(local_order["stock_code"]),
                side=str(local_order["side"]),
                quantity=newly_filled_quantity,
                price=new_fill_price,
                executed_at=executed_at,
            )

        changed = (
            newly_filled_quantity > 0
            or previous_execution_status
            != current_execution_status
            or previous_average_fill_price
            != current_average_fill_price
        )

        if changed:
            update_order_execution(
                order_no=order_no,
                filled_quantity=current_filled_quantity,
                remaining_quantity=remaining_quantity,
                average_fill_price=current_average_fill_price,
                execution_status=current_execution_status,
            )
        position_refreshed = False
        position_refresh_error = None

        if (
            newly_filled_quantity > 0
            and self._position_refresher is not None
        ):
            try:
                self._position_refresher()
                position_refreshed = True

            except Exception as exc:
                position_refresh_error = str(exc)    

        return {
            "order_no": str(order_no),
            "stock_code": str(local_order["stock_code"]),
            "side": str(local_order["side"]),
            "ordered_quantity": int(local_order["quantity"]),
            "previous_filled_quantity": (
                previous_filled_quantity
            ),
            "filled_quantity": current_filled_quantity,
            "newly_filled_quantity": newly_filled_quantity,
            "remaining_quantity": remaining_quantity,
            "average_fill_price": (
                current_average_fill_price
            ),
            "new_fill_price": new_fill_price,
            "execution_status": current_execution_status,
            "execution_id": execution_id,
            "changed": changed,
            "position_refreshed": position_refreshed,
            "position_refresh_error": position_refresh_error,
        }
    def sync_open_orders(
        self,
    ) -> list[dict[str, Any]]:
        """
        PENDING 또는 PARTIAL 상태인 주문을 모두 동기화한다.

        한 주문의 조회가 실패하더라도 나머지 주문은 계속 처리한다.
        """
        open_orders = fetch_open_orders()
        results: list[dict[str, Any]] = []

        for order in open_orders:
            order_no = str(order["order_no"])

            try:
                result = self.sync_order(order_no)
                results.append(result)

            except Exception as exc:
                results.append(
                    {
                        "order_no": order_no,
                        "stock_code": order.get(
                            "stock_code",
                            "",
                        ),
                        "execution_status": "ERROR",
                        "changed": False,
                        "error": str(exc),
                    }
                )

        return results

    def _aggregate_execution_rows(
        self,
        rows: list[dict[str, Any]],
        local_order: dict[str, Any],
    ) -> dict[str, Any]:
        """
        체결 조회 API 응답을 하나의 누적 체결 상태로 정리한다.

        Returns
        -------
        dict
            ordered_quantity
            filled_quantity
            remaining_quantity
            average_fill_price
            execution_status
        """
        ordered_quantity = int(local_order["quantity"])

        filled_quantity = 0
        average_fill_price = 0.0

        is_cancelled = False
        is_rejected = False

        for row in rows:
            row_filled_quantity = self._to_int(
                row.get("tot_ccld_qty")
                or row.get("TOT_CCLD_QTY")
                or row.get("ccld_qty")
                or row.get("CCLD_QTY")
                or 0
            )

            row_average_fill_price = self._to_float(
                row.get("avg_prvs")
                or row.get("AVG_PRVS")
                or row.get("avg_pric")
                or row.get("AVG_PRIC")
                or 0
            )

            # API 응답이 누적 체결수량과 누적 평균체결가를 제공한다는
            # 전제에서 가장 큰 누적 체결수량의 행을 사용한다.
            if row_filled_quantity >= filled_quantity:
                filled_quantity = row_filled_quantity
                average_fill_price = row_average_fill_price

            cancel_flag = str(
                row.get("cncl_yn")
                or row.get("CNCL_YN")
                or ""
            ).upper().strip()

            order_status_name = str(
                row.get("ord_dvsn_name")
                or row.get("ORD_DVSN_NAME")
                or ""
            ).strip()

            reject_reason = str(
                row.get("rjct_rson")
                or row.get("RJCT_RSON")
                or ""
            ).strip()

            if cancel_flag == "Y" or "취소" in order_status_name:
                is_cancelled = True

            if reject_reason:
                is_rejected = True

        filled_quantity = min(
            filled_quantity,
            ordered_quantity,
        )

        remaining_quantity = max(
            ordered_quantity - filled_quantity,
            0,
        )

        execution_status = (
            self._determine_execution_status(
                ordered_quantity=ordered_quantity,
                filled_quantity=filled_quantity,
                is_cancelled=is_cancelled,
                is_rejected=is_rejected,
            )
        )

        return {
            "ordered_quantity": ordered_quantity,
            "filled_quantity": filled_quantity,
            "remaining_quantity": remaining_quantity,
            "average_fill_price": average_fill_price,
            "execution_status": execution_status,
    }

    @staticmethod
    def _determine_execution_status(
        ordered_quantity: int,
        filled_quantity: int,
        is_cancelled: bool,
        is_rejected: bool,
    ) -> str:
        """
        주문수량과 누적 체결수량으로 체결 상태를 결정한다.
        """
        if is_rejected and filled_quantity == 0:
            return "REJECTED"

        if filled_quantity >= ordered_quantity:
            return "FILLED"

        if is_cancelled:
            return "CANCELLED"

        if filled_quantity > 0:
            return "PARTIAL"

        return "PENDING"

    def _build_not_found_result(
        self,
        local_order: dict[str, Any],
    ) -> dict[str, Any]:
        """
        증권사 조회 결과에서 주문을 아직 찾지 못한 경우
        로컬 주문 상태를 그대로 유지한다.
        """
        ordered_quantity = int(local_order["quantity"])
        filled_quantity = int(
            local_order.get("filled_quantity") or 0
        )

        return {
            "order_no": str(local_order["order_no"]),
            "stock_code": str(local_order["stock_code"]),
            "side": str(local_order["side"]),
            "ordered_quantity": ordered_quantity,
            "previous_filled_quantity": filled_quantity,
            "filled_quantity": filled_quantity,
            "newly_filled_quantity": 0,
            "remaining_quantity": int(
                local_order.get("remaining_quantity")
                or ordered_quantity - filled_quantity
            ),
            "average_fill_price": float(
                local_order.get("average_fill_price") or 0
            ),
            "new_fill_price": 0.0,
            "execution_status": str(
                local_order.get("execution_status")
                or "PENDING"
            ),
            "execution_id": None,
            "changed": False,
            "position_refreshed": False,
            "position_refresh_error": None,
            "message": (
                "증권사 체결 조회 결과에서 주문을 찾지 못해 "
                "기존 상태를 유지했습니다."
            ),
        }

    @staticmethod
    def _normalize_order_no(
        order_no: str,
    ) -> str:
        """
        주문번호 앞쪽의 0 차이로 인한 비교 오류를 방지한다.
        """
        normalized = str(order_no).strip()

        if normalized.isdigit():
            return normalized.lstrip("0") or "0"

        return normalized

    @staticmethod
    def _to_int(value: Any) -> int:
        if value in (None, ""):
            return 0

        try:
            return int(float(str(value).replace(",", "")))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _to_float(value: Any) -> float:
        if value in (None, ""):
            return 0.0

        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return 0.0
    @staticmethod
    def _extract_executed_at(
        rows: list[dict[str, Any]],
    ) -> str:
        """
        API 응답에서 체결일자와 체결시각을 추출한다.

        응답에 체결시각이 없으면 현재 시각을 사용한다.
        """
        latest_row = rows[-1]

        execution_date = str(
            latest_row.get("ord_dt")
            or latest_row.get("ORD_DT")
            or latest_row.get("ccld_dt")
            or latest_row.get("CCLD_DT")
            or ""
        ).strip()

        execution_time = str(
            latest_row.get("ord_tmd")
            or latest_row.get("ORD_TMD")
            or latest_row.get("ccld_tmd")
            or latest_row.get("CCLD_TMD")
            or ""
        ).strip()

        if (
            len(execution_date) == 8
            and execution_date.isdigit()
            and len(execution_time) == 6
            and execution_time.isdigit()
        ):
            return (
                f"{execution_date[0:4]}-"
                f"{execution_date[4:6]}-"
                f"{execution_date[6:8]} "
                f"{execution_time[0:2]}:"
                f"{execution_time[2:4]}:"
                f"{execution_time[4:6]}"
            )

        if (
            len(execution_time) == 6
            and execution_time.isdigit()
        ):
            today = datetime.now().strftime("%Y-%m-%d")

            return (
                f"{today} "
                f"{execution_time[0:2]}:"
                f"{execution_time[2:4]}:"
                f"{execution_time[4:6]}"
            )

        return datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    @staticmethod
    def _calculate_new_fill_price(
        previous_filled_quantity: int,
        previous_average_fill_price: float,
        current_filled_quantity: int,
        current_average_fill_price: float,
    ) -> float:
        """
        이전 누적 체결값과 현재 누적 체결값의 차이를 이용해
        이번에 새로 체결된 수량의 체결가격을 계산한다.

        예:
        기존 4주, 평균 70,000원
        현재 7주, 평균 70,100원

        신규 3주의 체결가격을 역산한다.
        """
        newly_filled_quantity = (
            current_filled_quantity
            - previous_filled_quantity
        )

        if newly_filled_quantity <= 0:
            return 0.0

        previous_total_amount = (
            previous_filled_quantity
            * previous_average_fill_price
        )

        current_total_amount = (
            current_filled_quantity
            * current_average_fill_price
        )

        new_fill_amount = (
            current_total_amount
            - previous_total_amount
        )

        new_fill_price = (
            new_fill_amount
            / newly_filled_quantity
        )

        if new_fill_price < 0:
            raise RuntimeError(
                "신규 체결가격 계산 결과가 음수입니다."
            )

        return float(new_fill_price)