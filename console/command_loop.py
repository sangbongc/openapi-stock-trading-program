

from console.presenters import (
    print_account, 
    print_collect_results,
    print_help,
    print_run_result,
    print_status,
    print_trading_results,
)
from console.manual_order import (
    run_manual_menu,
)
from data_collector import collect_daily_prices
from trading.trading_controller import (
    TradingController,
)
from universe import STOCK_UNIVERSE


DAILY_PRICE_TARGET_ROWS = 1000
DAILY_PRICE_LOOKBACK_DAYS = 500
DAILY_PRICE_MAX_REQUESTS = 15


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
