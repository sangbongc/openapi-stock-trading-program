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

DAILY_PRICE_TARGET_ROWS = 250
DAILY_PRICE_LOOKBACK_DAYS = 400
DAILY_PRICE_MAX_REQUESTS = 5

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
        stock_universe=STOCK_UNIVERSE,
        interval_seconds=TRADING_INTERVAL_SECONDS,
    )


def print_banner() -> None:
    """
    프로그램 시작 화면을 출력한다.
    """
    print()
    print("=" * 44)
    print(" KIS Rule-Based Auto Trading Program")
    print("=" * 44)
    print("자동매매는 start 명령을 입력해야 시작됩니다.")
    print()


def print_help() -> None:
    print()
    print("사용 가능한 명령어")
    print("-" * 44)
    print("start   반복 자동매매 시작")
    print("stop    반복 자동매매 중지")
    print("run     전체 종목을 한 번만 실행")
    print("collect 과거 일봉 데이터 수집")
    print("status  현재 프로그램 상태 확인")
    print("results 최근 종목별 실행 결과 확인")
    print("help    명령어 도움말")
    print("exit    프로그램 종료")


def normalize_signal(signal: Any) -> str:
    """
    Signal Enum 또는 문자열을 출력용 문자열로 변환한다.
    """
    if signal is None:
        return "-"

    value = getattr(signal, "value", signal)

    return str(value)


def print_trading_results(
    trading_results: list[dict[str, Any]],
) -> None:
    """
    TradingEngine의 종목별 실행 결과를 출력한다.
    """
    if not trading_results:
        print("종목별 매매 결과가 없습니다.")
        return

    print()
    print("종목별 실행 결과")
    print("-" * 44)

    for result in trading_results:
        stock_code = result.get(
            "stock_code",
            "UNKNOWN",
        )
        stock_name = result.get("stock_name")

        display_name = (
            f"{stock_name} ({stock_code})"
            if stock_name
            else stock_code
        )

        signal = normalize_signal(
            result.get("signal")
        )
        action = result.get("action", "-")
        ordered = (
            "예"
            if result.get("ordered") is True
            else "아니오"
        )
        reason = result.get(
            "reason",
            "처리 사유 없음",
        )

        print(f"신호: {signal}")
        print(f"처리: {action}")
        print(f"주문 생성: {ordered}")
        print(f"사유: {reason}")

        strategy_result = result.get("strategy_result")

        if strategy_result is not None:
            print("[전략 엔진 상세 결과]")

            final_signal = getattr(
                strategy_result,
                "final_signal",
                None,
            )
            final_score = getattr(
                strategy_result,
                "final_score",
                None,
            )

            if final_signal is not None:
                print(
                    "최종 전략 신호: "
                    f"{normalize_signal(final_signal)}"
                )

            if final_score is not None:
                print(
                    f"최종 점수: {final_score:.4f}"
                )

            individual_results = getattr(
                strategy_result,
                "results",
                None,
            )

            if individual_results is None:
                individual_results = getattr(
                    strategy_result,
                    "strategy_results",
                    None,
                )

            if individual_results is not None:
                
                    if isinstance(individual_results, dict):
                        result_items = individual_results.items()
                    else:
                        result_items = enumerate(individual_results)

                    for strategy_name, individual_result in result_items:
                        if isinstance(individual_result, dict):
                            individual_signal = individual_result.get(
                                "signal"
                            )
                            confidence = individual_result.get(
                                "confidence"
                            )
                            individual_reason = individual_result.get(
                                "reason",
                                "사유 없음",
                            )
                        else:
                            individual_signal = getattr(
                                individual_result,
                                "signal",
                                None,
                            )
                            confidence = getattr(
                                individual_result,
                                "confidence",
                                None,
                            )
                            individual_reason = getattr(
                                individual_result,
                                "reason",
                                "사유 없음",
                            )

                        print(f"- 전략: {strategy_name}")
                        print(
                            "  신호: "
                            f"{normalize_signal(individual_signal)}"
                        )

                        if confidence is not None:
                            print(
                                f"  신뢰도: {confidence:.4f}"
                            )

                        print(
                            f"  사유: {individual_reason}"
                        )
        print()

def print_collect_results(
    results: list[dict[str, Any]],
) -> None:
    """
    종목별 일봉 데이터 수집 결과를 출력한다.
    """
    print()
    print("일봉 데이터 수집 결과")
    print("-" * 44)

    success_count = 0

    for result in results:
        stock_code = result.get(
            "stock_code",
            "UNKNOWN",
        )
        stock_name = result.get(
            "stock_name",
            "",
        )

        display_name = (
            f"{stock_name} ({stock_code})"
            if stock_name
            else stock_code
        )

        success = result.get("success") is True

        if success:
            success_count += 1

        status = "완료" if success else "미완료"

        print(f"[{display_name}]")
        print(f"상태: {status}")
        print(
            "이번 조회 데이터: "
            f"{result.get('fetched_count', 0)}개"
        )
        print(
            "DB 저장 시도: "
            f"{result.get('saved_count', 0)}개"
        )
        print(
            "현재 DB 보유: "
            f"{result.get('total_count', 0)}개"
        )
        print(
            "API 요청 횟수: "
            f"{result.get('request_count', 0)}회"
        )
        print(
            f"메시지: "
            f"{result.get('message', '-')}"
        )

        error = result.get("error")

        if error:
            print(f"오류: {error}")

        print()

    print(
        f"수집 완료 종목: "
        f"{success_count}/{len(results)}"
    )
def print_execution_results(
    execution_results: list[dict[str, Any]],
) -> None:
    """
    ExecutionManager의 체결 동기화 결과 요약을 출력한다.
    """
    if not execution_results:
        print("동기화할 기존 미완료 주문이 없습니다.")
        return

    changed_count = sum(
        1
        for result in execution_results
        if result.get("changed") is True
    )

    error_count = sum(
        1
        for result in execution_results
        if (
            result.get("execution_status")
            == "ERROR"
            or result.get("status") == "ERROR"
            or result.get("error")
        )
    )

    print(
        "체결 동기화: "
        f"총 {len(execution_results)}건, "
        f"변경 {changed_count}건, "
        f"오류 {error_count}건"
    )


def print_run_result(
    result: dict[str, Any],
) -> None:
    """
    run_once() 호출 결과를 출력한다.
    """
    print()
    print(result.get("message", "실행 결과 없음"))

    if not result.get("success"):
        error = (
            result.get("error")
            or result.get("last_error")
        )

        if error:
            print(f"오류: {error}")

        return

    execution_results = result.get(
        "execution_results",
        [],
    )
    trading_results = result.get(
        "trading_results",
        [],
    )

    print_execution_results(execution_results)
    print_trading_results(trading_results)


def print_status(
    state: dict[str, Any],
) -> None:
    """
    TradingController의 현재 상태를 출력한다.
    """
    worker_text = (
        "실행 중"
        if state.get("worker_alive")
        else "중지"
    )

    last_error = state.get("last_error") or "없음"

    print()
    print("프로그램 상태")
    print("-" * 44)
    print(f"자동매매 상태: {state['status']}")
    print(f"작업 스레드: {worker_text}")
    print(f"대상 종목 수: {state['stock_count']}")
    print(
        "반복 주기: "
        f"{state['interval_seconds']:.0f}초"
    )
    print(f"최근 오류: {last_error}")


def print_last_results(
    controller: TradingController,
) -> None:
    """
    가장 최근 TradingEngine 실행 결과를 출력한다.
    """
    state = controller.get_state()
    results = state.get("last_results", [])

    print_trading_results(results)


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
        elif command == "collect":
            run_collection(controller)

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

