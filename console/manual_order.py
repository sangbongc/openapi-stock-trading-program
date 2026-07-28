

from console.presenters import (
    print_manual_order_result,
)
from trading.trading_controller import (
    TradingController,
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
