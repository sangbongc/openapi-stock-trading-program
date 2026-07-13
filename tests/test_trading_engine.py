from unittest.mock import Mock

import pandas as pd

from strategies.signal import Signal
from strategies.strategy_engine import EngineResult
from trading.trading_engine import TradingEngine


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
    """
    LIVE 모드에서 BUY 신호가 발생하고 미보유 상태이면
    매수 주문을 생성하는지 확인한다.
    """
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
        dry_run=False,
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


def test_buy_signal_dry_run_does_not_send_order():
    """
    Dry-run 모드에서 BUY 신호가 발생해도
    실제 매수 주문을 호출하지 않는지 확인한다.
    """
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()

    data_provider.return_value = make_test_data()

    strategy_engine.run.return_value = (
        make_strategy_result(Signal.BUY)
    )

    position_manager.get_position.return_value = None

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
        dry_run=True,
    )

    result = engine.run_stock("005930")

    assert result["signal"] == Signal.BUY
    assert result["action"] == "BUY_SIMULATED"
    assert result["ordered"] is False
    assert "Dry-run" in result["reason"]

    order_manager.buy.assert_not_called()
    order_manager.sell.assert_not_called()


def test_buy_signal_skips_when_already_holding():
    """
    BUY 신호가 발생해도 이미 보유 중이면
    추가 매수하지 않는지 확인한다.
    """
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
        dry_run=True,
    )

    result = engine.run_stock("005930")

    assert result["signal"] == Signal.BUY
    assert result["action"] == "SKIP"
    assert result["ordered"] is False

    order_manager.buy.assert_not_called()
    order_manager.sell.assert_not_called()


def test_sell_signal_orders_all_position_quantity():
    """
    LIVE 모드에서 SELL 신호가 발생하면
    보유 수량 전부를 매도 주문하는지 확인한다.
    """
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
        dry_run=False,
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


def test_sell_signal_dry_run_does_not_send_order():
    """
    Dry-run 모드에서 SELL 신호가 발생해도
    실제 매도 주문을 호출하지 않는지 확인한다.
    """
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

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
        dry_run=True,
    )

    result = engine.run_stock("005930")

    assert result["signal"] == Signal.SELL
    assert result["action"] == "SELL_SIMULATED"
    assert result["ordered"] is False
    assert "Dry-run" in result["reason"]

    order_manager.buy.assert_not_called()
    order_manager.sell.assert_not_called()


def test_sell_signal_skips_when_not_holding():
    """
    SELL 신호가 발생해도 보유 수량이 없으면
    매도 주문을 생성하지 않는지 확인한다.
    """
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
        dry_run=True,
    )

    result = engine.run_stock("005930")

    assert result["signal"] == Signal.SELL
    assert result["action"] == "SKIP"
    assert result["ordered"] is False

    order_manager.buy.assert_not_called()
    order_manager.sell.assert_not_called()


def test_hold_signal_does_not_order():
    """
    HOLD 신호에서는 주문이 생성되지 않는지 확인한다.
    """
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
        dry_run=True,
    )

    result = engine.run_stock("005930")

    assert result["signal"] == Signal.HOLD
    assert result["action"] == "HOLD"
    assert result["ordered"] is False

    order_manager.buy.assert_not_called()
    order_manager.sell.assert_not_called()


def test_insufficient_data_skips_strategy():
    """
    가격 데이터가 부족하면 전략을 실행하지 않고
    해당 종목을 건너뛰는지 확인한다.
    """
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
        dry_run=True,
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
    """
    처리 중인 주문이 있으면 새로운 전략 및 주문을
    실행하지 않는지 확인한다.
    """
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
        dry_run=True,
    )

    result = engine.run_stock("005930")

    assert result["action"] == "SKIP"
    assert result["ordered"] is False
    assert "처리 중인 주문" in result["reason"]

    pending_order_checker.assert_called_once_with(
        "005930"
    )

    strategy_engine.run.assert_not_called()
    position_manager.get_position.assert_not_called()
    order_manager.buy.assert_not_called()
    order_manager.sell.assert_not_called()


def test_rejected_buy_order_returns_ordered_false():
    """
    LIVE 모드에서 매수 주문이 거절되면
    ordered가 False로 반환되는지 확인한다.
    """
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
        dry_run=False,
    )

    result = engine.run_stock("005930")

    assert result["signal"] == Signal.BUY
    assert result["action"] == "BUY_REJECTED"
    assert result["ordered"] is False

    order_manager.buy.assert_called_once_with(
        stock_code="005930",
        quantity=1,
        order_type="MARKET",
    )

    order_manager.sell.assert_not_called()


def test_rejected_sell_order_returns_ordered_false():
    """
    LIVE 모드에서 매도 주문이 거절되면
    ordered가 False로 반환되는지 확인한다.
    """
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
        "success": False,
        "status": "REJECTED",
        "message": "주문 실패",
    }

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
        dry_run=False,
    )

    result = engine.run_stock("005930")

    assert result["signal"] == Signal.SELL
    assert result["action"] == "SELL_REJECTED"
    assert result["ordered"] is False

    order_manager.sell.assert_called_once_with(
        stock_code="005930",
        quantity=3,
        order_type="MARKET",
    )

    order_manager.buy.assert_not_called()


def test_run_all_executes_all_stock_codes():
    """
    여러 종목 코드가 전달되면 각 종목을
    모두 실행하는지 확인한다.
    """
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
        dry_run=True,
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
    """
    종목 정보 딕셔너리 목록을 전달받아
    종목명까지 결과에 포함하는지 확인한다.
    """
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
        dry_run=True,
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
    """
    특정 종목의 데이터 조회에서 오류가 발생해도
    나머지 종목을 계속 실행하는지 확인한다.
    """
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()

    def provide_data(
        stock_code: str,
    ) -> pd.DataFrame:
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
        dry_run=True,
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
    """
    빈 종목 목록을 전달하면 빈 결과 목록을
    반환하는지 확인한다.
    """
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=data_provider,
        dry_run=True,
    )

    results = engine.run_all([])

    assert results == []

    data_provider.assert_not_called()
    strategy_engine.run.assert_not_called()
    order_manager.buy.assert_not_called()
    order_manager.sell.assert_not_called()


def test_extracts_signal_from_engine_result():
    """
    실제 EngineResult 객체에서 final_signal을
    정상적으로 추출하는지 확인한다.
    """
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
        dry_run=True,
    )

    result = engine.run_stock("005930")

    assert result["signal"] == Signal.HOLD
    assert result["action"] == "HOLD"
    assert result["ordered"] is False

    order_manager.buy.assert_not_called()
    order_manager.sell.assert_not_called()


def test_dry_run_must_be_boolean():
    """
    dry_run에는 bool 값만 전달할 수 있는지 확인한다.
    """
    strategy_engine = Mock()
    order_manager = Mock()
    position_manager = Mock()
    data_provider = Mock()

    try:
        TradingEngine(
            strategy_engine=strategy_engine,
            order_manager=order_manager,
            position_manager=position_manager,
            data_provider=data_provider,
            dry_run="True",
        )

    except TypeError as error:
        assert "dry_run" in str(error)

    else:
        raise AssertionError(
            "dry_run이 bool이 아닌데도 TypeError가 발생하지 않았습니다."
        )

