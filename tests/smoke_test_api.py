import logging
from datetime import datetime, timedelta
import time
from api import (
    KISAPIError,
    get_access_token,
    get_current_price,
    get_daily_price,
)


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s [%(levelname)s] "
        "%(name)s: %(message)s"
    ),
)


def main() -> None:
    stock_code = "005930"

    try:
        token = get_access_token()

        current_price = get_current_price(
            token=token,
            stock_code=stock_code,
        )
        output = current_price.get("output", {})

        print("\n[현재가 조회 성공]")
        print("종목 코드:", stock_code)
        print("현재가:", output.get("stck_prpr"))
        print("전일 대비:", output.get("prdy_vrss"))
        print("등락률:", output.get("prdy_ctrt"))

        end_date = datetime.now()
        start_date = end_date - timedelta(days=10)
        time.sleep(1)

        daily_price = get_daily_price(
            token=token,
            stock_code=stock_code,
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )

        rows = daily_price.get("output2", [])

        print("\n[일봉 조회 성공]")
        print("조회 건수:", len(rows))

        if rows:
            latest = rows[0]
            print("최근 거래일:", latest.get("stck_bsop_date"))
            print("종가:", latest.get("stck_clpr"))
            print("거래량:", latest.get("acml_vol"))

    except KISAPIError as error:
        print("\n[KIS API 오류]")
        print(error)
        raise SystemExit(1) from error

    except ValueError as error:
        print("\n[설정 또는 입력 오류]")
        print(error)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()