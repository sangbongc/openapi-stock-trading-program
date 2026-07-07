import os
import json
from datetime import datetime, timedelta

import requests
from config import APP_KEY, APP_SECRET, BASE_URL, TOKEN_PATH

#token 발급
def get_access_token() -> str:

    # ① 저장된 토큰이 있으면 재사용
    cached_token = load_token()

    if cached_token:
        print("저장된 토큰 사용")
        return cached_token

    # ② 없으면 새로 발급
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

    access_token = data["access_token"]

    # ③ 저장
    save_token(access_token)

    print("새 토큰 발급")

    return access_token
#토큰 저장
def save_token(token: str):
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)

    expires_at = datetime.now() + timedelta(hours=23)

    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "access_token": token,
            "expires_at": expires_at.isoformat()
        }, f, ensure_ascii=False, indent=4)
#토큰 읽기
def load_token():

    if not os.path.exists(TOKEN_PATH):
        return None

    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    expires_at = datetime.fromisoformat(data["expires_at"])

    if datetime.now() >= expires_at:
        return None

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

# 일봉 데이터 조회
def get_daily_price(token: str, stock_code: str, start_date: str, end_date: str) -> dict:
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"

    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHKST03010100",
    }

    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code,
        "FID_INPUT_DATE_1": start_date,
        "FID_INPUT_DATE_2": end_date,
        "FID_PERIOD_DIV_CODE": "D",
        "FID_ORG_ADJ_PRC": "1",
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()