#잔고확인
from pprint import pprint

from api import get_account_balance


def main() -> None:
    print("=" * 70)
    print("한국투자증권 모의투자 계좌 잔고 API 테스트")
    print("=" * 70)

    try:
        balance = get_account_balance(
            include_zero_quantity=False,
            max_pages=10,
        )

    except Exception as error:
        print("\n[실패] 계좌 잔고 조회 중 오류가 발생했습니다.")
        print(f"오류 유형: {type(error).__name__}")
        print(f"오류 내용: {error}")
        return

    print("\n[성공] 계좌 잔고 조회 API가 정상 응답했습니다.")

    print("\n[계좌 요약]")
    print(f"예수금: {balance.get('cash', 0):,}원")
    print(f"D+1 예수금: {balance.get('d1_cash', 0):,}원")
    print(f"D+2 예수금: {balance.get('d2_cash', 0):,}원")
    print(
        "주식 평가금액: "
        f"{balance.get('stock_evaluation_amount', 0):,}원"
    )
    print(
        "총 평가금액: "
        f"{balance.get('total_evaluation_amount', 0):,}원"
    )
    print(
        "총 평가손익: "
        f"{balance.get('total_profit_loss', 0):,}원"
    )
    print(f"보유 종목 수: {balance.get('position_count', 0)}개")

    positions = balance.get("positions", [])

    print("\n[보유 종목]")

    if not positions:
        print("현재 보유 종목이 없습니다.")
        return

    for position in positions:
        print("-" * 70)
        pprint(position)


if __name__ == "__main__":
    main()

#매수/매도 검증
# from pprint import pprint

# from trading.order_manager import OrderManager


# TEST_STOCK_CODE = "035720"  # 카카오
# TEST_QUANTITY = 1


# def main() -> None:
#     print("=" * 70)
#     print("한국투자증권 모의투자 매도 주문 API 테스트")
#     print("=" * 70)
#     print(f"종목코드: {TEST_STOCK_CODE}")
#     print(f"주문수량: {TEST_QUANTITY}주")
#     print("주문유형: 시장가 매도")
#     print("=" * 70)

#     confirmation = input(
#         "모의투자 계좌에 실제 매도 주문을 전송합니다. "
#         "계속하려면 SELL을 입력하세요: "
#     )

#     if confirmation.strip().upper() != "SELL":
#         print("주문 전송을 취소했습니다.")
#         return

#     manager = OrderManager()

#     try:
#         result = manager.sell(
#             stock_code=TEST_STOCK_CODE,
#             quantity=TEST_QUANTITY,
#             order_type="MARKET",
#         )

#     except Exception as error:
#         print("\n[예외 발생]")
#         print(f"오류 유형: {type(error).__name__}")
#         print(f"오류 내용: {error}")
#         return

#     print("\n[주문 처리 결과]")
#     pprint(result)

#     is_accepted = (
#         result.get("success") is True
#         and result.get("status") == "ACCEPTED"
#         and bool(result.get("order_no"))
#     )

#     if is_accepted:
#         print("\n[성공] 모의투자 서버가 매도 주문을 접수했습니다.")
#         print(f"로컬 주문 ID: {result.get('order_id')}")
#         print(f"증권사 주문번호: {result.get('order_no')}")
#         print(f"종목코드: {result.get('stock_code')}")
#         print(f"매도수량: {result.get('quantity')}주")
#         print(f"주문 상태: {result.get('status')}")

#     else:
#         print("\n[실패] 매도 주문이 접수되지 않았습니다.")
#         print(f"상태: {result.get('status')}")
#         print(f"메시지 코드: {result.get('message_code')}")
#         print(f"메시지: {result.get('message')}")


# if __name__ == "__main__":
#     main()

