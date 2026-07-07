from strategies.strategy_factory import create_strategy, create_strategies


strategy = create_strategy("rsi")
print(strategy.name)

strategies = create_strategies(["ma_cross", "rsi", "macd"])
