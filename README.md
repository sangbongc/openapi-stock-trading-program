# KIS OpenAPI Rule-Based Auto Trading Program

## 📌 Project Overview

한국투자증권 OpenAPI를 활용한 **규칙 기반(Rule-Based) 자동매매 프로그램**입니다.

단순한 API 호출 예제가 아니라 실제 자동매매 시스템을 목표로 개발하고 있으며, 모듈화를 통해 유지보수성과 확장성을 고려한 구조로 설계하였습니다.

주요 목표는 다음과 같습니다.

* 한국투자증권 OpenAPI 기반 자동매매
* SQLite 기반 데이터 관리
* 기술적 지표 자동 계산
* 전략(Strategy) 기반 매매 의사결정
* 주문 및 주문 이력 관리
* 향후 백테스트 및 포트폴리오 분석 지원

---

# Tech Stack

* Python 3
* SQLite
* Pandas
* KIS OpenAPI
* unittest / unittest.mock
* Git / GitHub

---

# Project Structure

```text
kis-rule-based-trading-program/

├── api.py
├── config.py
├── database.py
├── parser.py
├── indicator.py
├── universe.py
│
├── trading/
│   └── order_manager.py
│
├── strategies/
│   ├── __init__.py
│   ├── base_strategy.py
│   ├── signal.py
│   ├── result.py
│   ├── strategy_factory.py
│   ├── strategy_engine.py
│   ├── ma_cross.py
│   ├── rsi.py
│   ├── macd.py
│   └── bollinger.py
│
├── tests/
│   ├── test_strategy_factory.py
│   ├── test_strategy_engine.py
│   ├── test_order_manager.py
│   └── ...
│
├── trading.db
├── README.md
└── requirements.txt
```

---

# Current Features

## OpenAPI

* OAuth2 인증 및 Access Token 발급
* Access Token 캐싱
* 현재가 조회
* 일봉 데이터 조회
* 시장가 / 지정가 매수 주문
* 시장가 / 지정가 매도 주문

---

## SQLite Database

구현 완료

* 현재가 저장
* 일봉 저장
* 주문 내역 저장
* 종목별 일봉 조회
* 데이터 일괄 저장(Bulk Insert)

---

## Technical Indicators

직접 Pandas를 이용하여 계산하도록 구현

지원 지표

* Moving Average
* RSI
* MACD
* Bollinger Bands

---

## Strategy System

전략을 독립적인 클래스로 구현

현재 지원 전략

* Moving Average Cross
* RSI
* MACD
* Bollinger Bands

공통 인터페이스

* BaseStrategy

결과 객체

* StrategyResult
* Signal Enum

---

## Strategy Engine

구현 완료

기능

* 여러 전략 실행
* 전략 결과 통합
* 최종 BUY / SELL / HOLD 결정
* 다수결 기반 최종 Signal 생성

---

## Strategy Factory

구현 완료

기능

* 전략 객체 생성
* 전략 리스트 생성
* 이름 기반 전략 관리

---

## Order Manager

구현 완료

기능

* 매수 주문 실행
* 매도 주문 실행
* 입력값 검증
* 주문 성공 / 실패 처리
* 주문 결과 SQLite 저장
* API 예외 처리

현재 OrderManager는 **주문 접수(ACCEPTED)** 까지의 역할을 담당합니다.

---

# Testing

단위 테스트 완료

테스트 대상

* Strategy Factory
* Strategy Engine
* MA Cross Strategy
* RSI Strategy
* MACD Strategy
* Bollinger Band Strategy
* OrderManager

테스트 항목

* 정상 동작
* 입력값 검증
* 예외 처리
* Mock을 이용한 API 호출 테스트
* Mock을 이용한 DB 저장 테스트

---

# Development Roadmap

## Phase 1 (Completed)

* [x] OpenAPI 연동
* [x] SQLite 구축
* [x] Parser 구현
* [x] Indicator 구현
* [x] Strategy 구현
* [x] Strategy Factory
* [x] Strategy Engine
* [x] Order Manager

---

## Phase 2 (In Progress)

* [ ] Execution Manager
* [ ] Position Manager
* [ ] Order Fill Tracking
* [ ] Portfolio Management
* [ ] Risk Management

---

## Phase 3 (Planned)

* [ ] Market Scanner
* [ ] Backtesting
* [ ] DART OpenAPI 연동
* [ ] Streamlit Dashboard
* [ ] Portfolio Analytics
* [ ] Performance Report
* [ ] Trade Log Visualization

---

# Future Improvements

* 실시간 체결 관리
* 부분 체결 처리
* 계좌 잔고 및 보유 종목 동기화
* 주문 상태 자동 갱신
* 다중 전략 조합
* 리스크 기반 포지션 사이징
* 실시간 자동매매
* 백테스트 엔진 구축
* 공시(DART) 데이터 기반 투자 의사결정

---

# Project Goal

본 프로젝트는 한국투자증권 OpenAPI를 활용한 단순 API 예제가 아니라,

**실제 운용 가능한 자동매매 시스템 구축**을 목표로 개발 중입니다.

또한 객체지향 설계, 모듈화, 단위 테스트를 적극 활용하여 유지보수성과 확장성을 고려한 구조를 지향하고 있습니다.
