from console.bootstrap import (
    build_controller,
    TRADING_INTERVAL_SECONDS,
)
from console.command_loop import (
    command_loop,
)
from console.presenters import (
    print_banner,
)
from trading.trading_controller import (
    TradingController,
)
from universe import STOCK_UNIVERSE


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

