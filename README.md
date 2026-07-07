openapi-stock-trading-program

This project reconstructs a rule-based simulated trading workflow using Korea Investment Open API. It focuses on API integration, basic risk controls, and transaction logging rather than profitability.

# Development Log

## Phase 1. 프로젝트 초기 구성

* 프로젝트 기본 디렉터리 구조 설계
* GitHub Repository 생성
* Python 개발 환경 구성
* `.env`를 이용한 API Key 관리
* `.gitignore` 설정을 통한 민감 정보 및 데이터베이스 파일 제외

---

## Phase 2. 한국투자증권 OpenAPI 연동

* Access Token 발급 기능 구현
* Access Token 캐싱(`token.json`) 기능 구현
* 현재가 조회 API 연동
* 일봉 데이터 조회 API 연동
* API 응답 예외 처리 기반 마련

---

## Phase 3. 데이터 파싱

* 현재가 API 응답 파싱
* 일봉 데이터 API 응답 파싱
* API 응답(JSON)을 프로젝트 내부 데이터 구조(dict)로 변환하도록 모듈 분리

---

## Phase 4. SQLite 데이터베이스 구축

* SQLite 기반 로컬 데이터베이스 구축
* `current_prices` 테이블 설계
* `daily_prices` 테이블 설계
* 일봉 데이터 저장 기능 구현
* 현재가 저장 기능 구현
* 종목별 일봉 조회 기능 구현
* `(stock_code, date)` 복합 기본키를 적용하여 동일 종목의 중복 저장 방지

---

## Phase 5. Technical Indicator Module

* Pandas 기반 데이터프레임 변환 기능 구현
* 이동평균(MA) 계산 기능 구현
* 거래량 이동평균 계산 기능 구현
* RSI 계산 기능 구현
* MACD 계산 기능 구현
* Bollinger Band 계산 기능 구현
* 공통 이동평균 함수(`add_rolling_mean`)로 리팩터링하여 코드 재사용성 향상

---

## Phase 6. 코드 리팩터링

* API / Parser / Database / Indicator 모듈 분리
* 불필요한 import 제거
* 함수 역할 분리
* 토큰 재사용 구조 개선
* 데이터 저장 구조 개선

---

# Next Development

* Strategy Engine 구현

  * Moving Average Strategy
  * RSI Strategy
  * MACD Strategy
  * Breakout Strategy

* Dashboard 구현

  * 종가 차트
  * 이동평균선 시각화
  * RSI / MACD 시각화
  * Bollinger Band 시각화

* Manual Trading Mode

  * 수동 매수/매도
  * 주문 내역 저장
  * 보유 종목 조회

* Auto Trading Mode

  * 전략 선택
  * 자동 주문 실행
  * 주문 로그 저장
  * 손익 추적

* Market Scanner

  * 거래량 상위 종목
  * 등락률 상위 종목
  * 관심종목 자동 업데이트

* DART API 연동

  * 사업보고서 수집
  * 주요 재무지표 저장
  * 투자 의사결정 보조 기능 추가

* Backtesting Engine

  * 전략별 성과 분석
  * 누적수익률 비교
  * 성능 리포트 생성
