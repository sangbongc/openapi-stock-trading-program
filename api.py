
import requests
from config import APP_KEY, APP_SECRET, BASE_URL

#token 발급
def get_access_token() -> str:
    url = f"{BASE_URL}/oauth2/tokenP"

    headers = {
        "content-type": "application/json"
    }

    body = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET
    }

    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()

    data = response.json()
    return data["access_token"]
#주가 확인
def get_current_price(token: str, stock_code: str) -> dict:
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"

    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHKST01010100",
    }

    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code,
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    return response.json()