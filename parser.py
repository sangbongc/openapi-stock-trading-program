#현재가 파싱
def parse_current_price(data: dict) -> dict:
    if data["rt_cd"] != "0":
        raise Exception(data["msg1"])

    output = data["output"]

    return {
        "stock_code": output["stck_shrn_iscd"],
        "price": int(output["stck_prpr"]),
        "change": int(output["prdy_vrss"]),
        "change_rate": float(output["prdy_ctrt"]),
        "open": int(output["stck_oprc"]),
        "high": int(output["stck_hgpr"]),
        "low": int(output["stck_lwpr"]),
        "volume": int(output["acml_vol"]),
        "per": float(output["per"]),
        "pbr": float(output["pbr"]),
    }
#일봉데이터 파싱
def parse_daily_price(data: dict, stock_code: str, stock_name: str = "") -> list[dict]:
    if data["rt_cd"] != "0":
        raise Exception(data["msg1"])

    rows = []

    for item in data["output2"]:
        rows.append({
            "stock_code": stock_code,
            "name": stock_name,
            "date": item["stck_bsop_date"],
            "open": int(item["stck_oprc"]),
            "high": int(item["stck_hgpr"]),
            "low": int(item["stck_lwpr"]),
            "close": int(item["stck_clpr"]),
            "volume": int(item["acml_vol"])
        })

    return rows