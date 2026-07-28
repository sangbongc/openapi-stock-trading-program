from __future__ import annotations

from api import get_account_balance
from config import (
    DEFAULT_BUY_QUANTITY,
    TRADING_DRY_RUN,
)
from trading.data_provider import prepare_strategy_data
from database import (
    create_tables,
    fetch_open_orders,
    migrate_orders_table,
)
from trading import (
    ExecutionManager,
    OrderManager,
    PositionManager,
    TradingController,
    TradingEngine,
)
from strategies import (
    StrategyEngine,
    StrategyFactory,
)
from universe import STOCK_UNIVERSE


MINIMUM_DATA_LENGTH = 120

STRATEGY_NAMES = [
    "ma_cross",
    "rsi",
    "macd",
    "bollinger",
]

TRADING_INTERVAL_SECONDS = 300.0


def has_open_order(stock_code: str) -> bool:
    """
    특정 종목에 아직 체결이 완료되지 않은 주문이
    존재하는지 확인한다.

    TradingEngine이 같은 종목에 중복 주문을
    생성하지 못하도록 하는 검사 함수다.
    """
    normalized_code = str(stock_code).strip()

    open_orders = fetch_open_orders()

    return any(
        str(order.get("stock_code", "")).strip()
        == normalized_code
        for order in open_orders
    )


def build_controller() -> TradingController:
    """
    자동매매 프로그램에 필요한 객체를 생성하고
    서로 연결한 뒤 TradingController를 반환한다.
    """
    create_tables()
    migrate_orders_table()

    strategies = StrategyFactory.create_strategies(
        STRATEGY_NAMES
    )

    strategy_engine = StrategyEngine(
        strategies=strategies,
        buy_threshold=0.2,
        sell_threshold=-0.2,
    )

    position_manager = PositionManager(
        balance_fetcher=get_account_balance,
    )

    # 프로그램 시작 시 실제 계좌 보유 상태를 먼저 반영한다.
    # 이를 생략하면 PositionManager가 빈 상태로 시작하여
    # 기존 보유 종목을 미보유로 판단할 수 있다.
    position_manager.refresh()

    order_manager = OrderManager()

    execution_manager = ExecutionManager(
        position_manager=position_manager,
        position_refresher=position_manager.refresh,
    )

    trading_engine = TradingEngine(
        strategy_engine=strategy_engine,
        order_manager=order_manager,
        position_manager=position_manager,
        data_provider=prepare_strategy_data,
        default_buy_quantity=DEFAULT_BUY_QUANTITY,
        pending_order_checker=has_open_order,
        minimum_data_length=MINIMUM_DATA_LENGTH,
        dry_run=TRADING_DRY_RUN,
    )

    return TradingController(
        trading_engine=trading_engine,
        execution_manager=execution_manager,
        order_manager=order_manager,
        position_manager=position_manager,
        stock_universe=STOCK_UNIVERSE,
        interval_seconds=TRADING_INTERVAL_SECONDS,
        sync_interval_seconds=10.0,
    )