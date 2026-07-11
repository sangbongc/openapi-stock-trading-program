from strategies.base_strategy import BaseStrategy
from strategies.bollinger_strategy import BollingerBandStrategy
from strategies.ma_cross import MACrossStrategy
from strategies.macd_strategy import MACDStrategy
from strategies.rsi_strategy import RSIStrategy
from strategies.strategy_factory import StrategyFactory


def test_create_ma_cross_strategy() -> None:
    strategy = StrategyFactory.create_strategy("ma_cross")

    assert isinstance(strategy, MACrossStrategy)
    assert isinstance(strategy, BaseStrategy)


def test_create_rsi_strategy() -> None:
    strategy = StrategyFactory.create_strategy("rsi")

    assert isinstance(strategy, RSIStrategy)
    assert isinstance(strategy, BaseStrategy)


def test_create_bollinger_strategy() -> None:
    strategy = StrategyFactory.create_strategy("bollinger")

    assert isinstance(strategy, BollingerBandStrategy)
    assert isinstance(strategy, BaseStrategy)


def test_create_macd_strategy() -> None:
    strategy = StrategyFactory.create_strategy("macd")

    assert isinstance(strategy, MACDStrategy)
    assert isinstance(strategy, BaseStrategy)


def test_strategy_name_is_normalized() -> None:
    strategy = StrategyFactory.create_strategy("  RSI  ")

    assert isinstance(strategy, RSIStrategy)


def test_create_multiple_strategies() -> None:
    strategies = StrategyFactory.create_strategies([
        "ma_cross",
        "rsi",
        "bollinger",
        "macd",
    ])

    assert len(strategies) == 4
    assert isinstance(strategies[0], MACrossStrategy)
    assert isinstance(strategies[1], RSIStrategy)
    assert isinstance(strategies[2], BollingerBandStrategy)
    assert isinstance(strategies[3], MACDStrategy)


def test_get_available_strategies() -> None:
    available = StrategyFactory.get_available_strategies()

    assert available == [
        "ma_cross",
        "rsi",
        "bollinger",
        "macd",
    ]


def test_rejects_unknown_strategy() -> None:
    try:
        StrategyFactory.create_strategy("unknown")

    except ValueError as error:
        assert "알 수 없는 전략" in str(error)
        assert "ma_cross" in str(error)
        assert "rsi" in str(error)
        assert "bollinger" in str(error)
        assert "macd" in str(error)

    else:
        raise AssertionError(
            "등록되지 않은 전략 이름이면 ValueError가 발생해야 합니다."
        )


def test_rejects_non_string_strategy_name() -> None:
    try:
        StrategyFactory.create_strategy(123)

    except TypeError as error:
        assert str(error) == "strategy_name은 문자열이어야 합니다."

    else:
        raise AssertionError(
            "strategy_name이 문자열이 아니면 "
            "TypeError가 발생해야 합니다."
        )


def test_rejects_empty_strategy_name() -> None:
    try:
        StrategyFactory.create_strategy("   ")

    except ValueError as error:
        assert str(error) == "strategy_name은 빈 문자열일 수 없습니다."

    else:
        raise AssertionError(
            "strategy_name이 빈 문자열이면 "
            "ValueError가 발생해야 합니다."
        )


def test_rejects_non_list_strategy_names() -> None:
    try:
        StrategyFactory.create_strategies(("rsi", "macd"))

    except TypeError as error:
        assert str(error) == "strategy_names는 리스트여야 합니다."

    else:
        raise AssertionError(
            "strategy_names가 리스트가 아니면 "
            "TypeError가 발생해야 합니다."
        )


def test_rejects_empty_strategy_list() -> None:
    try:
        StrategyFactory.create_strategies([])

    except ValueError as error:
        assert str(error) == "최소 하나 이상의 전략 이름이 필요합니다."

    else:
        raise AssertionError(
            "빈 전략 목록이면 ValueError가 발생해야 합니다."
        )


def test_each_call_returns_new_instance() -> None:
    first = StrategyFactory.create_strategy("rsi")
    second = StrategyFactory.create_strategy("rsi")

    assert first is not second


if __name__ == "__main__":
    test_create_ma_cross_strategy()
    test_create_rsi_strategy()
    test_create_bollinger_strategy()
    test_create_macd_strategy()
    test_strategy_name_is_normalized()
    test_create_multiple_strategies()
    test_get_available_strategies()
    test_rejects_unknown_strategy()
    test_rejects_non_string_strategy_name()
    test_rejects_empty_strategy_name()
    test_rejects_non_list_strategy_names()
    test_rejects_empty_strategy_list()
    test_each_call_returns_new_instance()

    print("모든 StrategyFactory 테스트를 통과했습니다.")