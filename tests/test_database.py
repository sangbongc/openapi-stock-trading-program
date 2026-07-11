# tests/test_database.py

from database import (
    clear_current_prices,
    clear_daily_prices,
    create_tables,
    fetch_all_current_prices,
    fetch_all_daily_prices,
    fetch_daily_prices_by_stock,
    fetch_latest_current_price,
    fetch_latest_daily_date,
    fetch_saved_stock_codes,
    save_current_price,
    save_daily_prices,
)


def test_database():
    print("\n1. 테이블 생성 테스트")
    create_tables()
    print("테이블 생성 완료")

    print("\n2. 기존 테스트 데이터 삭제")
    deleted_current = clear_current_prices()
    deleted_daily = clear_daily_prices()

    print(f"현재가 삭제: {deleted_current}건")
    print(f"일봉 삭제: {deleted_daily}건")

    print("\n3. 현재가 저장 테스트")

    current_price = {
        "collected_at": "2026-07-11 13:30:00",
        "stock_code": "005930",
        "name": "삼성전자",
        "price": 75000,
        "change": 1000,
        "change_rate": 1.35,
        "open": 74200,
        "high": 75500,
        "low": 74000,
        "volume": 12000000,
        "per": 15.2,
        "pbr": 1.3,
    }

    inserted_id = save_current_price(current_price)
    print(f"현재가 저장 완료, ID: {inserted_id}")

    print("\n4. 전체 현재가 조회 테스트")

    current_rows = fetch_all_current_prices()

    for row in current_rows:
        print(row)

    assert len(current_rows) == 1
    assert current_rows[0]["stock_code"] == "005930"
    assert current_rows[0]["price"] == 75000

    print("전체 현재가 조회 테스트 통과")

    print("\n5. 최근 현재가 조회 테스트")

    latest_current = fetch_latest_current_price("005930")

    print(latest_current)

    assert latest_current is not None
    assert latest_current["name"] == "삼성전자"
    assert latest_current["price"] == 75000

    print("최근 현재가 조회 테스트 통과")

    print("\n6. 일봉 데이터 저장 테스트")

    daily_rows = [
        {
            "stock_code": "005930",
            "date": "20260709",
            "open": 73000,
            "high": 74000,
            "low": 72500,
            "close": 73800,
            "volume": 10000000,
        },
        {
            "stock_code": "005930",
            "date": "20260710",
            "open": 73800,
            "high": 74800,
            "low": 73500,
            "close": 74500,
            "volume": 11000000,
        },
        {
            "stock_code": "005930",
            "date": "20260711",
            "open": 74200,
            "high": 75500,
            "low": 74000,
            "close": 75000,
            "volume": 12000000,
        },
        {
            "stock_code": "000660",
            "date": "20260711",
            "open": 210000,
            "high": 215000,
            "low": 208000,
            "close": 213000,
            "volume": 5000000,
        },
    ]

    saved_count = save_daily_prices(daily_rows)

    print(f"일봉 저장 요청: {saved_count}건")
    assert saved_count == 4

    print("\n7. 특정 종목 일봉 조회 테스트")

    samsung_rows = fetch_daily_prices_by_stock("005930", limit=2)

    for row in samsung_rows:
        print(row)

    assert len(samsung_rows) == 2
    assert samsung_rows[0]["date"] == "20260711"
    assert samsung_rows[1]["date"] == "20260710"

    print("종목별 일봉 조회 테스트 통과")

    print("\n8. 전체 일봉 조회 테스트")

    all_daily_rows = fetch_all_daily_prices()

    for row in all_daily_rows:
        print(row)

    assert len(all_daily_rows) == 4

    print("전체 일봉 조회 테스트 통과")

    print("\n9. 최근 저장 날짜 조회 테스트")

    latest_date = fetch_latest_daily_date("005930")

    print(f"삼성전자 최근 저장 날짜: {latest_date}")

    assert latest_date == "20260711"

    print("최근 저장 날짜 조회 테스트 통과")

    print("\n10. 저장 종목 목록 조회 테스트")

    stock_codes = fetch_saved_stock_codes()

    print(stock_codes)

    assert "005930" in stock_codes
    assert "000660" in stock_codes

    print("저장 종목 목록 테스트 통과")

    print("\n11. 중복 일봉 저장 테스트")

    duplicate_row = [
        {
            "stock_code": "005930",
            "date": "20260711",
            "open": 74200,
            "high": 76000,
            "low": 74000,
            "close": 75800,
            "volume": 13000000,
        }
    ]

    save_daily_prices(duplicate_row)

    updated_rows = fetch_daily_prices_by_stock("005930", limit=1)

    print(updated_rows[0])

    assert updated_rows[0]["date"] == "20260711"
    assert updated_rows[0]["close"] == 75800
    assert updated_rows[0]["volume"] == 13000000

    all_daily_rows = fetch_all_daily_prices()

    assert len(all_daily_rows) == 4

    print("중복 데이터 교체 테스트 통과")

    print("\n12. 존재하지 않는 종목 조회 테스트")

    missing_current = fetch_latest_current_price("999999")
    missing_date = fetch_latest_daily_date("999999")
    missing_daily = fetch_daily_prices_by_stock("999999")

    assert missing_current is None
    assert missing_date is None
    assert missing_daily == []

    print("존재하지 않는 종목 조회 테스트 통과")

    print("\n모든 database.py 테스트 통과")


if __name__ == "__main__":
    test_database()