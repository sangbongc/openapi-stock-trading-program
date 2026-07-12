import pytest
from unittest.mock import Mock, patch

from trading.execution_manager import ExecutionManager


LOCAL_ORDER = {
    "id": 1,
    "created_at": "2026-07-12 10:29:00",
    "updated_at": "2026-07-12 10:29:00",
    "stock_code": "005930",
    "side": "BUY",
    "order_type": "MARKET",
    "quantity": 10,
    "price": 0,
    "order_no": "0000012345",
    "status": "ACCEPTED",
    "execution_status": "PENDING",
    "filled_quantity": 0,
    "remaining_quantity": 10,
    "average_fill_price": 0.0,
    "message_code": "APBK0013",
    "message": "주문 접수 완료",
}


@patch(
    "trading.execution_manager.update_order_execution"
)
@patch(
    "trading.execution_manager.save_execution"
)
@patch(
    "trading.execution_manager.inquire_daily_orders"
)
@patch(
    "trading.execution_manager.fetch_order_by_order_no"
)
def test_sync_order_pending(
    mock_fetch_order: Mock,
    mock_inquire_orders: Mock,
    mock_save_execution: Mock,
    mock_update_order: Mock,
):
    """
    주문은 접수됐지만 아직 체결되지 않은 경우를 검증한다.
    """
    mock_fetch_order.return_value = LOCAL_ORDER.copy()

    mock_inquire_orders.return_value = {
        "rt_cd": "0",
        "output1": [
            {
                "odno": "0000012345",
                "tot_ccld_qty": "0",
                "avg_prvs": "0",
                "cncl_yn": "N",
                "ord_dvsn_name": "시장가",
                "rjct_rson": "",
            }
        ],
    }

    manager = ExecutionManager()
    result = manager.sync_order("0000012345")

    assert result["execution_status"] == "PENDING"
    assert result["previous_filled_quantity"] == 0
    assert result["filled_quantity"] == 0
    assert result["newly_filled_quantity"] == 0
    assert result["remaining_quantity"] == 10
    assert result["average_fill_price"] == 0
    assert result["new_fill_price"] == 0
    assert result["execution_id"] is None
    assert result["changed"] is False

    mock_save_execution.assert_not_called()
    mock_update_order.assert_not_called()


@patch(
    "trading.execution_manager.update_order_execution"
)
@patch(
    "trading.execution_manager.save_execution"
)
@patch(
    "trading.execution_manager.inquire_daily_orders"
)
@patch(
    "trading.execution_manager.fetch_order_by_order_no"
)
def test_sync_order_saves_first_partial_execution(
    mock_fetch_order: Mock,
    mock_inquire_orders: Mock,
    mock_save_execution: Mock,
    mock_update_order: Mock,
):
    """
    최초 부분체결 발생 시 신규 체결을 저장하고
    orders 테이블을 PARTIAL 상태로 갱신하는지 검증한다.
    """
    mock_fetch_order.return_value = LOCAL_ORDER.copy()

    mock_inquire_orders.return_value = {
        "rt_cd": "0",
        "output1": [
            {
                "odno": "0000012345",
                "tot_ccld_qty": "4",
                "avg_prvs": "70000",
                "cncl_yn": "N",
                "ord_dvsn_name": "시장가",
                "rjct_rson": "",
                "ord_dt": "20260712",
                "ord_tmd": "103000",
            }
        ],
    }

    mock_save_execution.return_value = 1

    manager = ExecutionManager()
    result = manager.sync_order("0000012345")

    assert result["execution_status"] == "PARTIAL"
    assert result["previous_filled_quantity"] == 0
    assert result["filled_quantity"] == 4
    assert result["newly_filled_quantity"] == 4
    assert result["remaining_quantity"] == 6
    assert result["average_fill_price"] == 70000
    assert result["new_fill_price"] == 70000
    assert result["execution_id"] == 1
    assert result["changed"] is True

    mock_save_execution.assert_called_once_with(
        order_id=1,
        order_no="0000012345",
        stock_code="005930",
        side="BUY",
        quantity=4,
        price=70000,
        executed_at="2026-07-12 10:30:00",
    )

    mock_update_order.assert_called_once_with(
        order_no="0000012345",
        filled_quantity=4,
        remaining_quantity=6,
        average_fill_price=70000,
        execution_status="PARTIAL",
    )


@patch(
    "trading.execution_manager.update_order_execution"
)
@patch(
    "trading.execution_manager.save_execution"
)
@patch(
    "trading.execution_manager.inquire_daily_orders"
)
@patch(
    "trading.execution_manager.fetch_order_by_order_no"
)
def test_sync_order_does_not_save_duplicate_execution(
    mock_fetch_order: Mock,
    mock_inquire_orders: Mock,
    mock_save_execution: Mock,
    mock_update_order: Mock,
):
    """
    동일한 누적 체결수량을 다시 조회했을 때
    executions에 중복 저장하지 않는지 검증한다.
    """
    local_order = LOCAL_ORDER.copy()
    local_order["execution_status"] = "PARTIAL"
    local_order["filled_quantity"] = 4
    local_order["remaining_quantity"] = 6
    local_order["average_fill_price"] = 70000

    mock_fetch_order.return_value = local_order

    mock_inquire_orders.return_value = {
        "rt_cd": "0",
        "output1": [
            {
                "odno": "0000012345",
                "tot_ccld_qty": "4",
                "avg_prvs": "70000",
                "cncl_yn": "N",
                "ord_dvsn_name": "시장가",
                "rjct_rson": "",
            }
        ],
    }

    manager = ExecutionManager()
    result = manager.sync_order("0000012345")

    assert result["execution_status"] == "PARTIAL"
    assert result["previous_filled_quantity"] == 4
    assert result["filled_quantity"] == 4
    assert result["newly_filled_quantity"] == 0
    assert result["remaining_quantity"] == 6
    assert result["changed"] is False

    mock_save_execution.assert_not_called()
    mock_update_order.assert_not_called()


@patch(
    "trading.execution_manager.update_order_execution"
)
@patch(
    "trading.execution_manager.save_execution"
)
@patch(
    "trading.execution_manager.inquire_daily_orders"
)
@patch(
    "trading.execution_manager.fetch_order_by_order_no"
)
def test_sync_order_saves_only_incremental_fill(
    mock_fetch_order: Mock,
    mock_inquire_orders: Mock,
    mock_save_execution: Mock,
    mock_update_order: Mock,
):
    """
    누적 체결수량이 4주에서 7주로 증가했을 때
    신규 체결분 3주만 저장하는지 검증한다.
    """
    local_order = LOCAL_ORDER.copy()
    local_order["execution_status"] = "PARTIAL"
    local_order["filled_quantity"] = 4
    local_order["remaining_quantity"] = 6
    local_order["average_fill_price"] = 70000

    mock_fetch_order.return_value = local_order

    # 기존 체결:
    # 4주 × 70,000원
    #
    # 신규 체결:
    # 3주 × 70,300원
    #
    # 현재 누적:
    # 7주, 평균 약 70,128.5714원
    current_average = (
        (4 * 70000)
        + (3 * 70300)
    ) / 7

    mock_inquire_orders.return_value = {
        "rt_cd": "0",
        "output1": [
            {
                "odno": "0000012345",
                "tot_ccld_qty": "7",
                "avg_prvs": str(current_average),
                "cncl_yn": "N",
                "ord_dvsn_name": "시장가",
                "rjct_rson": "",
                "ord_dt": "20260712",
                "ord_tmd": "103100",
            }
        ],
    }

    mock_save_execution.return_value = 2

    manager = ExecutionManager()
    result = manager.sync_order("0000012345")

    assert result["execution_status"] == "PARTIAL"
    assert result["previous_filled_quantity"] == 4
    assert result["filled_quantity"] == 7
    assert result["newly_filled_quantity"] == 3
    assert result["remaining_quantity"] == 3

    assert result["average_fill_price"] == pytest.approx(
        current_average
    )

    assert result["new_fill_price"] == pytest.approx(
        70300
    )

    assert result["execution_id"] == 2
    assert result["changed"] is True

    mock_save_execution.assert_called_once()

    save_call = mock_save_execution.call_args.kwargs

    assert save_call["order_id"] == 1
    assert save_call["order_no"] == "0000012345"
    assert save_call["stock_code"] == "005930"
    assert save_call["side"] == "BUY"
    assert save_call["quantity"] == 3
    assert save_call["price"] == pytest.approx(70300)
    assert save_call["executed_at"] == (
        "2026-07-12 10:31:00"
    )

    mock_update_order.assert_called_once()

    update_call = mock_update_order.call_args.kwargs

    assert update_call["order_no"] == "0000012345"
    assert update_call["filled_quantity"] == 7
    assert update_call["remaining_quantity"] == 3
    assert update_call[
        "average_fill_price"
    ] == pytest.approx(current_average)

    assert update_call["execution_status"] == "PARTIAL"


@patch(
    "trading.execution_manager.update_order_execution"
)
@patch(
    "trading.execution_manager.save_execution"
)
@patch(
    "trading.execution_manager.inquire_daily_orders"
)
@patch(
    "trading.execution_manager.fetch_order_by_order_no"
)
def test_sync_order_filled(
    mock_fetch_order: Mock,
    mock_inquire_orders: Mock,
    mock_save_execution: Mock,
    mock_update_order: Mock,
):
    """
    주문수량 전부가 체결된 경우 FILLED로 갱신되는지 검증한다.
    """
    mock_fetch_order.return_value = LOCAL_ORDER.copy()

    mock_inquire_orders.return_value = {
        "rt_cd": "0",
        "output1": [
            {
                "odno": "0000012345",
                "tot_ccld_qty": "10",
                "avg_prvs": "70100",
                "cncl_yn": "N",
                "ord_dvsn_name": "시장가",
                "rjct_rson": "",
                "ord_dt": "20260712",
                "ord_tmd": "103200",
            }
        ],
    }

    mock_save_execution.return_value = 1

    manager = ExecutionManager()
    result = manager.sync_order("0000012345")

    assert result["execution_status"] == "FILLED"
    assert result["filled_quantity"] == 10
    assert result["newly_filled_quantity"] == 10
    assert result["remaining_quantity"] == 0
    assert result["average_fill_price"] == 70100
    assert result["new_fill_price"] == 70100
    assert result["changed"] is True

    mock_save_execution.assert_called_once_with(
        order_id=1,
        order_no="0000012345",
        stock_code="005930",
        side="BUY",
        quantity=10,
        price=70100,
        executed_at="2026-07-12 10:32:00",
    )

    mock_update_order.assert_called_once_with(
        order_no="0000012345",
        filled_quantity=10,
        remaining_quantity=0,
        average_fill_price=70100,
        execution_status="FILLED",
    )


@patch(
    "trading.execution_manager.update_order_execution"
)
@patch(
    "trading.execution_manager.save_execution"
)
@patch(
    "trading.execution_manager.inquire_daily_orders"
)
@patch(
    "trading.execution_manager.fetch_order_by_order_no"
)
def test_sync_order_cancelled(
    mock_fetch_order: Mock,
    mock_inquire_orders: Mock,
    mock_save_execution: Mock,
    mock_update_order: Mock,
):
    """
    일부 체결 후 나머지 주문이 취소된 경우
    CANCELLED 상태로 변경되는지 검증한다.
    """
    local_order = LOCAL_ORDER.copy()
    local_order["status"] = "ACCEPTED"
    local_order["execution_status"] = "PARTIAL"
    local_order["filled_quantity"] = 3
    local_order["remaining_quantity"] = 7
    local_order["average_fill_price"] = 70000

    mock_fetch_order.return_value = local_order

    mock_inquire_orders.return_value = {
        "rt_cd": "0",
        "output1": [
            {
                "odno": "0000012345",
                "tot_ccld_qty": "3",
                "avg_prvs": "70000",
                "cncl_yn": "Y",
                "ord_dvsn_name": "취소",
                "rjct_rson": "",
            }
        ],
    }

    manager = ExecutionManager()
    result = manager.sync_order("0000012345")

    assert result["execution_status"] == "CANCELLED"
    assert result["previous_filled_quantity"] == 3
    assert result["filled_quantity"] == 3
    assert result["newly_filled_quantity"] == 0
    assert result["remaining_quantity"] == 7
    assert result["average_fill_price"] == 70000
    assert result["changed"] is True

    # 새 체결은 없으므로 executions에는 저장하지 않는다.
    mock_save_execution.assert_not_called()

    # 체결 상태만 PARTIAL에서 CANCELLED로 갱신한다.
    mock_update_order.assert_called_once_with(
        order_no="0000012345",
        filled_quantity=3,
        remaining_quantity=7,
        average_fill_price=70000,
        execution_status="CANCELLED",
    )


@patch(
    "trading.execution_manager.update_order_execution"
)
@patch(
    "trading.execution_manager.save_execution"
)
@patch(
    "trading.execution_manager.inquire_daily_orders"
)
@patch(
    "trading.execution_manager.fetch_order_by_order_no"
)
def test_sync_order_api_result_not_found(
    mock_fetch_order: Mock,
    mock_inquire_orders: Mock,
    mock_save_execution: Mock,
    mock_update_order: Mock,
):
    """
    API 응답에서 주문번호를 찾지 못한 경우
    기존 로컬 상태를 유지하는지 검증한다.
    """
    mock_fetch_order.return_value = LOCAL_ORDER.copy()

    mock_inquire_orders.return_value = {
        "rt_cd": "0",
        "output1": [],
    }

    manager = ExecutionManager()
    result = manager.sync_order("0000012345")

    assert result["execution_status"] == "PENDING"
    assert result["filled_quantity"] == 0
    assert result["newly_filled_quantity"] == 0
    assert result["remaining_quantity"] == 10
    assert result["execution_id"] is None
    assert result["changed"] is False
    assert "message" in result

    mock_save_execution.assert_not_called()
    mock_update_order.assert_not_called()


@patch(
    "trading.execution_manager.fetch_order_by_order_no"
)
def test_sync_order_rejects_failed_order(
    mock_fetch_order: Mock,
):
    """
    주문 접수 자체가 실패한 주문은 체결 조회하지 않는지 검증한다.
    """
    local_order = LOCAL_ORDER.copy()
    local_order["status"] = "FAILED"
    local_order["execution_status"] = "NOT_APPLICABLE"

    mock_fetch_order.return_value = local_order

    manager = ExecutionManager()

    with pytest.raises(
        ValueError,
        match="증권사에 접수된 주문만",
    ):
        manager.sync_order("0000012345")


@patch(
    "trading.execution_manager.fetch_order_by_order_no"
)
def test_sync_order_raises_when_local_order_not_found(
    mock_fetch_order: Mock,
):
    """
    로컬 DB에서 주문을 찾지 못했을 때 예외를 발생시키는지 검증한다.
    """
    mock_fetch_order.return_value = None

    manager = ExecutionManager()

    with pytest.raises(
        ValueError,
        match="찾을 수 없습니다",
    ):
        manager.sync_order("0000012345")


@patch(
    "trading.execution_manager.fetch_open_orders"
)
@patch.object(
    ExecutionManager,
    "sync_order",
)
def test_sync_open_orders(
    mock_sync_order: Mock,
    mock_fetch_open_orders: Mock,
):
    """
    PENDING 및 PARTIAL 주문들을 순서대로 동기화하는지 검증한다.
    """
    first_order = LOCAL_ORDER.copy()

    second_order = LOCAL_ORDER.copy()
    second_order["id"] = 2
    second_order["order_no"] = "0000012346"
    second_order["stock_code"] = "000660"
    second_order["execution_status"] = "PARTIAL"
    second_order["filled_quantity"] = 2
    second_order["remaining_quantity"] = 8

    mock_fetch_open_orders.return_value = [
        first_order,
        second_order,
    ]

    mock_sync_order.side_effect = [
        {
            "order_no": "0000012345",
            "execution_status": "FILLED",
        },
        {
            "order_no": "0000012346",
            "execution_status": "PARTIAL",
        },
    ]

    manager = ExecutionManager()
    results = manager.sync_open_orders()

    assert len(results) == 2
    assert results[0]["execution_status"] == "FILLED"
    assert results[1]["execution_status"] == "PARTIAL"

    mock_sync_order.assert_any_call("0000012345")
    mock_sync_order.assert_any_call("0000012346")
    assert mock_sync_order.call_count == 2


@patch(
    "trading.execution_manager.fetch_open_orders"
)
@patch.object(
    ExecutionManager,
    "sync_order",
)
def test_sync_open_orders_continues_after_error(
    mock_sync_order: Mock,
    mock_fetch_open_orders: Mock,
):
    """
    한 주문의 동기화가 실패해도 나머지 주문을 계속 처리하는지 검증한다.
    """
    first_order = LOCAL_ORDER.copy()

    second_order = LOCAL_ORDER.copy()
    second_order["id"] = 2
    second_order["order_no"] = "0000012346"
    second_order["stock_code"] = "000660"

    mock_fetch_open_orders.return_value = [
        first_order,
        second_order,
    ]

    mock_sync_order.side_effect = [
        RuntimeError("API 조회 실패"),
        {
            "order_no": "0000012346",
            "execution_status": "FILLED",
        },
    ]

    manager = ExecutionManager()
    results = manager.sync_open_orders()

    assert len(results) == 2

    assert results[0]["order_no"] == "0000012345"
    assert results[0]["execution_status"] == "ERROR"
    assert results[0]["changed"] is False
    assert "API 조회 실패" in results[0]["error"]

    assert results[1]["order_no"] == "0000012346"
    assert results[1]["execution_status"] == "FILLED"

    assert mock_sync_order.call_count == 2
@patch(
    "trading.execution_manager.update_order_execution"
)
@patch(
    "trading.execution_manager.save_execution"
)
@patch(
    "trading.execution_manager.inquire_daily_orders"
)
@patch(
    "trading.execution_manager.fetch_order_by_order_no"
)
def test_sync_order_refreshes_position_after_new_fill(
    mock_fetch_order: Mock,
    mock_inquire_orders: Mock,
    mock_save_execution: Mock,
    mock_update_order: Mock,
):
    local_order = LOCAL_ORDER.copy()

    mock_fetch_order.return_value = local_order

    mock_inquire_orders.return_value = {
        "rt_cd": "0",
        "output1": [
            {
                "odno": "0000012345",
                "tot_ccld_qty": "4",
                "avg_prvs": "70000",
                "cncl_yn": "N",
                "ord_dvsn_name": "시장가",
                "rjct_rson": "",
                "ord_dt": "20260712",
                "ord_tmd": "103000",
            }
        ],
    }

    mock_save_execution.return_value = 1
    mock_position_refresh = Mock()

    manager = ExecutionManager(
        position_refresher=mock_position_refresh,
    )

    result = manager.sync_order("0000012345")

    mock_position_refresh.assert_called_once_with()

    assert result["position_refreshed"] is True
    assert result["position_refresh_error"] is None
@patch(
    "trading.execution_manager.update_order_execution"
)
@patch(
    "trading.execution_manager.save_execution"
)
@patch(
    "trading.execution_manager.inquire_daily_orders"
)
@patch(
    "trading.execution_manager.fetch_order_by_order_no"
)
def test_sync_order_does_not_refresh_without_new_fill(
    mock_fetch_order: Mock,
    mock_inquire_orders: Mock,
    mock_save_execution: Mock,
    mock_update_order: Mock,
):
    local_order = LOCAL_ORDER.copy()
    local_order["execution_status"] = "PARTIAL"
    local_order["filled_quantity"] = 4
    local_order["remaining_quantity"] = 6
    local_order["average_fill_price"] = 70000

    mock_fetch_order.return_value = local_order

    mock_inquire_orders.return_value = {
        "rt_cd": "0",
        "output1": [
            {
                "odno": "0000012345",
                "tot_ccld_qty": "4",
                "avg_prvs": "70000",
                "cncl_yn": "N",
                "ord_dvsn_name": "시장가",
                "rjct_rson": "",
            }
        ],
    }

    mock_position_refresh = Mock()

    manager = ExecutionManager(
        position_refresher=mock_position_refresh,
    )

    result = manager.sync_order("0000012345")

    mock_position_refresh.assert_not_called()

    assert result["position_refreshed"] is False
    assert result["position_refresh_error"] is None
@patch(
    "trading.execution_manager.update_order_execution"
)
@patch(
    "trading.execution_manager.save_execution"
)
@patch(
    "trading.execution_manager.inquire_daily_orders"
)
@patch(
    "trading.execution_manager.fetch_order_by_order_no"
)
def test_sync_order_keeps_execution_when_position_refresh_fails(
    mock_fetch_order: Mock,
    mock_inquire_orders: Mock,
    mock_save_execution: Mock,
    mock_update_order: Mock,
):
    mock_fetch_order.return_value = LOCAL_ORDER.copy()

    mock_inquire_orders.return_value = {
        "rt_cd": "0",
        "output1": [
            {
                "odno": "0000012345",
                "tot_ccld_qty": "4",
                "avg_prvs": "70000",
                "cncl_yn": "N",
                "ord_dvsn_name": "시장가",
                "rjct_rson": "",
                "ord_dt": "20260712",
                "ord_tmd": "103000",
            }
        ],
    }

    mock_save_execution.return_value = 1

    mock_position_refresh = Mock(
        side_effect=RuntimeError(
            "계좌 잔고 조회 실패"
        )
    )

    manager = ExecutionManager(
        position_refresher=mock_position_refresh,
    )

    result = manager.sync_order("0000012345")

    mock_save_execution.assert_called_once()
    mock_update_order.assert_called_once()
    mock_position_refresh.assert_called_once()

    assert result["execution_status"] == "PARTIAL"
    assert result["execution_id"] == 1
    assert result["position_refreshed"] is False
    assert (
        result["position_refresh_error"]
        == "계좌 잔고 조회 실패"
    )
def test_execution_manager_rejects_invalid_position_refresher():
    with pytest.raises(
        TypeError,
        match="호출 가능한 함수",
    ):
        ExecutionManager(
            position_refresher="not-callable",
        )