from __future__ import annotations

from api import get_account_balance
from config import (
    DEFAULT_BUY_QUANTITY,
    TRADING_DRY_RUN,
    )
from console.presenters import (
    print_account, 
    print_banner,
    print_collect_results,
    print_help,
    print_run_result,
    print_status,
    print_trading_results,
)
from console.manual_order import (
    run_manual_menu,
)
from database import (
    create_tables,
    fetch_open_orders,
    migrate_orders_table,
)
from strategies import (
    StrategyEngine,
    StrategyFactory,
)
from trading import (
    ExecutionManager,
    OrderManager,
    PositionManager,
    TradingController,
    TradingEngine,
)
from trading.data_provider import prepare_strategy_data
from universe import STOCK_UNIVERSE
from data_collector import collect_daily_prices


DAILY_PRICE_TARGET_ROWS = 1000
DAILY_PRICE_LOOKBACK_DAYS = 500
DAILY_PRICE_MAX_REQUESTS = 15

TRADING_INTERVAL_SECONDS = 300.0

MINIMUM_DATA_LENGTH = 120

STRATEGY_NAMES = [
    "ma_cross",
    "rsi",
    "macd",
    "bollinger",
]


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



def command_loop(
    controller: TradingController,
) -> None:
    """
    사용자 명령어를 받아 TradingController에 전달한다.
    """
    print_help()

    while True:
        try:
            command = input(
                "\ncommand> "
            ).strip().lower()

        except EOFError:
            command = "exit"

        except KeyboardInterrupt:
            print()
            print("종료 요청을 받았습니다.")
            command = "exit"

        if not command:
            continue

        if command == "start":
            result = controller.start()
            print(result["message"])

        elif command == "stop":
            result = controller.stop(
                wait=True,
                timeout=10,
            )
            print(result["message"])

        elif command == "run":
            result = controller.run_once()
            print_run_result(result)
        elif command == "manual":
            run_manual_menu(controller)
        elif command == "collect":
            run_collection(controller)
        elif command == "balance":
            result = controller.get_account()
            print_account(result)
        elif command == "sync":
            result = controller.sync()

            print()

            if result["success"]:
                print(result["message"])
                print(
                    f"총 {len(result['execution_results'])}건, "
                    f"변경 {result['changed']}건, "
                    f"오류 {result['errors']}건"
                )

            else:
                print(result["message"])
        elif command == "status":
            print_status(
                controller.get_state()
            )

        elif command == "results":
            state = controller.get_state()
            results = state.get("last_results", [])
            print_trading_results(results)

        elif command == "help":
            print_help()

        elif command in {"exit", "quit"}:
            result = controller.shutdown(
                timeout=10,
            )
            print(result["message"])
            print("프로그램을 종료합니다.")
            break

        else:
            print(
                "알 수 없는 명령어입니다. "
                "help를 입력해 명령어를 확인하세요."
            )


def run_collection(
    controller: TradingController,
) -> None:
    """
    전체 투자 대상 종목의 과거 일봉을 수집한다.
    """
    state = controller.get_state()

    if state["status"] != "STOPPED":
        print(
            "자동매매가 실행 중이거나 중단 처리 중입니다. "
            "stop 명령 후 데이터를 수집하세요."
        )
        return

    print()
    print(
        "전체 종목의 과거 일봉 수집을 시작합니다."
    )
    print(
        f"종목별 목표: "
        f"{DAILY_PRICE_TARGET_ROWS}개"
    )

    results = collect_daily_prices(
        stock_universe=STOCK_UNIVERSE,
        target_rows=DAILY_PRICE_TARGET_ROWS,
        lookback_days=DAILY_PRICE_LOOKBACK_DAYS,
        max_requests_per_stock=(
            DAILY_PRICE_MAX_REQUESTS
        ),
    )

    print_collect_results(results)


def main() -> None:
    """
    자동매매 애플리케이션 진입점.
    """
    controller: TradingController | None = None

    try:
        print_banner()
        print("프로그램을 초기화하고 있습니다.")

        controller = build_controller()

        print("초기화가 완료되었습니다.")
        print(
            f"대상 종목: {len(STOCK_UNIVERSE)}개"
        )
        print(
            "자동매매 반복 주기: "
            f"{TRADING_INTERVAL_SECONDS:.0f}초"
        )

        command_loop(controller)

    except KeyboardInterrupt:
        print()
        print("프로그램 종료 요청을 받았습니다.")

    except Exception as error:
        print()
        print(
            "프로그램 초기화 또는 실행 중 "
            f"오류가 발생했습니다: {error}"
        )

    finally:
        if controller is not None:
            shutdown_result = controller.shutdown(
                timeout=10,
            )

            if (
                shutdown_result.get("status")
                != "STOPPED"
            ):
                print(
                    "자동매매 작업이 완전히 "
                    "종료되지 않았을 수 있습니다."
                )


if __name__ == "__main__":
    main()

