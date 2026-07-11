from database import (
    create_tables,
    fetch_orders,
    save_order,
)


def test_save_success_order():
    create_tables()

    order_id = save_order(
        stock_code="005930",
        side="BUY",
        order_type="MARKET",
        quantity=1,
        price=0,
        status="SUCCESS",
        order_no="0000012345",
        message_code="APBK0013",
        message="주문 전송 완료",
    )

    assert isinstance(order_id, int)
    assert order_id > 0

    orders = fetch_orders(
        stock_code="005930",
        limit=1,
    )

    assert len(orders) == 1

    saved_order = orders[0]

    assert saved_order["stock_code"] == "005930"
    assert saved_order["side"] == "BUY"
    assert saved_order["order_type"] == "MARKET"
    assert saved_order["quantity"] == 1
    assert saved_order["price"] == 0
    assert saved_order["status"] == "SUCCESS"
    assert saved_order["order_no"] == "0000012345"

    print("성공 주문 저장 테스트 통과")


def test_save_failed_order():
    order_id = save_order(
        stock_code="000660",
        side="BUY",
        order_type="LIMIT",
        quantity=2,
        price=150000,
        status="FAILED",
        message_code="ORDER_ERROR",
        message="주문 가능 금액을 초과했습니다.",
    )

    assert order_id > 0

    orders = fetch_orders(
        stock_code="000660",
        limit=1,
    )

    saved_order = orders[0]

    assert saved_order["status"] == "FAILED"
    assert saved_order["order_no"] is None
    assert saved_order["message_code"] == "ORDER_ERROR"

    print("실패 주문 저장 테스트 통과")


if __name__ == "__main__":
    test_save_success_order()
    test_save_failed_order()

    print("orders 테이블 테스트 완료")