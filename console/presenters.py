from __future__ import annotations

from typing import Any
from trading.trading_controller import (
    TradingController,
)

def normalize_signal(signal: Any) -> str:
    """
    Signal Enum 또는 문자열을 출력용 문자열로 변환한다.
    """
    if signal is None:
        return "-"

    value = getattr(signal, "value", signal)

    return str(value)


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
    print("manual  수동 매수 및 매도")
    print("collect 과거 일봉 데이터 수집")
    print("balance 현재 계좌 잔고 및 보유 종목 조회")
    print("sync    미체결 주문 체결 동기화")
    print("status  현재 프로그램 상태 확인")
    print("results 최근 종목별 실행 결과 확인")
    print("help    명령어 도움말")
    print("exit    프로그램 종료")


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


def print_account(
    result: dict[str, Any],
) -> None:
    """
    TradingController의 계좌 조회 결과를 출력한다.
    """

    if not result.get("success"):
        print()
        print(result.get(
            "message",
            "계좌 조회에 실패했습니다.",
        ))
        return

    summary = result.get("account_summary", {})
    positions = result.get("positions", {})

    def first_value(
        *keys: str,
        default: int = 0,
    ) -> Any:
        """
        계좌 요약에서 사용 가능한 첫 번째 키의
        값을 반환한다.
        """
        for key in keys:
            value = summary.get(key)

            if value is not None and value != "":
                return value

        return default

    def to_int(value: Any) -> int:
        """
        문자열 또는 숫자 형태의 금액을
        출력용 정수로 변환한다.
        """
        try:
            return int(
                float(
                    str(value).replace(",", "")
                )
            )
        except (TypeError, ValueError):
            return 0

    cash = to_int(
        first_value(
            "cash",
            "deposit",
            "dnca_tot_amt",
        )
    )

    d1_cash = to_int(
        first_value(
            "d1_cash",
            "d1_deposit",
            "nxdy_excc_amt",
        )
    )

    d2_cash = to_int(
        first_value(
            "d2_cash",
            "d2_deposit",
            "prvs_rcdl_excc_amt",
        )
    )

    stock_evaluation_amount = to_int(
        first_value(
            "stock_evaluation_amount",
            "stock_evaluation",
            "scts_evlu_amt",
        )
    )

    total_evaluation_amount = to_int(
        first_value(
            "total_evaluation_amount",
            "total_evaluation",
            "tot_evlu_amt",
        )
    )

    total_profit_loss = to_int(
        first_value(
            "total_profit_loss",
            "evaluation_profit_loss",
            "evlu_pfls_smtl_amt",
        )
    )

    print()
    print("계좌 조회 결과")
    print("-" * 44)
    print(f"예수금: {cash:,}원")
    print(f"D+1 예수금: {d1_cash:,}원")
    print(f"D+2 예수금: {d2_cash:,}원")
    print(
        "주식 평가금액: "
        f"{stock_evaluation_amount:,}원"
    )
    print(
        "총 평가금액: "
        f"{total_evaluation_amount:,}원"
    )
    print(
        "총 평가손익: "
        f"{total_profit_loss:,}원"
    )
    print(f"보유 종목 수: {len(positions)}개")

    print()
    print("[보유 종목]")

    if not positions:
        print("현재 보유 종목이 없습니다.")
        return

    for position in positions.values():
        print("-" * 44)
        print(
            f"{position.stock_name} "
            f"({position.stock_code})"
        )
        print(f"보유 수량: {position.quantity:,}주")
        print(
            "매도 가능 수량: "
            f"{position.available_quantity:,}주"
        )
        print(
            "평균 매입가: "
            f"{float(position.average_price):,.2f}원"
        )
        print(
            "총 매입금액: "
            f"{position.purchase_amount:,}원"
        )
        print(
            f"현재가: "
            f"{position.current_price:,}원"
        )
        print(
            "평가금액: "
            f"{position.evaluation_amount:,}원"
        )
        print(
            "평가손익: "
            f"{position.profit_loss:,}원"
        )
        print(
            "평가손익률: "
            f"{float(position.profit_loss_rate):,.2f}%"
        )


