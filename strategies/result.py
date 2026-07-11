from dataclasses import dataclass

from .signal import Signal


@dataclass
class StrategyResult:
    strategy: str
    signal: Signal
    confidence: float
    reason: str