from unittest.mock import Mock, patch

from api import get_account_balance
from config import ACCOUNT_NO, ACCOUNT_PRODUCT_CODE

@patch("api.get_access_token")
@patch("api.requests.get")
def test_get_account_balance(
    mock_get: Mock,
    mock_get_access_token: Mock,
):
    mock_get_access_token.return_value = "test-token"

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.headers = {
        "tr_cont": "",
    }

    mock_response.json.return_value = {
        "rt_cd": "0",
        "msg_cd": "KIOK0560",
        "msg1": "정상처리 되었습니다.",
        "output1": [
            {
                "pdno": "005930",
                "prdt_name": "삼성전자",
                "hldg_qty": "10",
                "ord_psbl_qty": "8",
                "pchs_avg_pric": "68000.0000",
                "pchs_amt": "680000",
                "prpr": "71000",
                "evlu_amt": "710000",
                "evlu_pfls_amt": "30000",
                "evlu_pfls_rt": "4.4117",
                "thdt_buyqty": "2",
                "thdt_sll_qty": "0",
            },
            {
                "pdno": "000660",
                "prdt_name": "SK하이닉스",
                "hldg_qty": "0",
                "ord_psbl_qty": "0",
                "pchs_avg_pric": "0",
                "pchs_amt": "0",
                "prpr": "200000",
                "evlu_amt": "0",
                "evlu_pfls_amt": "0",
                "evlu_pfls_rt": "0",
                "thdt_buyqty": "0",
                "thdt_sll_qty": "0",
            },
        ],
        "output2": [
            {
                "dnca_tot_amt": "5000000",
                "nxdy_excc_amt": "4900000",
                "prvs_rcdl_excc_amt": "4800000",
                "scts_evlu_amt": "710000",
                "tot_evlu_amt": "5710000",
                "evlu_pfls_smtl_amt": "30000",
                "bfdy_buy_amt": "0",
                "thdt_buy_amt": "136000",
                "bfdy_sll_amt": "0",
                "thdt_sll_amt": "0",
            }
        ],
        "ctx_area_fk100": "",
        "ctx_area_nk100": "",
    }

    mock_get.return_value = mock_response

    result = get_account_balance()

    assert result["cash"] == 5_000_000
    assert result["d1_cash"] == 4_900_000
    assert result["d2_cash"] == 4_800_000

    assert result["stock_evaluation_amount"] == 710_000
    assert result["total_evaluation_amount"] == 5_710_000
    assert result["total_profit_loss"] == 30_000

    # 보유수량 0인 SK하이닉스는 기본적으로 제외된다.
    assert result["position_count"] == 1
    assert len(result["positions"]) == 1

    position = result["positions"][0]

    assert position["stock_code"] == "005930"
    assert position["stock_name"] == "삼성전자"
    assert position["quantity"] == 10
    assert position["sellable_quantity"] == 8
    assert position["avg_price"] == 68000.0
    assert position["current_price"] == 71000
    assert position["profit_loss"] == 30000

    mock_get.assert_called_once()

    _, call_kwargs = mock_get.call_args

    assert call_kwargs["headers"]["tr_id"] == "VTTC8434R"
    assert call_kwargs["params"]["CANO"] == ACCOUNT_NO
    assert (
        call_kwargs["params"]["ACNT_PRDT_CD"]
        == ACCOUNT_PRODUCT_CODE
    )
    assert call_kwargs["params"]["INQR_DVSN"] == "02"
    assert call_kwargs["params"]["PRCS_DVSN"] == "00"

    print("계좌 잔고 조회 API 구조 테스트 통과")
from api import get_account_balance

result = get_account_balance()

print("예수금:", result.get("cash"))
print("총 평가금액:", result.get("total_evaluation_amount"))
print("보유 종목 수:", result.get("position_count"))
print("보유 종목:", result.get("positions"))

if __name__ == "__main__":
    test_get_account_balance()