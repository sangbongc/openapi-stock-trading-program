import unittest
from decimal import Decimal
from unittest.mock import Mock

from trading.position_manager import (
    BalanceResponseError,
    PositionManager,
)


class TestPositionManager(unittest.TestCase):

    def setUp(self):
        self.balance_response = {
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output1": [
                {
                    "pdno": "005930",
                    "prdt_name": "삼성전자",
                    "hldg_qty": "10",
                    "ord_psbl_qty": "8",
                    "pchs_avg_pric": "70000.0000",
                    "pchs_amt": "700000",
                    "prpr": "73000",
                    "evlu_amt": "730000",
                    "evlu_pfls_amt": "30000",
                    "evlu_pfls_rt": "4.28571429",
                },
                {
                    "pdno": "000660",
                    "prdt_name": "SK하이닉스",
                    "hldg_qty": "5",
                    "ord_psbl_qty": "5",
                    "pchs_avg_pric": "180000.0000",
                    "pchs_amt": "900000",
                    "prpr": "175000",
                    "evlu_amt": "875000",
                    "evlu_pfls_amt": "-25000",
                    "evlu_pfls_rt": "-2.77777778",
                },
            ],
            "output2": [
                {
                    "dnca_tot_amt": "1000000",
                    "tot_evlu_amt": "2605000",
                    "nass_amt": "2605000",
                }
            ],
        }

        self.balance_fetcher = Mock(
            return_value=self.balance_response
        )

        self.manager = PositionManager(self.balance_fetcher)

    def test_refresh_calls_balance_fetcher(self):
        self.manager.refresh()

        self.balance_fetcher.assert_called_once_with()

    def test_refresh_creates_positions(self):
        positions = self.manager.refresh()

        self.assertEqual(len(positions), 2)
        self.assertIn("005930", positions)
        self.assertIn("000660", positions)

    def test_get_position(self):
        self.manager.refresh()

        position = self.manager.get_position("005930")

        self.assertIsNotNone(position)
        self.assertEqual(position.stock_code, "005930")
        self.assertEqual(position.stock_name, "삼성전자")
        self.assertEqual(position.quantity, 10)
        self.assertEqual(position.available_quantity, 8)
        self.assertEqual(
            position.average_price,
            Decimal("70000.0000"),
        )
        self.assertEqual(position.current_price, 73000)

    def test_has_position(self):
        self.manager.refresh()

        self.assertTrue(self.manager.has_position("005930"))
        self.assertFalse(self.manager.has_position("035420"))

    def test_get_quantity(self):
        self.manager.refresh()

        self.assertEqual(
            self.manager.get_quantity("005930"),
            10,
        )
        self.assertEqual(
            self.manager.get_quantity("035420"),
            0,
        )

    def test_get_available_quantity(self):
        self.manager.refresh()

        self.assertEqual(
            self.manager.get_available_quantity("005930"),
            8,
        )

    def test_can_sell(self):
        self.manager.refresh()

        self.assertTrue(
            self.manager.can_sell("005930", 8)
        )
        self.assertFalse(
            self.manager.can_sell("005930", 9)
        )

    def test_validate_sell_quantity_success(self):
        self.manager.refresh()

        self.manager.validate_sell_quantity("005930", 8)

    def test_validate_sell_quantity_failure(self):
        self.manager.refresh()

        with self.assertRaises(ValueError):
            self.manager.validate_sell_quantity(
                "005930",
                9,
            )

    def test_total_purchase_amount(self):
        self.manager.refresh()

        self.assertEqual(
            self.manager.get_total_purchase_amount(),
            1_600_000,
        )

    def test_total_evaluation_amount(self):
        self.manager.refresh()

        self.assertEqual(
            self.manager.get_total_evaluation_amount(),
            1_605_000,
        )

    def test_total_profit_loss(self):
        self.manager.refresh()

        self.assertEqual(
            self.manager.get_total_profit_loss(),
            5_000,
        )

    def test_profitable_position(self):
        self.manager.refresh()

        samsung = self.manager.get_position("005930")
        hynix = self.manager.get_position("000660")

        self.assertTrue(samsung.is_profitable)
        self.assertFalse(samsung.is_loss)

        self.assertFalse(hynix.is_profitable)
        self.assertTrue(hynix.is_loss)

    def test_account_summary(self):
        self.manager.refresh()

        summary = self.manager.get_account_summary()

        self.assertEqual(
            summary["dnca_tot_amt"],
            "1000000",
        )
        self.assertEqual(
            summary["tot_evlu_amt"],
            "2605000",
        )

    def test_zero_quantity_position_is_excluded(self):
        self.balance_response["output1"].append(
            {
                "pdno": "035420",
                "prdt_name": "NAVER",
                "hldg_qty": "0",
                "ord_psbl_qty": "0",
            }
        )

        positions = self.manager.refresh()

        self.assertNotIn("035420", positions)

    def test_refresh_removes_sold_position(self):
        self.manager.refresh()

        self.assertTrue(
            self.manager.has_position("005930")
        )

        self.balance_fetcher.return_value = {
            "rt_cd": "0",
            "output1": [
                {
                    "pdno": "000660",
                    "prdt_name": "SK하이닉스",
                    "hldg_qty": "5",
                    "ord_psbl_qty": "5",
                }
            ],
            "output2": [],
        }

        self.manager.refresh()

        self.assertFalse(
            self.manager.has_position("005930")
        )
        self.assertTrue(
            self.manager.has_position("000660")
        )

    def test_api_failure_raises_error(self):
        self.balance_fetcher.return_value = {
            "rt_cd": "1",
            "msg_cd": "ERROR",
            "msg1": "계좌 조회 실패",
        }

        with self.assertRaises(BalanceResponseError):
            self.manager.refresh()

    def test_invalid_quantity_type(self):
        self.manager.refresh()

        with self.assertRaises(TypeError):
            self.manager.can_sell("005930", 1.5)

    def test_invalid_quantity_value(self):
        self.manager.refresh()

        with self.assertRaises(ValueError):
            self.manager.can_sell("005930", 0)

    def test_clear(self):
        self.manager.refresh()
        self.manager.clear()

        self.assertEqual(
            self.manager.get_all_positions(),
            {},
        )
        self.assertEqual(
            self.manager.get_account_summary(),
            {},
        )


if __name__ == "__main__":
    unittest.main()