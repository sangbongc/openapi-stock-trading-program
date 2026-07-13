from pprint import pprint

from trading.execution_manager import ExecutionManager


TEST_ORDER_NO = "0000022467"


def main() -> None:
    print("=" * 70)
    print("한국투자증권 모의투자 체결 동기화 테스트")
    print("=" * 70)
    print(f"주문번호: {TEST_ORDER_NO}")

    manager = ExecutionManager()

    try:
        result = manager.sync_order(TEST_ORDER_NO)

    except Exception as error:
        print("\n[실패] 체결 동기화 중 오류가 발생했습니다.")
        print(f"오류 유형: {type(error).__name__}")
        print(f"오류 내용: {error}")
        return

    print("\n[체결 동기화 결과]")
    pprint(result)

    execution_status = result.get("execution_status")
    filled_quantity = result.get("filled_quantity", 0)
    remaining_quantity = result.get("remaining_quantity", 0)
    changed = result.get("changed", False)

    if execution_status == "FILLED":
        print("\n[성공] 주문이 전량 체결된 것으로 확인됐습니다.")
        print(f"누적 체결수량: {filled_quantity}주")
        print(f"미체결수량: {remaining_quantity}주")
        print(
            "평균 체결가격: "
            f"{result.get('average_fill_price', 0):,.0f}원"
        )
        print(f"신규 체결 DB 저장 여부: {changed}")
        print(f"체결 기록 ID: {result.get('execution_id')}")

    elif execution_status == "PARTIAL":
        print("\n[부분 체결] 일부 수량만 체결됐습니다.")

    elif execution_status == "PENDING":
        print("\n[미체결] 아직 체결되지 않은 주문입니다.")

    else:
        print(f"\n[확인 필요] 체결 상태: {execution_status}")


if __name__ == "__main__":
    main()