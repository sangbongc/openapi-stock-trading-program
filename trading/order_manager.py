from typing import Any

from api import buy_stock, sell_stock
from database import save_order


class OrderManager:
    """
    주문 API 호출과 주문 결과 DB 저장을 관리한다.
    """

    def execute_order(
        self,
        stock_code: str,
        side: str,
        quantity: int,
        price: int = 0,
        order_type: str = "MARKET",
    ) -> dict[str, Any]:
        """
        매수 또는 매도 주문을 실행하고 결과를 DB에 저장한다.

        입력값 검증 실패는 DB에 저장하지 않는다.
        API 호출 실패는 FAILED,
        주문 접수 성공은 ACCEPTED로 저장한다.
        """
        stock_code = str(stock_code).strip()
        side = str(side).upper().strip()
        order_type = str(order_type).upper().strip()

        self._validate_order(
            stock_code=stock_code,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
        )

        api_result: dict[str, Any] | None = None

        try:
            if side == "BUY":
                api_result = buy_stock(
                    stock_code=stock_code,
                    quantity=quantity,
                    price=price,
                    order_type=order_type,
                )
            else:
                api_result = sell_stock(
                    stock_code=stock_code,
                    quantity=quantity,
                    price=price,
                    order_type=order_type,
                )

            if not isinstance(api_result, dict):
                raise RuntimeError(
                    "주문 API 응답이 딕셔너리 형식이 아닙니다."
                )

            message_code = api_result.get("msg_cd")
            message = api_result.get("msg1")

            if api_result.get("rt_cd") != "0":
                raise RuntimeError(
                    f"주문 실패 [{message_code or 'UNKNOWN'}]: "
                    f"{message or '알 수 없는 주문 오류'}"
                )

            output = api_result.get("output") or {}

            if not isinstance(output, dict):
                raise RuntimeError(
                    "주문 API 응답의 output 형식이 올바르지 않습니다."
                )

            order_no = output.get("ODNO") or output.get("odno")

            if order_no is not None:
                order_no = str(order_no).strip() or None

            order_id = save_order(
                stock_code=stock_code,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                status="ACCEPTED",
                order_no=order_no,
                message_code=message_code,
                message=message,
            )

            return {
                "success": True,
                "status": "ACCEPTED",
                "order_id": order_id,
                "order_no": order_no,
                "stock_code": stock_code,
                "side": side,
                "order_type": order_type,
                "quantity": quantity,
                "price": price,
                "message_code": message_code,
                "message": message,
                "api_result": api_result,
            }

        except Exception as exc:
            message_code = type(exc).__name__
            message = str(exc)

            if isinstance(api_result, dict):
                message_code = api_result.get("msg_cd") or message_code
                message = api_result.get("msg1") or message

            order_id = save_order(
                stock_code=stock_code,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                status="FAILED",
                order_no=None,
                message_code=message_code,
                message=message,
            )

            return {
                "success": False,
                "status": "FAILED",
                "order_id": order_id,
                "order_no": None,
                "stock_code": stock_code,
                "side": side,
                "order_type": order_type,
                "quantity": quantity,
                "price": price,
                "message_code": message_code,
                "message": message,
                "api_result": api_result,
            }

    def buy(
        self,
        stock_code: str,
        quantity: int,
        price: int = 0,
        order_type: str = "MARKET",
    ) -> dict[str, Any]:
        """
        매수 주문을 실행한다.
        """
        return self.execute_order(
            stock_code=stock_code,
            side="BUY",
            quantity=quantity,
            price=price,
            order_type=order_type,
        )

    def sell(
        self,
        stock_code: str,
        quantity: int,
        price: int = 0,
        order_type: str = "MARKET",
    ) -> dict[str, Any]:
        """
        매도 주문을 실행한다.
        """
        return self.execute_order(
            stock_code=stock_code,
            side="SELL",
            quantity=quantity,
            price=price,
            order_type=order_type,
        )

    @staticmethod
    def _validate_order(
        stock_code: str,
        side: str,
        quantity: int,
        price: int,
        order_type: str,
    ) -> None:
        """
        주문 입력값을 검증한다.
        """
        if len(stock_code) != 6 or not stock_code.isdigit():
            raise ValueError(
                "stock_code는 숫자로 된 6자리 종목코드여야 합니다."
            )

        if side not in {"BUY", "SELL"}:
            raise ValueError(
                "side는 BUY 또는 SELL이어야 합니다."
            )

        if order_type not in {"MARKET", "LIMIT"}:
            raise ValueError(
                "order_type은 MARKET 또는 LIMIT이어야 합니다."
            )

        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise TypeError("quantity는 정수여야 합니다.")

        if quantity <= 0:
            raise ValueError("quantity는 1 이상이어야 합니다.")

        if isinstance(price, bool) or not isinstance(price, int):
            raise TypeError("price는 정수여야 합니다.")

        if price < 0:
            raise ValueError("price는 0 이상이어야 합니다.")

        if order_type == "MARKET" and price != 0:
            raise ValueError(
                "시장가 주문은 가격을 지정할 수 없습니다. "
                "price는 0으로 설정해야 합니다."
            )

        if order_type == "LIMIT" and price <= 0:
            raise ValueError(
                "지정가 주문에서는 price를 1 이상으로 지정해야 합니다."
            )