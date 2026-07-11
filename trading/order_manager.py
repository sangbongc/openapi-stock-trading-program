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

        Parameters
        ----------
        stock_code : str
            6자리 종목코드

        side : str
            BUY 또는 SELL

        quantity : int
            주문 수량

        price : int, default=0
            지정가 주문 가격.
            시장가 주문에서는 0을 사용한다.

        order_type : str, default="MARKET"
            MARKET 또는 LIMIT

        Returns
        -------
        dict
            주문 실행 결과
        """
        stock_code = str(stock_code).strip()
        side = side.upper().strip()
        order_type = order_type.upper().strip()

        self._validate_order(
            stock_code=stock_code,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
        )

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

            output = api_result.get("output") or {}

            order_no = output.get("ODNO")
            message_code = api_result.get("msg_cd")
            message = api_result.get("msg1")

            order_id = save_order(
                stock_code=stock_code,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                status="SUCCESS",
                order_no=order_no,
                message_code=message_code,
                message=message,
            )

            return {
                "success": True,
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
            order_id = save_order(
                stock_code=stock_code,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                status="FAILED",
                order_no=None,
                message_code=type(exc).__name__,
                message=str(exc),
            )

            return {
                "success": False,
                "order_id": order_id,
                "order_no": None,
                "stock_code": stock_code,
                "side": side,
                "order_type": order_type,
                "quantity": quantity,
                "price": price,
                "message_code": type(exc).__name__,
                "message": str(exc),
                "api_result": None,
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

        if order_type == "LIMIT" and price <= 0:
            raise ValueError(
                "지정가 주문의 price는 1 이상이어야 합니다."
            )