from strategies.ma_cross import MACrossStrategy
from strategies.rsi_strategy import RSIStrategy
from strategies.bollinger_strategy import BollingerBandStrategy
from strategies.macd_strategy import MACDStrategy


STRATEGY_REGISTRY = {
    "ma_cross": MACrossStrategy,
    "rsi": RSIStrategy,
    "bollinger": BollingerBandStrategy,
    "macd": MACDStrategy,
}


def create_strategy(strategy_name: str):
    if strategy_name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy: {strategy_name}")

    return STRATEGY_REGISTRY[strategy_name]()


def create_strategies(strategy_names: list):
    return [create_strategy(name) for name in strategy_names]