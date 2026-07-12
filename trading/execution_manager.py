from typing import Any

from api import get_order_executions
from database import (
    fetch_order_by_order_no,
    save_execution,
    update_order_execution_status,
)
from trading.order_status import OrderStatus


class ExecutionManager:
    def check_order(self, order_no: str) -> dict[str, Any]:
        """
        특정 주문번호의 체결 상태를 조회하고 DB에 반영한다.
        """
        order = fetch_order_by_order_no(order_no)

        if order is None:
            raise ValueError(
                f"DB에서 주문번호를 찾을 수 없습니다: {order_no}"
            )

        response = get_order_executions(order_no=order_no)

        if response.get("rt_cd") != "0":
            return {
                "SUCCESS": False,
                "order_no": order_no,
                "status": OrderStatus.UNKNOWN.value,
                "message": response.get(
                    "msg1",
                    "체결 조회에 실패했습니다.",
                ),
            }

        executions = self._parse_executions(
            response=response,
            order=order,
        )

        for execution in executions:
            save_execution(**execution)

        summary = self._summarize_execution(
            ordered_quantity=order["ordered_quantity"],
            executions=executions,
        )

        update_order_execution_status(
            order_no=order_no,
            status=summary["status"],
            filled_quantity=summary["filled_quantity"],
            remaining_quantity=summary["remaining_quantity"],
            average_fill_price=summary["average_fill_price"],
        )

        return {
            "SUCCESS": True,
            "order_no": order_no,
            **summary,
            "executions": executions,
        }

    def _parse_executions(
        self,
        response: dict[str, Any],
        order: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        증권사 체결 조회 응답을 내부 형식으로 변환한다.
        """
        parsed: list[dict[str, Any]] = []

        rows = response.get("output1", [])

        for row in rows:
            executed_quantity = int(
                row.get("tot_ccld_qty", 0) or 0
            )

            if executed_quantity <= 0:
                continue

            parsed.append(
                {
                    "order_id": order["id"],
                    "order_no": order["order_no"],
                    "execution_no": row.get(
                        "odno",
                        order["order_no"],
                    ),
                    "stock_code": order["stock_code"],
                    "side": order["side"],
                    "executed_quantity": executed_quantity,
                    "executed_price": int(
                        row.get("avg_prvs", 0) or 0
                    ),
                    "executed_at": row.get(
                        "ord_tmd",
                        "",
                    ),
                }
            )

        return parsed

    def _summarize_execution(
        self,
        ordered_quantity: int,
        executions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        filled_quantity = sum(
            execution["executed_quantity"]
            for execution in executions
        )

        remaining_quantity = max(
            ordered_quantity - filled_quantity,
            0,
        )

        total_amount = sum(
            execution["executed_quantity"]
            * execution["executed_price"]
            for execution in executions
        )

        if filled_quantity > 0:
            average_fill_price = (
                total_amount / filled_quantity
            )
        else:
            average_fill_price = 0

        if filled_quantity == 0:
            status = OrderStatus.ACCEPTED.value
        elif filled_quantity < ordered_quantity:
            status = OrderStatus.PARTIALLY_FILLED.value
        else:
            status = OrderStatus.FILLED.value

        return {
            "status": status,
            "filled_quantity": filled_quantity,
            "remaining_quantity": remaining_quantity,
            "average_fill_price": average_fill_price,
        }