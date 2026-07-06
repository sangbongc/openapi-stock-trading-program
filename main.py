from datetime import datetime

from api import get_access_token, get_current_price
from parser import parse_current_price
from universe import STOCK_UNIVERSE
from database import create_tables, save_current_price


def main():
    create_tables()

    token = get_access_token()

    for stock in STOCK_UNIVERSE:
        raw_data = get_current_price(token, stock["code"])
        price_data = parse_current_price(raw_data)

        price_data["name"] = stock["name"]
        price_data["collected_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        save_current_price(price_data)

        print(price_data)


if __name__ == "__main__":
    main()
from database import fetch_all_current_prices

rows = fetch_all_current_prices()

for row in rows:
    print(row)    