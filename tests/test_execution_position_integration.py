from unittest.mock import Mock, patch

from trading.execution_manager import ExecutionManager


LOCAL_BUY_ORDER = {
    "id": 1,
    "stock_code": "005930",
    "side": "BUY",
    "order_type": "MARKET",
    "quantity": 10,
    "price": 0,
    "status": "ACCEPTED",
    "order_no": "0000012345",
    "execution_status": "PENDING",
    "filled_quantity": 0,
    "remaining_quantity": 10,
    "average_fill_price": 0,
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
def test_new_buy_execution_refreshes_position_manager(
    mock_fetch_order: Mock,
    mock_inquire_orders: Mock,
    mock_save_execution: Mock,
    mock_update_order: Mock,
):
    """
    매수 신규 체결이 발생하면 PositionManager.refresh()가
    한 번 호출되는지 확인한다.
    """
    mock_fetch_order.return_value = LOCAL_BUY_ORDER.copy()

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

    mock_position_refresher = Mock()

    manager = ExecutionManager(
        position_refresher=mock_position_refresher,
    )

    result = manager.sync_order("0000012345")

    assert result["newly_filled_quantity"] == 4
    assert result["position_refreshed"] is True
    assert result["position_refresh_error"] is None

    mock_position_refresher.assert_called_once_with()
    mock_save_execution.assert_called_once()
    mock_update_order.assert_called_once()
    mock_save_execution.assert_called_once()
    mock_update_order.assert_called_once()


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
def test_no_new_execution_does_not_refresh_position_manager(
    mock_fetch_order: Mock,
    mock_inquire_orders: Mock,
    mock_save_execution: Mock,
    mock_update_order: Mock,
):
    """
    새 체결이 없다면 PositionManager.refresh()를 호출하지
    않는지 확인한다.
    """
    local_order = LOCAL_BUY_ORDER.copy()
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
                "ord_dt": "20260712",
                "ord_tmd": "103000",
            }
        ],
    }

    mock_position_refresher = Mock()

    manager = ExecutionManager(
        position_refresher=mock_position_refresher,
    )

    result = manager.sync_order("0000012345")

    assert result["newly_filled_quantity"] == 0
    assert result["position_refreshed"] is False
    assert result["position_refresh_error"] is None

    mock_position_refresher.assert_not_called()
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
def test_execution_manager_works_without_position_manager(
    mock_fetch_order: Mock,
    mock_inquire_orders: Mock,
    mock_save_execution: Mock,
    mock_update_order: Mock,
):
    """
    PositionManager를 전달하지 않아도 기존 방식대로
    ExecutionManager가 정상 작동하는지 확인한다.
    """
    mock_fetch_order.return_value = LOCAL_BUY_ORDER.copy()

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
                "ord_tmd": "103100",
            }
        ],
    }

    mock_save_execution.return_value = 1

    manager = ExecutionManager()

    result = manager.sync_order("0000012345")

    assert result["newly_filled_quantity"] == 10
    assert result["position_refreshed"] is False

    mock_save_execution.assert_called_once()
    mock_update_order.assert_called_once()


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
def test_sell_execution_refreshes_position_manager(
    mock_fetch_order: Mock,
    mock_inquire_orders: Mock,
    mock_save_execution: Mock,
    mock_update_order: Mock,
):
    """
    매도 체결도 매수 체결과 동일하게 포지션 갱신을
    발생시키는지 확인한다.
    """
    sell_order = LOCAL_BUY_ORDER.copy()
    sell_order.update(
        {
            "id": 2,
            "side": "SELL",
            "quantity": 3,
            "order_no": "0000054321",
            "remaining_quantity": 3,
        }
    )

    mock_fetch_order.return_value = sell_order

    mock_inquire_orders.return_value = {
        "rt_cd": "0",
        "output1": [
            {
                "odno": "0000054321",
                "tot_ccld_qty": "3",
                "avg_prvs": "70500",
                "cncl_yn": "N",
                "ord_dvsn_name": "시장가",
                "rjct_rson": "",
                "ord_dt": "20260712",
                "ord_tmd": "104000",
            }
        ],
    }

    mock_save_execution.return_value = 2

    mock_position_refresher = Mock()

    manager = ExecutionManager(
    position_refresher=mock_position_refresher,)

    result = manager.sync_order("0000054321")

    assert result["newly_filled_quantity"] == 3
    assert result["position_refreshed"] is True
    assert result["position_refresh_error"] is None

    mock_position_refresher.assert_called_once_with()
    mock_save_execution.assert_called_once()
    mock_update_order.assert_called_once()