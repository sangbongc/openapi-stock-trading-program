import time
from unittest.mock import Mock

import pytest

from trading.trading_controller import (
    TradingController,
    TradingStatus,
)


TEST_UNIVERSE = [
    {
        "stock_code": "005930",
        "name": "삼성전자",
    },
    {
        "stock_code": "000660",
        "name": "SK하이닉스",
    },
]


def make_controller(
    interval_seconds: float = 0.05,
) -> tuple[TradingController, Mock, Mock]:
    """
    테스트용 TradingController와 Mock 객체를 생성한다.
    """
    trading_engine = Mock()
    execution_manager = Mock()

    execution_manager.sync_open_orders.return_value = []
    trading_engine.run_all.return_value = [
        {
            "stock_code": "005930",
            "action": "HOLD",
            "ordered": False,
        },
        {
            "stock_code": "000660",
            "action": "HOLD",
            "ordered": False,
        },
    ]

    controller = TradingController(
        trading_engine=trading_engine,
        execution_manager=execution_manager,
        stock_universe=TEST_UNIVERSE,
        interval_seconds=interval_seconds,
    )

    return (
        controller,
        trading_engine,
        execution_manager,
    )


def wait_until(
    condition,
    timeout: float = 1.0,
    interval: float = 0.01,
) -> bool:
    """
    비동기 작업이 특정 상태에 도달할 때까지 기다린다.

    time.sleep()을 고정적으로 길게 사용하는 대신,
    조건을 짧은 간격으로 확인한다.
    """
    end_time = time.monotonic() + timeout

    while time.monotonic() < end_time:
        if condition():
            return True

        time.sleep(interval)

    return condition()


def test_controller_initial_state_is_stopped():
    controller, _, _ = make_controller()

    assert controller.get_status() == (
        TradingStatus.STOPPED.value
    )

    state = controller.get_state()

    assert state["status"] == "STOPPED"
    assert state["worker_alive"] is False
    assert state["stock_count"] == 2
    assert state["last_error"] is None
    assert state["last_results"] == []
    assert state["last_execution_results"] == []


def test_run_once_syncs_orders_before_running_stocks():
    call_order = []

    trading_engine = Mock()
    execution_manager = Mock()

    def sync_orders():
        call_order.append("execution")
        return [
            {
                "order_no": "0000012345",
                "status": "FILLED",
            }
        ]

    def run_all(stocks):
        call_order.append("trading")

        assert stocks == TEST_UNIVERSE

        return [
            {
                "stock_code": "005930",
                "action": "HOLD",
                "ordered": False,
            }
        ]

    execution_manager.sync_open_orders.side_effect = (
        sync_orders
    )
    trading_engine.run_all.side_effect = run_all

    controller = TradingController(
        trading_engine=trading_engine,
        execution_manager=execution_manager,
        stock_universe=TEST_UNIVERSE,
        interval_seconds=1,
    )

    result = controller.run_once()

    assert result["success"] is True
    assert result["status"] == "STOPPED"
    assert call_order == [
        "execution",
        "trading",
    ]

    execution_manager.sync_open_orders.assert_called_once_with()
    trading_engine.run_all.assert_called_once_with(
        TEST_UNIVERSE
    )

    assert result["execution_results"] == [
        {
            "order_no": "0000012345",
            "status": "FILLED",
        }
    ]

    assert result["trading_results"] == [
        {
            "stock_code": "005930",
            "action": "HOLD",
            "ordered": False,
        }
    ]


def test_run_once_saves_latest_results():
    (
        controller,
        trading_engine,
        execution_manager,
    ) = make_controller()

    execution_results = [
        {
            "order_no": "0000012345",
            "status": "FILLED",
        }
    ]

    trading_results = [
        {
            "stock_code": "005930",
            "action": "BUY_ORDER",
            "ordered": True,
        }
    ]

    execution_manager.sync_open_orders.return_value = (
        execution_results
    )
    trading_engine.run_all.return_value = trading_results

    result = controller.run_once()

    assert result["success"] is True

    assert controller.last_execution_results == (
        execution_results
    )
    assert controller.last_results == trading_results

    state = controller.get_state()

    assert state["last_execution_results"] == (
        execution_results
    )
    assert state["last_results"] == trading_results


def test_start_runs_controller_in_worker_thread():
    (
        controller,
        trading_engine,
        execution_manager,
    ) = make_controller(
        interval_seconds=1,
    )

    result = controller.start()

    assert result["success"] is True

    assert wait_until(
        lambda: trading_engine.run_all.call_count >= 1
    )

    assert controller.get_status() == "RUNNING"

    execution_manager.sync_open_orders.assert_called()
    trading_engine.run_all.assert_called_with(
        TEST_UNIVERSE
    )

    stop_result = controller.stop(
        wait=True,
        timeout=1,
    )

    assert stop_result["success"] is True
    assert controller.get_status() == "STOPPED"


def test_start_prevents_duplicate_worker_thread():
    controller, trading_engine, _ = make_controller(
        interval_seconds=1,
    )

    first_result = controller.start()

    assert first_result["success"] is True

    assert wait_until(
        lambda: trading_engine.run_all.call_count >= 1
    )

    second_result = controller.start()

    assert second_result["success"] is False
    assert second_result["status"] == "RUNNING"
    assert "이미 실행 중" in second_result["message"]

    controller.stop(
        wait=True,
        timeout=1,
    )


def test_stop_interrupts_interval_wait():
    controller, trading_engine, _ = make_controller(
        interval_seconds=10,
    )

    controller.start()

    assert wait_until(
        lambda: trading_engine.run_all.call_count >= 1
    )

    start_time = time.monotonic()

    result = controller.stop(
        wait=True,
        timeout=1,
    )

    elapsed = time.monotonic() - start_time

    assert result["success"] is True
    assert controller.get_status() == "STOPPED"

    # Event.wait()를 사용하므로 10초 주기를 기다리지 않고
    # stop 요청에 빠르게 반응해야 한다.
    assert elapsed < 1


def test_stop_returns_false_when_already_stopped():
    controller, _, _ = make_controller()

    result = controller.stop()

    assert result["success"] is False
    assert result["status"] == "STOPPED"
    assert "실행 중이 아닙니다" in result["message"]


def test_run_once_is_blocked_while_running():
    controller, trading_engine, _ = make_controller(
        interval_seconds=1,
    )

    controller.start()

    assert wait_until(
        lambda: trading_engine.run_all.call_count >= 1
    )

    result = controller.run_once()

    assert result["success"] is False
    assert result["status"] == "RUNNING"
    assert "1회 실행할 수 없습니다" in result["message"]

    controller.stop(
        wait=True,
        timeout=1,
    )


def test_run_once_handles_execution_manager_error():
    (
        controller,
        trading_engine,
        execution_manager,
    ) = make_controller()

    execution_manager.sync_open_orders.side_effect = (
        RuntimeError("체결 조회 실패")
    )

    result = controller.run_once()

    assert result["success"] is False
    assert result["status"] == "STOPPED"
    assert result["error"] == "체결 조회 실패"
    assert controller.last_error == "체결 조회 실패"

    trading_engine.run_all.assert_not_called()


def test_run_once_handles_trading_engine_error():
    (
        controller,
        trading_engine,
        execution_manager,
    ) = make_controller()

    execution_results = [
        {
            "order_no": "0000012345",
            "status": "FILLED",
        }
    ]

    execution_manager.sync_open_orders.return_value = (
        execution_results
    )

    trading_engine.run_all.side_effect = RuntimeError(
        "전략 실행 실패"
    )

    result = controller.run_once()

    assert result["success"] is False
    assert result["error"] == "전략 실행 실패"
    assert controller.last_error == "전략 실행 실패"

    assert controller.last_execution_results == (
        execution_results
    )


def test_worker_stops_safely_after_cycle_error():
    (
        controller,
        trading_engine,
        execution_manager,
    ) = make_controller(
        interval_seconds=0.05,
    )

    execution_manager.sync_open_orders.side_effect = (
        RuntimeError("자동매매 주기 오류")
    )

    result = controller.start()

    assert result["success"] is True

    assert wait_until(
        lambda: controller.get_status() == "STOPPED"
    )

    assert controller.last_error == (
        "자동매매 주기 오류"
    )

    trading_engine.run_all.assert_not_called()

    state = controller.get_state()

    assert state["status"] == "STOPPED"
    assert state["worker_alive"] is False


def test_shutdown_stops_running_controller():
    controller, trading_engine, _ = make_controller(
        interval_seconds=10,
    )

    controller.start()

    assert wait_until(
        lambda: trading_engine.run_all.call_count >= 1
    )

    result = controller.shutdown(timeout=1)

    assert result["success"] is True
    assert controller.get_status() == "STOPPED"


def test_shutdown_succeeds_when_already_stopped():
    controller, _, _ = make_controller()

    result = controller.shutdown()

    assert result["success"] is True
    assert result["status"] == "STOPPED"
    assert "이미 중단" in result["message"]


def test_constructor_rejects_invalid_interval():
    trading_engine = Mock()
    execution_manager = Mock()

    trading_engine.run_all = Mock()
    execution_manager.sync_open_orders = Mock()

    with pytest.raises(ValueError):
        TradingController(
            trading_engine=trading_engine,
            execution_manager=execution_manager,
            stock_universe=TEST_UNIVERSE,
            interval_seconds=0,
        )


def test_constructor_rejects_missing_run_all():
    trading_engine = object()
    execution_manager = Mock()
    execution_manager.sync_open_orders = Mock()

    with pytest.raises(TypeError):
        TradingController(
            trading_engine=trading_engine,
            execution_manager=execution_manager,
            stock_universe=TEST_UNIVERSE,
        )


def test_constructor_rejects_missing_sync_open_orders():
    trading_engine = Mock()
    trading_engine.run_all = Mock()
    execution_manager = object()

    with pytest.raises(TypeError):
        TradingController(
            trading_engine=trading_engine,
            execution_manager=execution_manager,
            stock_universe=TEST_UNIVERSE,
        )