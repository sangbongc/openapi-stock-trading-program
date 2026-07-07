from datetime import datetime, timedelta

from api import get_access_token, get_daily_price
from parser import parse_daily_price
from universe import STOCK_UNIVERSE
from database import create_tables, save_daily_prices, fetch_daily_prices_by_stock
from indicator import get_daily_price_df, add_rolling_mean, add_rsi, add_macd, add_bollinger_bands
def main():
    create_tables()
    token = get_access_token()

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

    for stock in STOCK_UNIVERSE:
        raw_daily = get_daily_price(
            token=token,
            stock_code=stock["code"],
            start_date=start_date,
            end_date=end_date,
        )

        daily_rows = parse_daily_price(
            raw_daily,
            stock_code=stock["code"],
            stock_name=stock["name"],
        )

        save_daily_prices(daily_rows)


if __name__ == "__main__":
    main()