# OpenAPI Stock Trading Program

> **Python 기반 한국투자증권 OpenAPI 자동매매 시스템**

한국투자증권 OpenAPI를 활용하여 **실제 모의투자 계좌에서 동작하는 Rule-Based 자동매매 시스템**입니다.

단순한 API 호출 예제가 아니라 **시장 데이터 수집 → 전략 생성 → 주문 → 체결 관리 → 계좌 동기화 → 자동 반복 실행**까지 하나의 구조로 구현하는 것을 목표로 개발하고 있습니다.

향후에는 OpenDART API를 연동하여 재무정보와 공시 데이터를 활용한 투자 의사결정 기능과 백테스팅, 머신러닝 기반 전략 최적화를 추가할 예정입니다.

---

# Features

## Data Collection

* 한국투자 OpenAPI 연동
* 현재가 조회
* 일봉 데이터 수집
* SQLite 저장

---

## Technical Indicators

현재 구현된 기술적 지표

* Moving Average (MA)
* RSI
* MACD
* Bollinger Band

모든 지표는 Pandas를 이용하여 직접 계산하며 Strategy Engine에서 공통으로 사용됩니다.

---

## Strategy Engine

현재 구현 전략

* MA Cross Strategy
* RSI Strategy
* MACD Strategy
* Bollinger Band Strategy

### 특징

* Strategy Pattern 적용
* Strategy Factory 구현
* 가중치 기반 Signal Aggregation
* Threshold 기반 최종 매매 신호 결정

최종 신호

* BUY
* SELL
* HOLD

---

## Trading Engine

Trading Engine은 아래 순서로 동작합니다.

```
Strategy Engine
        ↓
Trading Decision
        ↓
Order Manager
        ↓
Execution Manager
        ↓
Position Manager
```

자동으로

* 보유 여부 확인
* 매수 가능 여부 판단
* 매도 가능 수량 확인
* 주문 생성

을 수행합니다.

---

## Order Management

지원 기능

* 시장가 매수
* 시장가 매도
* 지정가 주문
* 주문 DB 저장
* 주문 상태 관리

주문 상태

* ACCEPTED
* FAILED
* REJECTED

---

## Execution Management

지원 기능

* 주문 체결 조회
* 체결 내역 저장
* 평균 체결가 저장
* 주문 상태 자동 갱신

Orders 테이블과 Executions 테이블이 자동으로 동기화됩니다.

---

## Position Management

실제 계좌 기준으로

* 보유 종목
* 평균 매입 단가
* 평가 금액
* 예수금

을 조회하고 SQLite와 동기화합니다.

---

## Trading Controller

CLI 기반 자동매매 컨트롤러를 제공합니다.

지원 명령어

```
collect
run
start
stop
sync
status
account
positions
manual
results
help
exit
```

---

# Automatic Trading

자동매매는 두 개의 작업을 독립적으로 수행합니다.

## Strategy Loop (기본 300초)

```
Position Refresh
        ↓
Strategy
        ↓
Order
```

## Execution Sync Loop (기본 10초)

```
Execution Sync
        ↓
Orders Update
        ↓
Position Refresh
```

자동매매가 실행되는 동안 체결 내역을 주기적으로 확인하여 실제 계좌와 데이터베이스를 지속적으로 동기화합니다.

---

# Project Structure

```
.
├── api.py
├── config.py
├── database.py
├── indicator.py
├── main.py
├── parser.py
├── universe.py
│
├── database/
│
├── strategies/
│   ├── base_strategy.py
│   ├── strategy_engine.py
│   ├── strategy_factory.py
│   ├── ma_cross.py
│   ├── rsi_strategy.py
│   ├── macd_strategy.py
│   ├── bollinger_strategy.py
│
├── trading/
│   ├── trading_controller.py
│   ├── trading_engine.py
│   ├── order_manager.py
│   ├── execution_manager.py
│   └── position_manager.py
│
└── tests/
```

---

# Tech Stack

* Python
* SQLite
* Pandas
* 한국투자 OpenAPI
* Pytest

---

# System Workflow

```
Market Data
      ↓
SQLite Database
      ↓
Technical Indicators
      ↓
Strategy Engine
      ↓
Trading Engine
      ↓
Order Manager
      ↓
KIS OpenAPI
      ↓
Execution Manager
      ↓
Position Manager
      ↓
Database Synchronization
```

---

# Tested Features

다음 기능들의 동작을 실제 모의투자 계좌에서 검증했습니다.

* OpenAPI 인증
* 현재가 조회
* 일봉 데이터 수집
* SQLite 저장
* 기술적 지표 계산
* Strategy Engine
* Strategy Factory
* Trading Engine
* Order Manager
* Execution Manager
* Position Manager
* 수동 매수
* 수동 매도
* 자동 주문
* 자동 체결 동기화
* 실제 계좌와 DB 동기화

---

# Development Roadmap

## ✅ Completed

* OpenAPI Authentication
* SQLite Database
* Current Price Collection
* Daily Price Collection
* Technical Indicators
* Strategy Engine
* Strategy Factory
* Trading Engine
* Order Manager
* Execution Manager
* Position Manager
* Trading Controller
* Manual Buy / Sell
* Automatic Trading Loop
* Periodic Execution Synchronization
* Real Account Synchronization

---

## 🚧 In Progress

* Logging System
* Performance Statistics
* Portfolio Analytics

---

## 📌 Planned

* Backtesting Engine
* OpenDART Integration
* Financial Statement Database
* Disclosure Analysis
* Machine Learning Strategy Optimization
* Streamlit Dashboard
* WebSocket Real-Time Trading

---

# Future Goals

향후 OpenDART 기반 재무정보 분석 프로젝트와 통합하여

* 기술적 분석
* 재무제표 분석
* 공시 분석
* 머신러닝 기반 전략 최적화

를 하나의 투자 플랫폼으로 발전시키는 것을 목표로 하고 있습니다.
