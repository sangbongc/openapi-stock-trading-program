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