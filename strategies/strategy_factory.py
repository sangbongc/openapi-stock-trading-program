from typing import Type

from strategies.base_strategy import BaseStrategy
from strategies.bollinger_strategy import BollingerBandStrategy
from strategies.ma_cross import MACrossStrategy
from strategies.macd_strategy import MACDStrategy
from strategies.rsi_strategy import RSIStrategy


class StrategyFactory:
    """
    전략 이름을 기반으로 매매 전략 객체를 생성하는 팩토리 클래스.
    """

    _registry: dict[str, Type[BaseStrategy]] = {
        "ma_cross": MACrossStrategy,
        "rsi": RSIStrategy,
        "bollinger": BollingerBandStrategy,
        "macd": MACDStrategy,
    }

    @classmethod
    def create_strategy(
        cls,
        strategy_name: str,
    ) -> BaseStrategy:
        """
        전략 이름에 해당하는 전략 객체를 생성한다.

        Parameters
        ----------
        strategy_name : str
            생성할 전략의 등록 이름

        Returns
        -------
        BaseStrategy
            생성된 전략 객체

        Raises
        ------
        TypeError
            strategy_name이 문자열이 아닌 경우

        ValueError
            등록되지 않은 전략 이름인 경우
        """
        if not isinstance(strategy_name, str):
            raise TypeError("strategy_name은 문자열이어야 합니다.")

        normalized_name = strategy_name.strip().lower()

        if not normalized_name:
            raise ValueError("strategy_name은 빈 문자열일 수 없습니다.")

        strategy_class = cls._registry.get(normalized_name)

        if strategy_class is None:
            available = ", ".join(cls.get_available_strategies())

            raise ValueError(
                f"알 수 없는 전략입니다: {strategy_name}. "
                f"사용 가능한 전략: {available}"
            )

        return strategy_class()

    @classmethod
    def create_strategies(
        cls,
        strategy_names: list[str],
    ) -> list[BaseStrategy]:
        """
        여러 전략 이름을 받아 전략 객체 목록을 생성한다.
        """
        if not isinstance(strategy_names, list):
            raise TypeError("strategy_names는 리스트여야 합니다.")

        if not strategy_names:
            raise ValueError(
                "최소 하나 이상의 전략 이름이 필요합니다."
            )

        return [
            cls.create_strategy(strategy_name)
            for strategy_name in strategy_names
        ]

    @classmethod
    def get_available_strategies(cls) -> list[str]:
        """
        현재 등록된 전략 이름을 반환한다.
        """
        return list(cls._registry.keys())