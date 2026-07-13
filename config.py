from dotenv import load_dotenv
import os

load_dotenv()

APP_KEY = os.getenv("KIS_APP_KEY")
APP_SECRET = os.getenv("KIS_APP_SECRET")
BASE_URL = os.getenv("KIS_BASE_URL")
ACCOUNT_NO = os.getenv("KIS_ACCOUNT_NO")

TRADING_DRY_RUN = False
DEFAULT_BUY_QUANTITY = 1
STRATEGY_BUY_THRESHOLD = 0.2
STRATEGY_SELL_THRESHOLD = -0.2
IS_VIRTUAL=True
DB_PATH = "data/trading.db"
TOKEN_PATH = "data/token.json"
CHECK_INTERVAL = 60
REQUEST_INTERVAL = 1.0
ACCOUNT_PRODUCT_CODE = os.getenv(
    "ACCOUNT_PRODUCT_CODE"
)