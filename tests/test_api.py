import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

import api
import logging

@pytest.fixture
def isolated_token_path(tmp_path, monkeypatch):
    token_path = tmp_path / "token.json"
    monkeypatch.setattr(api, "TOKEN_PATH", str(token_path))
    return token_path


def test_build_url_handles_slashes(monkeypatch):
    monkeypatch.setattr(api, "BASE_URL", "https://example.com/")

    assert (
        api._build_url("/uapi/test")
        == "https://example.com/uapi/test"
    )


def test_validate_stock_code_accepts_six_digits():
    api._validate_stock_code("005930")


@pytest.mark.parametrize(
    "stock_code, expected_exception",
    [
        (5930, TypeError),
        ("5930", ValueError),
        ("ABC930", ValueError),
    ],
)
def test_validate_stock_code_rejects_invalid_value(
    stock_code,
    expected_exception,
):
    with pytest.raises(expected_exception):
        api._validate_stock_code(stock_code)


def test_validate_date_range_accepts_valid_dates():
    api._validate_date_range("20260701", "20260711")


def test_validate_date_range_rejects_reversed_dates():
    with pytest.raises(ValueError):
        api._validate_date_range("20260711", "20260701")


def test_validate_business_response_accepts_success():
    api.validate_business_response(
        {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
        }
    )


def test_validate_business_response_raises_on_failure():
    with pytest.raises(api.KISAPIError, match="TEST_ERROR"):
        api.validate_business_response(
            {
                "rt_cd": "1",
                "msg_cd": "TEST_ERROR",
                "msg1": "테스트 오류",
            }
        )


def test_save_and_load_token(
    isolated_token_path,
):
    expires_at = datetime.now() + timedelta(hours=1)

    api.save_token(
        access_token="test-token",
        token_type="Bearer",
        expires_at=expires_at,
    )

    assert isolated_token_path.exists()
    assert api.load_token() == "test-token"


def test_expired_token_is_deleted(
    isolated_token_path,
):
    isolated_token_path.write_text(
        json.dumps(
            {
                "access_token": "expired-token",
                "token_type": "Bearer",
                "expires_at": (
                    datetime.now() - timedelta(minutes=1)
                ).isoformat(),
            }
        ),
        encoding="utf-8",
    )

    assert api.load_token() is None
    assert not isolated_token_path.exists()


def test_get_current_price_builds_correct_request(
    monkeypatch,
):
    captured = {}

    def fake_request_json(**kwargs):
        captured.update(kwargs)
        return {
            "rt_cd": "0",
            "output": {
                "stck_prpr": "70000",
            },
        }

    monkeypatch.setattr(
        api,
        "request_json",
        fake_request_json,
    )

    result = api.get_current_price(
        token="test-token",
        stock_code="005930",
    )

    assert result["output"]["stck_prpr"] == "70000"
    assert captured["method"] == "GET"
    assert captured["tr_id"] == "FHKST01010100"
    assert (
        captured["params"]["FID_INPUT_ISCD"]
        == "005930"
    )


def test_request_json_retries_once_on_401(
    monkeypatch,
):
    monkeypatch.setattr(api, "APP_KEY", "test-key")
    monkeypatch.setattr(api, "APP_SECRET", "test-secret")
    monkeypatch.setattr(
        api,
        "BASE_URL",
        "https://example.com",
    )
    monkeypatch.setattr(api, "TOKEN_PATH", "token.json")

    unauthorized_response = Mock()
    unauthorized_response.status_code = 401
    unauthorized_response.raise_for_status.side_effect = (
        requests.HTTPError(response=unauthorized_response)
    )

    success_response = Mock()
    success_response.status_code = 200
    success_response.raise_for_status.return_value = None
    success_response.json.return_value = {
        "rt_cd": "0",
        "output": {},
    }

    session = Mock()
    session.request.side_effect = [
        unauthorized_response,
        success_response,
    ]

    monkeypatch.setattr(
        api,
        "delete_cached_token",
        Mock(),
    )
    monkeypatch.setattr(
        api,
        "get_access_token",
        Mock(return_value="new-token"),
    )

    result = api.request_json(
        method="GET",
        endpoint="/test",
        token="old-token",
        tr_id="TEST_TR",
        session=session,
    )

    assert result["rt_cd"] == "0"
    assert session.request.call_count == 2
    api.get_access_token.assert_called_once_with(
        force_refresh=True
    )