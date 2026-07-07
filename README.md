# KIS Rule-Based Trading Program

## Project Overview

A Python-based rule-based stock trading system using the Korea Investment & Securities OpenAPI.

This project is a reconstruction and expansion of a stock trading automation assignment originally implemented in an economics programming course.
The goal is to build a modular investment decision support system that can collect market data, store it in a database, calculate technical indicators, generate strategy signals, and eventually support backtesting, dashboard visualization, and automated trading.

---

## Tech Stack

* Python
* Korea Investment & Securities OpenAPI
* SQLite
* Pandas
* Requests
* Git / GitHub

---

## System Architecture

```text
KIS OpenAPI
        │
        ▼
api.py
        │
        ▼
parser.py
        │
        ▼
SQLite Database
(database.py)
        │
        ▼
indicator.py
        │
        ▼
strategies/
        │
        ▼
Strategy Engine
        │
        ▼
Dashboard / Trading / Backtesting
```

---

## Project Structure

```text
.
├── api.py                  # Korea Investment OpenAPI communication
├── config.py               # Environment variable and API configuration
├── database.py             # SQLite database management
├── indicator.py            # Technical indicator calculation
├── main.py                 # Program entry point
├── parser.py               # API response parser
├── universe.py             # Stock universe management
├── data/                   # Local data storage
├── strategies/             # Rule-based trading strategies
│   ├── __init__.py
│   ├── base_strategy.py
│   ├── signal.py
│   ├── ma_cross.py
│   ├── rsi_strategy.py
│   ├── bollinger_strategy.py
│   └── macd_strategy.py
├── tests/                  # Strategy and module tests
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Current Features

### OpenAPI

* Access Token 발급
* Access Token Cache 적용
* 현재가 조회 API
* 일봉 조회 API

### Data Processing

* JSON API Response Parsing
* API Response Normalization
* 종목별 가격 데이터 변환

### Database

* SQLite Database 구축
* `current_prices` Table
* `daily_prices` Table
* Composite Primary Key 적용
* 현재가 저장
* 일봉 저장
* 종목별 일봉 조회

### Technical Indicators

* Moving Average
* Volume Moving Average
* RSI
* MACD
* Bollinger Bands
* Generic Rolling Mean Function

### Strategy Module

* Moving Average Cross Strategy
* RSI Strategy
* Bollinger Band Strategy
* MACD Strategy
* `Signal` Enum을 통한 공통 매매 신호 관리

  * `BUY`
  * `SELL`
  * `HOLD`

---

## Strategy Calculation Logic

현재 프로젝트의 전략 모듈은 가격 데이터 `DataFrame`을 입력받아 `BUY`, `SELL`, `HOLD` 중 하나의 신호를 반환한다.

각 전략은 기본적으로 `close` 컬럼을 기준으로 계산한다.

---

### 1. Moving Average Cross Strategy

Moving Average Cross 전략은 단기 이동평균선과 장기 이동평균선의 교차 여부를 기준으로 매매 신호를 판단한다.

현재 전략 코드는 이미 계산된 이동평균 컬럼을 사용하여 교차 여부를 판단하는 구조이다.

예를 들어 다음과 같은 이동평균 컬럼을 사용한다.

```python
ma5
ma20
```

단기 이동평균선은 짧은 기간의 평균 가격을 의미하고, 장기 이동평균선은 더 긴 기간의 평균 가격을 의미한다.

일반적인 이동평균 계산식은 다음과 같다.

```python
short_ma = close.rolling(window=short_window).mean()
long_ma = close.rolling(window=long_window).mean()
```

#### BUY 조건

이전 시점에는 단기 이동평균선이 장기 이동평균선보다 낮거나 같았지만, 현재 시점에서 단기 이동평균선이 장기 이동평균선을 상향 돌파하면 매수 신호를 발생시킨다.

```python
prev_short <= prev_long and latest_short > latest_long
```

이는 일반적으로 골든크로스라고 부른다.

#### SELL 조건

이전 시점에는 단기 이동평균선이 장기 이동평균선보다 높거나 같았지만, 현재 시점에서 단기 이동평균선이 장기 이동평균선을 하향 돌파하면 매도 신호를 발생시킨다.

```python
prev_short >= prev_long and latest_short < latest_long
```

이는 일반적으로 데드크로스라고 부른다.

#### Signal

```text
Golden Cross → BUY
Dead Cross   → SELL
No Cross     → HOLD
```

---

### 2. RSI Strategy

RSI 전략은 가격의 상승폭과 하락폭을 비교하여 현재 주가가 과매수 상태인지, 과매도 상태인지 판단하는 전략이다.

#### Calculation

먼저 종가의 변화량을 계산한다.

```python
delta = close.diff()
```

상승분과 하락분을 분리한다.

```python
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)
```

평균 상승폭과 평균 하락폭을 계산한다.

```python
avg_gain = gain.rolling(window=period).mean()
avg_loss = loss.rolling(window=period).mean()
```

상대강도 `RS`를 계산한다.

```python
rs = avg_gain / avg_loss
```

RSI는 다음 공식으로 계산한다.

```python
rsi = 100 - (100 / (1 + rs))
```

#### BUY 조건

RSI가 30보다 낮으면 과매도 상태로 판단하여 매수 신호를 발생시킨다.

```python
latest_rsi < 30
```

#### SELL 조건

RSI가 70보다 높으면 과매수 상태로 판단하여 매도 신호를 발생시킨다.

```python
latest_rsi > 70
```

#### Signal

```text
RSI < 30 → BUY
RSI > 70 → SELL
Otherwise → HOLD
```

---

### 3. Bollinger Band Strategy

Bollinger Band 전략은 이동평균선과 표준편차를 이용하여 현재 주가가 통계적으로 높은 구간인지 낮은 구간인지 판단하는 전략이다.

#### Calculation

중심선은 일정 기간의 이동평균으로 계산한다.

```python
middle_band = close.rolling(window=period).mean()
```

같은 기간의 표준편차를 계산한다.

```python
std = close.rolling(window=period).std()
```

상단 밴드와 하단 밴드는 다음과 같이 계산한다.

```python
upper_band = middle_band + num_std * std
lower_band = middle_band - num_std * std
```

기본 설정은 다음과 같다.

```python
period = 20
num_std = 2.0
```

#### BUY 조건

현재 종가가 하단 밴드보다 낮으면 주가가 과도하게 하락한 것으로 판단하여 매수 신호를 발생시킨다.

```python
latest_close < latest_lower
```

#### SELL 조건

현재 종가가 상단 밴드보다 높으면 주가가 과도하게 상승한 것으로 판단하여 매도 신호를 발생시킨다.

```python
latest_close > latest_upper
```

#### Signal

```text
Close < Lower Band → BUY
Close > Upper Band → SELL
Inside Band        → HOLD
```

---

### 4. MACD Strategy

MACD 전략은 단기 지수이동평균과 장기 지수이동평균의 차이를 이용하여 추세 전환을 판단하는 전략이다.

#### Calculation

단기 지수이동평균을 계산한다.

```python
short_ema = close.ewm(span=short_period, adjust=False).mean()
```

장기 지수이동평균을 계산한다.

```python
long_ema = close.ewm(span=long_period, adjust=False).mean()
```

MACD선은 단기 EMA에서 장기 EMA를 차감하여 계산한다.

```python
macd = short_ema - long_ema
```

Signal선은 MACD선의 지수이동평균으로 계산한다.

```python
signal_line = macd.ewm(span=signal_period, adjust=False).mean()
```

기본 설정은 다음과 같다.

```python
short_period = 12
long_period = 26
signal_period = 9
```

#### BUY 조건

이전 시점에는 MACD선이 Signal선보다 낮거나 같았지만, 현재 시점에서 MACD선이 Signal선을 상향 돌파하면 매수 신호를 발생시킨다.

```python
prev_macd <= prev_signal and latest_macd > latest_signal
```

#### SELL 조건

이전 시점에는 MACD선이 Signal선보다 높거나 같았지만, 현재 시점에서 MACD선이 Signal선을 하향 돌파하면 매도 신호를 발생시킨다.

```python
prev_macd >= prev_signal and latest_macd < latest_signal
```

#### Signal

```text
MACD crosses above Signal Line → BUY
MACD crosses below Signal Line → SELL
No Cross                       → HOLD
```

---

## Strategy Signal Summary

| Strategy             | BUY 조건                    | SELL 조건                   | HOLD 조건       |
| -------------------- | ------------------------- | ------------------------- | ------------- |
| Moving Average Cross | 단기 이동평균선이 장기 이동평균선을 상향 돌파 | 단기 이동평균선이 장기 이동평균선을 하향 돌파 | 교차 없음         |
| RSI                  | RSI < 30                  | RSI > 70                  | 30 ≤ RSI ≤ 70 |
| Bollinger Band       | 현재가 < 하단 밴드               | 현재가 > 상단 밴드               | 밴드 내부         |
| MACD                 | MACD선이 Signal선을 상향 돌파     | MACD선이 Signal선을 하향 돌파     | 교차 없음         |

---

## Software Architecture

* API Layer 분리
* Parser Layer 분리
* Database Layer 분리
* Indicator Layer 분리
* Strategy Layer 분리
* Token Cache 적용
* Modular Project Structure

---

## How to Run Tests

프로젝트 루트 디렉터리에서 다음과 같이 실행한다.

```bash
python -m tests.test_ma_cross
python -m tests.test_rsi_strategy
python -m tests.test_bollinger_strategy
python -m tests.test_macd_strategy
```

`python -m` 방식으로 실행하면 프로젝트 루트를 기준으로 패키지를 인식하므로, `strategies` 모듈을 안정적으로 import할 수 있다.

---

## Roadmap

## Phase 1: Completed

### Project Setup

* [x] GitHub Repository 구축
* [x] 프로젝트 구조 설계
* [x] Environment Variable 관리
* [x] `.gitignore` 구성

### OpenAPI

* [x] Access Token 발급
* [x] Token Cache 구현
* [x] 현재가 조회 API
* [x] 일봉 조회 API

### Database

* [x] SQLite 구축
* [x] Current Price 저장
* [x] Daily Price 저장
* [x] Composite Primary Key 적용
* [x] 종목별 조회 기능

### Data Processing

* [x] API Parser 구현
* [x] JSON Response 변환

### Technical Indicators

* [x] Moving Average
* [x] Volume Moving Average
* [x] RSI
* [x] MACD
* [x] Bollinger Bands
* [x] Rolling Mean Function

---

## Phase 2: In Progress

### Strategy Module

* [x] Signal Enum
* [x] Base Strategy 구조
* [x] Moving Average Cross Strategy
* [x] RSI Strategy
* [x] Bollinger Band Strategy
* [x] MACD Strategy
* [ ] Strategy Engine
* [ ] Multiple Strategy Aggregation
* [ ] Final Signal Decision Logic

### Market Scanner

* [ ] Volume Top Stocks
* [ ] Price Change Top Stocks
* [ ] Dynamic Stock Universe

### Manual Trading

* [ ] Manual Buy
* [ ] Manual Sell
* [ ] Order History
* [ ] Position Management

### Dashboard

* [ ] Streamlit Dashboard
* [ ] Candlestick Chart
* [ ] Indicator Visualization
* [ ] Strategy Signal Visualization

---

## Phase 3: Planned

### Auto Trading

* [ ] Rule-based Auto Trading
* [ ] Strategy Selection
* [ ] Scheduled Execution
* [ ] Trading Log

### Fundamental Analysis

* [ ] DART API Integration
* [ ] Financial Statement Parsing
* [ ] Financial Ratio Analysis

### Backtesting

* [ ] Strategy Backtesting
* [ ] Performance Report
* [ ] Portfolio Analytics

### Future Improvements

* [ ] Risk Management Module
* [ ] AI-based Stock Ranking
* [ ] Portfolio Optimization
* [ ] Explainable Strategy Logs

---

## Future Vision

This project aims to evolve beyond a simple trading bot into an integrated investment decision support platform by combining market data, technical analysis, financial statement analysis, visualization, backtesting, and automated trading.

The long-term goal is to build a modular system where each component can be independently improved and connected into a full investment workflow.

```text
Market Data
    +
Technical Indicators
    +
Rule-based Strategies
    +
Financial Statement Analysis
    +
Backtesting
    +
Dashboard
    +
Trading Execution
```
