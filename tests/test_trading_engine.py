from unittest.mock import Mock

import pandas as pd

from strategies.signal import Signal
from trading.trading_engine import TradingEngine
from strategies.strategy_engine import EngineResult

def make_test_data(
    row_count: int = 120,
) -> pd.DataFrame:
    """
    TradingEngine 테스트에 사용할 DataFrame을 생성한다.
    """
    return pd.DataFrame(
        {
            "close": list(
                range(100, 100 + row_count)
            )
        }
    )


def make_strategy_result(
    signal: Signal,
) -> dict:
    """
    StrategyEngine의 반환값과 유사한 테스트 결과를 만든다.
    """
    return {
        "results": {},
        "final_signal": signal,
    }


def test_buy_signal_orders_when_not_holding():
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()

    data_provider.return_value = make_test_data()

    strategy_engine.run.return_value = (
        make_strategy_result(Signal.BUY)
    )

    position_manager.get_position.return_value = None

    order_manager.buy.return_value = {
    "success": True,
    "status": "ACCEPTED",
    "order_id": 1,
    "order_no": "0000012345",
    "side": "BUY",
}

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
    )

    result = engine.run_stock("005930")

    assert result["signal"] == Signal.BUY
    assert result["action"] == "BUY_ORDER"
    assert result["ordered"] is True

    order_manager.buy.assert_called_once_with(
        stock_code="005930",
        quantity=1,
        order_type="MARKET",
    )

    order_manager.sell.assert_not_called()


def test_buy_signal_skips_when_already_holding():
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()

    data_provider.return_value = make_test_data()

    strategy_engine.run.return_value = (
        make_strategy_result(Signal.BUY)
    )

    position_manager.get_position.return_value = {
        "stock_code": "005930",
        "quantity": 3,
    }

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
    )

    result = engine.run_stock("005930")

    assert result["signal"] == Signal.BUY
    assert result["action"] == "SKIP"
    assert result["ordered"] is False

    order_manager.buy.assert_not_called()
    order_manager.sell.assert_not_called()


def test_sell_signal_orders_all_position_quantity():
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()

    data_provider.return_value = make_test_data()

    strategy_engine.run.return_value = (
        make_strategy_result(Signal.SELL)
    )

    position_manager.get_position.return_value = {
        "stock_code": "005930",
        "quantity": 3,
    }

    order_manager.sell.return_value = {
    "success": True,
    "status": "ACCEPTED",
    "order_id": 2,
    "order_no": "0000012346",
    "side": "SELL",
}

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
    )

    result = engine.run_stock("005930")

    assert result["signal"] == Signal.SELL
    assert result["action"] == "SELL_ORDER"
    assert result["ordered"] is True

    order_manager.sell.assert_called_once_with(
        stock_code="005930",
        quantity=3,
        order_type="MARKET",
    )

    order_manager.buy.assert_not_called()


def test_sell_signal_skips_when_not_holding():
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()

    data_provider.return_value = make_test_data()

    strategy_engine.run.return_value = (
        make_strategy_result(Signal.SELL)
    )

    position_manager.get_position.return_value = None

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
    )

    result = engine.run_stock("005930")

    assert result["signal"] == Signal.SELL
    assert result["action"] == "SKIP"
    assert result["ordered"] is False

    order_manager.buy.assert_not_called()
    order_manager.sell.assert_not_called()


def test_hold_signal_does_not_order():
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()

    data_provider.return_value = make_test_data()

    strategy_engine.run.return_value = (
        make_strategy_result(Signal.HOLD)
    )

    position_manager.get_position.return_value = {
        "stock_code": "005930",
        "quantity": 2,
    }

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
    )

    result = engine.run_stock("005930")

    assert result["signal"] == Signal.HOLD
    assert result["action"] == "HOLD"
    assert result["ordered"] is False

    order_manager.buy.assert_not_called()
    order_manager.sell.assert_not_called()


def test_insufficient_data_skips_strategy():
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()

    data_provider.return_value = make_test_data(
        row_count=50
    )

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
        minimum_data_length=120,
    )

    result = engine.run_stock("005930")

    assert result["signal"] == Signal.HOLD
    assert result["action"] == "SKIP"
    assert result["ordered"] is False
    assert "데이터가 부족" in result["reason"]

    strategy_engine.run.assert_not_called()
    position_manager.get_position.assert_not_called()
    order_manager.buy.assert_not_called()
    order_manager.sell.assert_not_called()


def test_pending_order_prevents_new_order():
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()
    pending_order_checker = Mock()

    data_provider.return_value = make_test_data()
    pending_order_checker.return_value = True

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
        pending_order_checker=pending_order_checker,
    )

    result = engine.run_stock("005930")

    assert result["action"] == "SKIP"
    assert result["ordered"] is False
    assert "처리 중인 주문" in result["reason"]

    pending_order_checker.assert_called_once_with(
        "005930"
    )

    strategy_engine.run.assert_not_called()
    order_manager.buy.assert_not_called()
    order_manager.sell.assert_not_called()


def test_rejected_buy_order_returns_ordered_false():
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()

    data_provider.return_value = make_test_data()

    strategy_engine.run.return_value = (
        make_strategy_result(Signal.BUY)
    )

    position_manager.get_position.return_value = None

    order_manager.buy.return_value = {
    "success": False,
    "status": "REJECTED",
    "message": "주문 실패",
}

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
    )

    result = engine.run_stock("005930")

    assert result["signal"] == Signal.BUY
    assert result["action"] == "BUY_REJECTED"
    assert result["ordered"] is False
def test_run_all_executes_all_stock_codes():
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()

    data_provider.return_value = make_test_data()

    strategy_engine.run.return_value = (
        make_strategy_result(Signal.HOLD)
    )

    position_manager.get_position.return_value = None

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
    )

    results = engine.run_all(
        [
            "005930",
            "000660",
            "035420",
        ]
    )

    assert len(results) == 3

    assert results[0]["stock_code"] == "005930"
    assert results[1]["stock_code"] == "000660"
    assert results[2]["stock_code"] == "035420"

    assert all(
        result["signal"] == Signal.HOLD
        for result in results
    )

    assert data_provider.call_count == 3
    assert strategy_engine.run.call_count == 3
def test_run_all_accepts_stock_dictionaries():
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()

    data_provider.return_value = make_test_data()

    strategy_engine.run.return_value = (
        make_strategy_result(Signal.HOLD)
    )

    position_manager.get_position.return_value = None

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
    )

    stocks = [
        {
            "stock_code": "005930",
            "name": "삼성전자",
        },
        {
            "stock_code": "000660",
            "name": "SK하이닉스",
        },
    ]

    results = engine.run_all(stocks)

    assert len(results) == 2

    assert results[0]["stock_code"] == "005930"
    assert results[0]["stock_name"] == "삼성전자"

    assert results[1]["stock_code"] == "000660"
    assert results[1]["stock_name"] == "SK하이닉스"
def test_run_all_continues_after_stock_error():
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()

    def provide_data(stock_code: str):
        if stock_code == "000660":
            raise RuntimeError(
                "테스트 데이터 조회 오류"
            )

        return make_test_data()

    data_provider.side_effect = provide_data

    strategy_engine.run.return_value = (
        make_strategy_result(Signal.HOLD)
    )

    position_manager.get_position.return_value = None

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
    )

    results = engine.run_all(
        [
            "005930",
            "000660",
            "035420",
        ]
    )

    assert len(results) == 3

    assert results[0]["action"] == "HOLD"

    assert results[1]["stock_code"] == "000660"
    assert results[1]["action"] == "ERROR"
    assert results[1]["ordered"] is False

    assert results[2]["stock_code"] == "035420"
    assert results[2]["action"] == "HOLD"

    assert data_provider.call_count == 3
def test_run_all_returns_empty_list_for_empty_stocks():
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
    )

    results = engine.run_all([])

    assert results == []

    data_provider.assert_not_called()
    strategy_engine.run.assert_not_called()
    order_manager.buy.assert_not_called()
    order_manager.sell.assert_not_called()
def test_extracts_signal_from_engine_result():
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()

    data_provider.return_value = make_test_data()

    strategy_engine.run.return_value = EngineResult(
        final_signal=Signal.HOLD,
        confidence_score=0.0,
        final_confidence=1.0,
        strategy_results={},
    )

    position_manager.get_position.return_value = None

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
    )

    result = engine.run_stock("005930")

    assert result["signal"] == Signal.HOLD
    assert result["action"] == "HOLD"
    assert result["ordered"] is False

    order_manager.buy.assert_not_called()
    order_manager.sell.assert_not_called()

