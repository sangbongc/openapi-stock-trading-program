from __future__ import annotations

from typing import Any

from config import (DEFAULT_BUY_QUANTITY,TRADING_DRY_RUN)
from api import get_account_balance
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
from console.presenters import (
    print_account, 
    print_banner,
    print_collect_results,
    print_help,
    print_last_results,
    print_run_result,
    print_status,
)

DAILY_PRICE_TARGET_ROWS = 1000
DAILY_PRICE_LOOKBACK_DAYS = 500
DAILY_PRICE_MAX_REQUESTS = 15

TRADING_INTERVAL_SECONDS = 300.0
DEFAULT_BUY_QUANTITY = 1
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


def input_order_details() -> tuple[str, int]:
    """
    시장가 또는 지정가 주문 조건을 입력받는다.

    Returns
    -------
    tuple[str, int]
        주문 유형과 주문 가격
    """
    while True:
        order_choice = input(
            "주문 유형 선택 "
            "[1: 시장가, 2: 지정가]: "
        ).strip()

        if order_choice == "1":
            return "MARKET", 0

        if order_choice == "2":
            price_text = input(
                "지정가를 입력하세요: "
            ).strip()

            try:
                price = int(price_text)

            except ValueError:
                print("가격은 정수로 입력해야 합니다.")
                continue

            if price <= 0:
                print("지정가는 1원 이상이어야 합니다.")
                continue

            return "LIMIT", price

        print("1 또는 2를 입력하세요.")


def print_manual_order_result(
    result: dict[str, Any],
) -> None:
    """
    수동 주문 처리 결과를 출력한다.
    """
    print()
    print("수동 주문 결과")
    print("-" * 44)

    success = result.get("success") is True

    print(
        f"처리 결과: "
        f"{'성공' if success else '실패'}"
    )
    print(
        f"주문 상태: "
        f"{result.get('status', '-')}"
    )

    message = (
        result.get("message")
        or result.get("reason")
        or "메시지 없음"
    )
    print(f"메시지: {message}")

    if result.get("stock_code"):
        print(
            f"종목 코드: "
            f"{result['stock_code']}"
        )

    if result.get("side"):
        print(f"구분: {result['side']}")

    if result.get("quantity") is not None:
        print(
            f"주문 수량: "
            f"{result['quantity']}주"
        )

    if result.get("order_type"):
        print(
            f"주문 유형: "
            f"{result['order_type']}"
        )

    if result.get("price") is not None:
        price = result["price"]

        if result.get("order_type") == "MARKET":
            print("주문 가격: 시장가")
        else:
            print(f"주문 가격: {price:,}원")

    if result.get("order_no"):
        print(
            f"주문번호: "
            f"{result['order_no']}"
        )


def run_manual_buy(
    controller: TradingController,
) -> None:
    """
    콘솔 입력을 받아 수동 매수 주문을 실행한다.
    """
    print()
    print("[수동 매수]")
    print("-" * 44)

    stock_code = input(
        "매수할 종목 코드 6자리를 입력하세요: "
    ).strip()

    if (
        len(stock_code) != 6
        or not stock_code.isdigit()
    ):
        print("종목 코드는 숫자로 된 6자리여야 합니다.")
        return

    quantity_text = input(
        "매수 수량을 입력하세요: "
    ).strip()

    try:
        quantity = int(quantity_text)

    except ValueError:
        print("수량은 정수로 입력해야 합니다.")
        return

    if quantity <= 0:
        print("수량은 1주 이상이어야 합니다.")
        return

    order_type, price = input_order_details()

    price_text = (
        "시장가"
        if order_type == "MARKET"
        else f"{price:,}원"
    )

    print()
    print("[주문 확인]")
    print(f"종목 코드: {stock_code}")
    print("구분: 매수")
    print(f"수량: {quantity}주")
    print(f"가격: {price_text}")

    confirmation = input(
        "실제 모의투자 주문을 전송하시겠습니까? "
        "(y/n): "
    ).strip().lower()

    if confirmation not in {"y", "yes"}:
        print("수동 매수 주문을 취소했습니다.")
        return

    result = controller.manual_buy(
        stock_code=stock_code,
        quantity=quantity,
        order_type=order_type,
        price=price,
    )

    print_manual_order_result(result)


def run_manual_sell(
    controller: TradingController,
) -> None:
    """
    보유 종목을 표시하고 선택한 종목의
    수동 매도 주문을 실행한다.
    """
    print()
    print("[수동 매도]")
    print("-" * 44)

    position_result = controller.get_positions(
        refresh=True,
    )

    if not position_result.get("success"):
        print(
            position_result.get(
                "message",
                "보유 종목 조회에 실패했습니다.",
            )
        )
        return

    positions_dict = position_result.get(
        "positions",
        {},
    )
    positions = list(positions_dict.values())

    sellable_positions = [
        position
        for position in positions
        if position.available_quantity > 0
    ]

    if not sellable_positions:
        print("현재 매도 가능한 보유 종목이 없습니다.")
        return

    print("매도 가능한 보유 종목")

    for index, position in enumerate(
        sellable_positions,
        start=1,
    ):
        print(
            f"{index}. "
            f"{position.stock_name} "
            f"({position.stock_code}) / "
            f"보유 {position.quantity}주 / "
            f"매도 가능 "
            f"{position.available_quantity}주"
        )

    selection_text = input(
        "매도할 종목의 목록 번호 또는 종목 코드를 입력하세요: "
    ).strip()

    selected_position = None

    # 목록 번호로 선택
    if selection_text.isdigit():
        selection_number = int(selection_text)

        if 1 <= selection_number <= len(sellable_positions):
            selected_position = sellable_positions[
                selection_number - 1
            ]

    # 종목 코드로 선택
    if selected_position is None:
        for position in sellable_positions:
            if position.stock_code == selection_text:
                selected_position = position
                break

    if selected_position is None:
        print(
            "목록 번호 또는 보유 종목의 "
            "6자리 코드를 입력하세요."
        )
        return

    quantity_text = input(
        "매도 수량을 입력하세요 "
        f"(최대 {selected_position.available_quantity}주): "
    ).strip()

    try:
        quantity = int(quantity_text)

    except ValueError:
        print("수량은 정수로 입력해야 합니다.")
        return

    if quantity <= 0:
        print("수량은 1주 이상이어야 합니다.")
        return

    if quantity > selected_position.available_quantity:
        print("매도 가능 수량을 초과했습니다.")
        return

    order_type, price = input_order_details()

    price_text = (
        "시장가"
        if order_type == "MARKET"
        else f"{price:,}원"
    )

    print()
    print("[주문 확인]")
    print(
        f"종목: {selected_position.stock_name} "
        f"({selected_position.stock_code})"
    )
    print("구분: 매도")
    print(f"수량: {quantity}주")
    print(f"가격: {price_text}")

    confirmation = input(
        "실제 모의투자 주문을 전송하시겠습니까? "
        "(y/n): "
    ).strip().lower()

    if confirmation not in {"y", "yes"}:
        print("수동 매도 주문을 취소했습니다.")
        return

    result = controller.manual_sell(
        stock_code=selected_position.stock_code,
        quantity=quantity,
        order_type=order_type,
        price=price,
    )

    print_manual_order_result(result)


def run_manual_menu(
    controller: TradingController,
) -> None:
    """
    수동 주문 하위 메뉴를 실행한다.
    """
    while True:
        print()
        print("수동 주문 메뉴")
        print("-" * 44)
        print("1. 수동 매수")
        print("2. 수동 매도")
        print("3. 이전 메뉴")

        choice = input(
            "선택> "
        ).strip().lower()

        if choice in {"1", "buy"}:
            run_manual_buy(controller)
            return

        if choice in {"2", "sell"}:
            run_manual_sell(controller)
            return

        if choice in {
            "3",
            "back",
            "exit",
            "cancel",
        }:
            print("수동 주문 메뉴를 종료합니다.")
            return

        print("1, 2, 3 중 하나를 입력하세요.")


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
            print_last_results(controller)

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

