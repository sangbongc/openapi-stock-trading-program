from pathlib import Path
from unittest.mock import patch

import pytest

from database import (
    create_tables,
    fetch_executions,
    fetch_executions_by_order_id,
    fetch_executions_by_order_no,
    get_average_execution_price,
    get_connection,
    get_total_executed_quantity,
    save_execution,
    save_order
)
@pytest.fixture
def test_database(tmp_path: Path):
    test_db_path = tmp_path / "test_trading.db"

    with patch(
        "database.DB_PATH",
        str(test_db_path),
    ):
        create_tables()

        order_id = save_order(
            stock_code="005930",
            side="BUY",
            order_type="MARKET",
            quantity=10,
            price=0,
            status="ACCEPTED",
            order_no="0000012345",
            message_code="APBK0013",
            message="주문 접수 완료",
        )

        yield {
            "db_path": str(test_db_path),
            "order_id": order_id,
        }
def test_save_execution(test_database):
    with patch(
        "database.DB_PATH",
        test_database["db_path"],
    ):
        execution_id = save_execution(
            order_id=test_database["order_id"],
            order_no="0000012345",
            stock_code="005930",
            side="BUY",
            quantity=4,
            price=70000,
            executed_at="2026-07-12 10:30:00",
        )

        assert execution_id is not None

        executions = fetch_executions_by_order_no(
            "0000012345"
        )

        assert len(executions) == 1
        assert executions[0]["quantity"] == 4
        assert executions[0]["price"] == 70000
        assert executions[0]["side"] == "BUY"

def test_duplicate_execution_is_ignored(
    test_database,
):
    with patch(
        "database.DB_PATH",
        test_database["db_path"],
    ):
        first_id = save_execution(
            order_id=test_database["order_id"],
            order_no="0000012345",
            stock_code="005930",
            side="BUY",
            quantity=4,
            price=70000,
            executed_at="2026-07-12 10:30:00",
        )

        second_id = save_execution(
            order_id=test_database["order_id"],
            order_no="0000012345",
            stock_code="005930",
            side="BUY",
            quantity=4,
            price=70000,
            executed_at="2026-07-12 10:30:00",
        )

        assert first_id is not None
        assert second_id is None

        executions = fetch_executions_by_order_no(
            "0000012345"
        )

        assert len(executions) == 1

def test_multiple_executions(test_database):
    with patch(
        "database.DB_PATH",
        test_database["db_path"],
    ):
        save_execution(
            order_id=test_database["order_id"],
            order_no="0000012345",
            stock_code="005930",
            side="BUY",
            quantity=4,
            price=70000,
            executed_at="2026-07-12 10:30:00",
        )

        save_execution(
            order_id=test_database["order_id"],
            order_no="0000012345",
            stock_code="005930",
            side="BUY",
            quantity=3,
            price=70100,
            executed_at="2026-07-12 10:31:00",
        )

        executions = fetch_executions_by_order_id(
            test_database["order_id"]
        )

        assert len(executions) == 2
        assert executions[0]["quantity"] == 4
        assert executions[1]["quantity"] == 3

def test_get_total_executed_quantity(
    test_database,
):
    with patch(
        "database.DB_PATH",
        test_database["db_path"],
    ):
        save_execution(
            order_id=test_database["order_id"],
            order_no="0000012345",
            stock_code="005930",
            side="BUY",
            quantity=4,
            price=70000,
            executed_at="2026-07-12 10:30:00",
        )

        save_execution(
            order_id=test_database["order_id"],
            order_no="0000012345",
            stock_code="005930",
            side="BUY",
            quantity=3,
            price=70100,
            executed_at="2026-07-12 10:31:00",
        )

        total_quantity = get_total_executed_quantity(
            "0000012345"
        )

        assert total_quantity == 7

def test_get_average_execution_price(
    test_database,
):
    with patch(
        "database.DB_PATH",
        test_database["db_path"],
    ):
        save_execution(
            order_id=test_database["order_id"],
            order_no="0000012345",
            stock_code="005930",
            side="BUY",
            quantity=4,
            price=70000,
            executed_at="2026-07-12 10:30:00",
        )

        save_execution(
            order_id=test_database["order_id"],
            order_no="0000012345",
            stock_code="005930",
            side="BUY",
            quantity=3,
            price=70100,
            executed_at="2026-07-12 10:31:00",
        )

        average_price = get_average_execution_price(
            "0000012345"
        )

        expected_price = (
            4 * 70000
            + 3 * 70100
        ) / 7

        assert average_price == pytest.approx(
            expected_price
        )

def test_fetch_executions(test_database):
    with patch(
        "database.DB_PATH",
        test_database["db_path"],
    ):
        save_execution(
            order_id=test_database["order_id"],
            order_no="0000012345",
            stock_code="005930",
            side="BUY",
            quantity=4,
            price=70000,
            executed_at="2026-07-12 10:30:00",
        )

        executions = fetch_executions(limit=10)

        assert len(executions) == 1
        assert executions[0]["stock_code"] == "005930"