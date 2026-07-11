from datetime import datetime, timedelta

from api import (
    KISAPIError,
    get_access_token,
    get_current_price,
    get_daily_price,
)


def test_access_token() -> str:
    print("\n[1] 접근토큰 테스트 시작")

    token = get_access_token()

    if not token:
        raise RuntimeError("접근토큰이 비어 있습니다.")

    print("접근토큰 발급 또는 로드 성공")
    print(f"토큰 앞부분: {token[:10]}...")

    return token


def test_current_price(token: str) -> None:
    print("\n[2] 현재가 조회 테스트 시작")

    stock_code = "005930"

    response = get_current_price(
        token=token,
        stock_code=stock_code,
    )

    output = response.get("output")

    if not output:
        raise RuntimeError(
            "현재가 응답에 output이 없습니다."
        )

    print("현재가 조회 성공")
    print(f"종목코드: {stock_code}")
    print(f"현재가: {output.get('stck_prpr')}")
    print(f"전일 대비: {output.get('prdy_vrss')}")
    print(f"등락률: {output.get('prdy_ctrt')}")
    print(f"시가: {output.get('stck_oprc')}")
    print(f"고가: {output.get('stck_hgpr')}")
    print(f"저가: {output.get('stck_lwpr')}")
    print(f"누적 거래량: {output.get('acml_vol')}")


def test_daily_price(token: str) -> None:
    print("\n[3] 일봉 조회 테스트 시작")

    stock_code = "005930"

    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    response = get_daily_price(
        token=token,
        stock_code=stock_code,
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
    )

    daily_rows = response.get("output2", [])

    if not daily_rows:
        raise RuntimeError(
            "일봉 응답에 output2 데이터가 없습니다."
        )

    print("일봉 조회 성공")
    print(f"반환된 일봉 개수: {len(daily_rows)}")

    print("\n최근 일봉 5개")

    for row in daily_rows[:5]:
        print(
            {
                "date": row.get("stck_bsop_date"),
                "open": row.get("stck_oprc"),
                "high": row.get("stck_hgpr"),
                "low": row.get("stck_lwpr"),
                "close": row.get("stck_clpr"),
                "volume": row.get("acml_vol"),
            }
        )


def main() -> None:
    try:
        token = test_access_token()
        test_current_price(token)
        test_daily_price(token)

        print("\n모든 API 테스트가 정상적으로 완료되었습니다.")

    except KISAPIError as error:
        print("\n한국투자증권 API 오류")
        print(error)

    except ValueError as error:
        print("\n입력값 또는 환경설정 오류")
        print(error)

    except Exception as error:
        print("\n예상하지 못한 오류")
        print(type(error).__name__, error)


if __name__ == "__main__":
    main()