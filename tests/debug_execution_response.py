from pprint import pprint

from api import inquire_daily_orders


ORDER_NO = "0000019532"
STOCK_CODE = "035720"
SIDE = "BUY"


def main() -> None:
    print("=" * 70)
    print("일별 주문체결 API 원본 응답 확인")
    print("=" * 70)

    try:
        response = inquire_daily_orders(
            order_no="",
            stock_code="",
            side="ALL",
            executed_only=False,
        )

    except Exception as error:
        print("[조회 실패]")
        print(f"오류 유형: {type(error).__name__}")
        print(f"오류 내용: {error}")
        return

    print("\n[전체 응답]")
    pprint(response)

    rows = response.get("output1") or []

    print(f"\noutput1 행 개수: {len(rows)}")

    for index, row in enumerate(rows, start=1):
        print(f"\n[{index}번째 행]")
        pprint(row)


if __name__ == "__main__":
    main()