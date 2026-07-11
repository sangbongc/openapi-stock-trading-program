import pandas as pd

from indicator import (
    add_rolling_mean,
    add_rsi,
    add_macd,
    add_bollinger_bands,
)
from strategies.result import StrategyResult
from strategies.signal import Signal
from strategies.strategy_factory import StrategyFactory
from strategies.strategy_engine import StrategyEngine, EngineResult





def create_test_dataframe() -> pd.DataFrame:
    return pd.DataFrame({
        "close": [
            100, 99, 98, 97, 96,
            95, 94, 93, 92, 91,
            90, 91, 92, 93, 94,
            95, 96, 97, 98, 99,
            100, 101, 102, 103, 104,
            105, 106, 107, 108, 109,
            103, 102, 302, 405, 201,
        ],
        "volume": [
            1000, 1100, 1050, 1200, 1150,
            1300, 1250, 1400, 1350, 1500,
            1450, 1600, 1550, 1700, 1650,
            1800, 1750, 1900, 1850, 2000,
            1950, 2100, 2050, 2200, 2150,
            2300, 2250, 2400, 2350, 2500,
            1235, 3242, 1230, 3020, 2350,
        ],
    })





def test_factory_and_engine_integration():
    strategy_names = [
        "ma_cross",
        "rsi",
        "macd",
        "bollinger",
    ]

    # Factory를 통해 전략 객체 생성
    strategies = StrategyFactory.create_strategies(strategy_names)

    assert len(strategies) == len(strategy_names)

    # Engine 생성
    engine = StrategyEngine(strategies)

    # 테스트용 가격 데이터 생성
    df = create_test_dataframe()

    # 전략에서 필요한 지표 계산
    df = add_rolling_mean(
        df,
        column="close",
        windows=[5, 20],
        prefix="ma",
    )
    df = add_rsi(df)
    df = add_macd(df)
    df = add_bollinger_bands(df)   

    # Engine 실행
    result = engine.run(df)

    valid_signals = {
        Signal.BUY,
        Signal.SELL,
        Signal.HOLD,
    }

    # EngineResult 반환 여부
    assert isinstance(result, EngineResult)

    # 최종 신호 검증
    assert isinstance(result.final_signal, Signal)
    assert result.final_signal in valid_signals

    # 신뢰도 값 검증
    assert isinstance(result.confidence_score, float)
    assert isinstance(result.final_confidence, float)

    # 전략별 결과 구조 검증
    assert isinstance(result.strategy_results, dict)
    assert len(result.strategy_results) == len(strategies)

    # 모든 전략이 실행됐는지 확인
    for strategy in strategies:
        assert strategy.name in result.strategy_results

        strategy_result = result.strategy_results[strategy.name]

        assert isinstance(strategy_result, StrategyResult)

    print("전략별 결과:")
    for name, strategy_result in result.strategy_results.items():
        print(name, strategy_result)

    print("최종 신호:", result.final_signal)
    print("신뢰도 점수:", result.confidence_score)
    print("최종 신뢰도:", result.final_confidence)


if __name__ == "__main__":
    test_factory_and_engine_integration()
    print("StrategyFactory + StrategyEngine 통합 테스트 통과")