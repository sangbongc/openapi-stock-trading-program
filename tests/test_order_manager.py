from unittest.mock import Mock, patch

from trading.order_manager import OrderManager


@patch("trading.order_manager.save_order")
@patch("trading.order_manager.buy_stock")
def test_buy_order_success(
    mock_buy_stock: Mock,
    mock_save_order: Mock,
):
    mock_buy_stock.return_value = {
        "rt_cd": "0",
        "msg_cd": "APBK0013",
        "msg1": "주문 전송 완료",
        "output": {
            "ODNO": "0000012345",
            "ORD_TMD": "103000",
        },
    }

    mock_save_order.return_value = 1

    manager = OrderManager()

    result = manager.buy(
        stock_code="005930",
        quantity=1,
        order_type="MARKET",
    )

    assert result["success"] is True
    assert result["status"] == "ACCEPTED"
    assert result["order_id"] == 1
    assert result["order_no"] == "0000012345"
    assert result["side"] == "BUY"

    mock_buy_stock.assert_called_once_with(
        stock_code="005930",
        quantity=1,
        price=0,
        order_type="MARKET",
    )

    mock_save_order.assert_called_once_with(
        stock_code="005930",
        side="BUY",
        order_type="MARKET",
        quantity=1,
        price=0,
        status="ACCEPTED",
        order_no="0000012345",
        message_code="APBK0013",
        message="주문 전송 완료",
    )

    print("OrderManager 매수 성공 테스트 통과")


@patch("trading.order_manager.save_order")
@patch("trading.order_manager.sell_stock")
def test_sell_order_success(
    mock_sell_stock: Mock,
    mock_save_order: Mock,
):
    mock_sell_stock.return_value = {
        "rt_cd": "0",
        "msg_cd": "APBK0013",
        "msg1": "주문 전송 완료",
        "output": {
            "ODNO": "0000054321",
            "ORD_TMD": "104000",
        },
    }

    mock_save_order.return_value = 2

    manager = OrderManager()

    result = manager.sell(
        stock_code="005930",
        quantity=2,
        order_type="MARKET",
    )

    assert result["success"] is True
    assert result["status"] == "ACCEPTED"
    assert result["order_id"] == 2
    assert result["order_no"] == "0000054321"
    assert result["side"] == "SELL"

    mock_sell_stock.assert_called_once_with(
        stock_code="005930",
        quantity=2,
        price=0,
        order_type="MARKET",
    )

    mock_save_order.assert_called_once_with(
        stock_code="005930",
        side="SELL",
        order_type="MARKET",
        quantity=2,
        price=0,
        status="ACCEPTED",
        order_no="0000054321",
        message_code="APBK0013",
        message="주문 전송 완료",
    )

    print("OrderManager 매도 성공 테스트 통과")


@patch("trading.order_manager.save_order")
@patch("trading.order_manager.buy_stock")
def test_buy_order_failure(
    mock_buy_stock: Mock,
    mock_save_order: Mock,
):
    mock_buy_stock.side_effect = RuntimeError(
        "주문 실패 [ORDER_ERROR]: 주문 가능 금액을 초과했습니다."
    )

    mock_save_order.return_value = 3

    manager = OrderManager()

    result = manager.buy(
        stock_code="005930",
        quantity=10000,
        order_type="MARKET",
    )

    assert result["success"] is False
    assert result["status"] == "FAILED"
    assert result["order_id"] == 3
    assert result["order_no"] is None
    assert result["message_code"] == "RuntimeError"
    assert "주문 가능 금액" in result["message"]

    mock_save_order.assert_called_once_with(
        stock_code="005930",
        side="BUY",
        order_type="MARKET",
        quantity=10000,
        price=0,
        status="FAILED",
        order_no=None,
        message_code="RuntimeError",
        message=(
            "주문 실패 [ORDER_ERROR]: "
            "주문 가능 금액을 초과했습니다."
        ),
    )

    print("OrderManager 주문 실패 처리 테스트 통과")


def test_invalid_order_input():
    manager = OrderManager()

    try:
        manager.buy(
            stock_code="5930",
            quantity=1,
        )
    except ValueError as exc:
        assert "6자리 종목코드" in str(exc)
    else:
        raise AssertionError(
            "잘못된 종목코드에서 ValueError가 발생하지 않았습니다."
        )

    print("OrderManager 입력값 검증 테스트 통과")


if __name__ == "__main__":
    test_buy_order_success()
    test_sell_order_success()
    test_buy_order_failure()
    test_invalid_order_input()

    print("OrderManager 전체 테스트 완료")