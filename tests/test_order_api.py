from unittest.mock import Mock, patch

import pytest

from api import buy_stock, sell_stock


def make_success_response() -> Mock:
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "rt_cd": "0",
        "msg_cd": "APBK0013",
        "msg1": "주문 전송 완료 되었습니다.",
        "output": {
            "ODNO": "0000012345",
            "ORD_TMD": "103000",
        },
    }
    return mock_response


@patch("api.get_access_token")
@patch("api.requests.post")
def test_sell_stock_market_order(
    mock_post: Mock,
    mock_get_access_token: Mock,
):
    mock_get_access_token.return_value = "test-token"
    mock_post.return_value = make_success_response()

    result = sell_stock(
        stock_code="005930",
        quantity=2,
        order_type="MARKET",
    )

    assert result["rt_cd"] == "0"

    _, call_kwargs = mock_post.call_args

    request_body = call_kwargs["json"]
    request_headers = call_kwargs["headers"]

    assert request_body["PDNO"] == "005930"
    assert request_body["ORD_QTY"] == "2"
    assert request_body["ORD_DVSN"] == "01"
    assert request_body["ORD_UNPR"] == "0"

    # 모의투자 매도 TR ID
    assert request_headers["tr_id"] == "VTTC0801U"

    print("모의 매도 주문 요청 구조 테스트 통과")


@patch("api.get_access_token")
@patch("api.requests.post")
def test_buy_stock_limit_order(
    mock_post: Mock,
    mock_get_access_token: Mock,
):
    mock_get_access_token.return_value = "test-token"
    mock_post.return_value = make_success_response()

    buy_stock(
        stock_code="005930",
        quantity=1,
        price=70000,
        order_type="LIMIT",
    )

    _, call_kwargs = mock_post.call_args

    request_body = call_kwargs["json"]

    # 지정가 주문 구분
    assert request_body["ORD_DVSN"] == "00"

    # 지정가 주문 가격
    assert request_body["ORD_UNPR"] == "70000"

    print("모의 지정가 매수 요청 구조 테스트 통과")


def test_buy_stock_invalid_stock_code():
    with pytest.raises(
        ValueError,
        match="6자리 종목코드",
    ):
        buy_stock(
            stock_code="5930",
            quantity=1,
        )


def test_buy_stock_invalid_quantity():
    with pytest.raises(
        ValueError,
        match="quantity는 1 이상",
    ):
        buy_stock(
            stock_code="005930",
            quantity=0,
        )


def test_limit_order_without_price():
    with pytest.raises(
        ValueError,
        match="지정가 주문의 price",
    ):
        buy_stock(
            stock_code="005930",
            quantity=1,
            price=0,
            order_type="LIMIT",
        )


@patch("api.get_access_token")
@patch("api.requests.post")
def test_order_api_failure(
    mock_post: Mock,
    mock_get_access_token: Mock,
):
    mock_get_access_token.return_value = "test-token"

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "rt_cd": "1",
        "msg_cd": "ORDER_ERROR",
        "msg1": "주문 가능 금액을 초과했습니다.",
    }

    mock_post.return_value = mock_response

    with pytest.raises(
        RuntimeError,
        match="주문 실패",
    ):
        buy_stock(
            stock_code="005930",
            quantity=100,
        )