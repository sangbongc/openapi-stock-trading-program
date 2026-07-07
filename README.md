# KIS Rule-Based Trading Program

## Project Overview

A Python-based rule-based stock trading system utilizing the Korea Investment & Securities OpenAPI.
This project is designed to automate the entire investment workflow, including market data collection, storage, technical indicator calculation, strategy execution, and order management.

---

# Tech Stack

* Python
* Korea Investment OpenAPI
* SQLite
* Pandas
* Requests
* Git / GitHub

---

# System Architecture

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
strategies (Planned)
        │
        ▼
Dashboard / Trading (Planned)
```

---

# Project Structure

```text
.
├── api.py              # Korea Investment OpenAPI communication
├── config.py           # Environment configuration
├── database.py         # SQLite database management
├── indicator.py        # Technical indicators
├── main.py             # Program entry point
├── parser.py           # API response parser
├── universe.py         # Stock universe
├── requirements.txt
├── .env.example
└── README.md
```

---

# Current Features

### OpenAPI

* Access Token 발급
* Access Token Cache (`token.json`)
* 현재가 조회 API
* 일봉 조회 API

### Data Processing

* JSON → Python Dictionary Parsing
* API Response Normalization

### Database

* SQLite Database 구축
* `current_prices` Table
* `daily_prices` Table
* 복합 Primary Key (`stock_code`, `date`)
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

### Strategy Logic
## Strategy Calculation Logic

현재 프로젝트의 전략 모듈은 가격 데이터(`DataFrame`)를 입력받아 `BUY`, `SELL`, `HOLD` 중 하나의 신호를 반환한다.
각 전략은 공통적으로 `close` 컬럼을 기준으로 계산한다.

---

### 1. Moving Average Cross Strategy

이동평균선 교차 전략은 단기 이동평균선과 장기 이동평균선의 교차 여부를 기준으로 매매 신호를 판단한다.

#### 계산 방식

단기 이동평균선:

```python
short_ma = close.rolling(window=short_window).mean()
```

장기 이동평균선:

```python
long_ma = close.rolling(window=long_window).mean()
```

예를 들어 `short_window=5`, `long_window=20`이면 최근 5일 평균 종가와 최근 20일 평균 종가를 계산한다.

#### 매수 조건

이전 시점에는 단기 이동평균선이 장기 이동평균선보다 낮거나 같았지만, 현재 시점에서 단기 이동평균선이 장기 이동평균선을 상향 돌파하면 매수 신호를 발생시킨다.

```python
prev_short <= prev_long and latest_short > latest_long
```

즉, 골든크로스가 발생한 경우이다.

#### 매도 조건

이전 시점에는 단기 이동평균선이 장기 이동평균선보다 높거나 같았지만, 현재 시점에서 단기 이동평균선이 장기 이동평균선을 하향 돌파하면 매도 신호를 발생시킨다.

```python
prev_short >= prev_long and latest_short < latest_long
```

즉, 데드크로스가 발생한 경우이다.

#### 신호 판단

```text
골든크로스 발생 → BUY
데드크로스 발생 → SELL
그 외 → HOLD
```

---

### 2. RSI Strategy

RSI 전략은 가격 상승폭과 하락폭을 비교하여 현재 주가가 과매수 상태인지, 과매도 상태인지 판단하는 전략이다.

#### 계산 방식

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

상대강도(RS)를 계산한다.

```python
rs = avg_gain / avg_loss
```

RSI는 다음 공식으로 계산한다.

```python
rsi = 100 - (100 / (1 + rs))
```

#### 매수 조건

RSI가 30보다 낮으면 과매도 상태로 판단하여 매수 신호를 발생시킨다.

```python
latest_rsi < 30
```

#### 매도 조건

RSI가 70보다 높으면 과매수 상태로 판단하여 매도 신호를 발생시킨다.

```python
latest_rsi > 70
```

#### 신호 판단

```text
RSI < 30 → BUY
RSI > 70 → SELL
그 외 → HOLD
```

---

### 3. Bollinger Band Strategy

볼린저 밴드 전략은 이동평균선과 표준편차를 이용하여 주가가 통계적으로 높은 구간인지 낮은 구간인지 판단하는 전략이다.

#### 계산 방식

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

기본 설정은 `period=20`, `num_std=2.0`이다.

#### 매수 조건

현재 종가가 하단 밴드보다 낮으면 주가가 과도하게 하락한 것으로 판단하여 매수 신호를 발생시킨다.

```python
latest_close < latest_lower
```

#### 매도 조건

현재 종가가 상단 밴드보다 높으면 주가가 과도하게 상승한 것으로 판단하여 매도 신호를 발생시킨다.

```python
latest_close > latest_upper
```

#### 신호 판단

```text
현재가 < 하단 밴드 → BUY
현재가 > 상단 밴드 → SELL
그 외 → HOLD
```

---

### 4. MACD Strategy

MACD 전략은 단기 지수이동평균과 장기 지수이동평균의 차이를 이용하여 추세 전환을 판단하는 전략이다.

#### 계산 방식

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

기본 설정은 `short_period=12`, `long_period=26`, `signal_period=9`이다.

#### 매수 조건

이전 시점에는 MACD선이 Signal선보다 낮거나 같았지만, 현재 시점에서 MACD선이 Signal선을 상향 돌파하면 매수 신호를 발생시킨다.

```python
prev_macd <= prev_signal and latest_macd > latest_signal
```

#### 매도 조건

이전 시점에는 MACD선이 Signal선보다 높거나 같았지만, 현재 시점에서 MACD선이 Signal선을 하향 돌파하면 매도 신호를 발생시킨다.

```python
prev_macd >= prev_signal and latest_macd < latest_signal
```

#### 신호 판단

```text
MACD선이 Signal선을 상향 돌파 → BUY
MACD선이 Signal선을 하향 돌파 → SELL
그 외 → HOLD
```

---

## Strategy Signal Summary

| Strategy       | BUY 조건                                   | SELL 조건                                  | HOLD 조건       |
| -------------- | -------------------------------------------|-------------------------------------------| ----------------|
| MA Cross       | 단기 이동평균선이 장기 이동평균선을 상향 돌파 | 단기 이동평균선이 장기 이동평균선을 하향 돌파 | 교차 없음        |
| RSI            | RSI < 30                                   | RSI > 70                                  | 30 ≤ RSI ≤ 70   |
| Bollinger Band | 현재가 < 하단 밴드                          | 현재가 > 상단 밴드                         | 밴드 내부        |
| MACD           | MACD선이 Signal선을 상향 돌파               | MACD선이 Signal선을 하향 돌파               | 교차 없음        |


### Software Architecture

* API Layer 분리
* Parser Layer 분리
* Database Layer 분리
* Indicator Layer 분리
* Token Cache 적용
* Modular Project Structure

---

# Roadmap

## Phase 1 (Completed)

### Project Setup

* [x] GitHub Repository 구축
* [x] 프로젝트 구조 설계
* [x] Environment Variable 관리 (.env)
* [x] .gitignore 구성

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
* [x] JSON → Dictionary 변환

### Technical Indicators

* [x] Moving Average
* [x] Volume Moving Average
* [x] RSI
* [x] MACD
* [x] Bollinger Bands
* [x] Rolling Mean Function

---

## Phase 2 (In Progress)

### Strategy Engine

* [x] Moving Average Strategy
* [x] RSI Strategy
* [x] MACD Strategy
* [x] Bollinger Band Strategy


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

## Phase 3 (Planned)

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

# Future Vision

This project aims to evolve beyond a simple trading bot into an integrated investment decision support platform by combining market data, technical analysis, financial statement analysis, visualization, and automated trading.

---

# Database Schema

current_prices
daily_prices
(향후)
orders
positions
strategy_logs

# Execution Flow

Program Start
    ↓
Access Token
    ↓
Collect Daily Prices
    ↓
Save to SQLite
    ↓
Data Loader(현재는 indicator에서 병합 수행)
    ↓
Data Preporcessor(dart api 활용시 사용예정)
    ↓
Calculate Indicators
    ↓
Strategy Engine
    ↓
Manual / Auto Trading