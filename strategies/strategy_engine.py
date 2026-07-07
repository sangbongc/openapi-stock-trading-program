from collections import Counter

import pandas as pd

from strategies.signal import Signal


class StrategyEngine:
    def __init__(self, strategies: list):
        self.strategies = strategies

    def run(self, df: pd.DataFrame) -> dict:
        strategy_results = {}

        for strategy in self.strategies:
            strategy_name = strategy.__class__.__name__
            signal = strategy.generate_signal(df)
            strategy_results[strategy_name] = signal

        final_signal = self._decide_final_signal(strategy_results)

        return {
            "strategy_results": strategy_results,
            "final_signal": final_signal,
        }

    def _decide_final_signal(self, strategy_results: dict) -> Signal:
        signals = list(strategy_results.values())

        if not signals:
            return Signal.HOLD

        counts = Counter(signals)

        buy_count = counts[Signal.BUY]
        sell_count = counts[Signal.SELL]
        hold_count = counts[Signal.HOLD]

        max_count = max(buy_count, sell_count, hold_count)

        top_signals = [
            signal
            for signal, count in counts.items()
            if count == max_count
        ]

        if len(top_signals) > 1:
            return Signal.HOLD

        return top_signals[0]