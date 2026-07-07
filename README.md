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
strategy.py (Planned)
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

* [ ] Moving Average Strategy
* [ ] RSI Strategy
* [ ] MACD Strategy
* [ ] Breakout Strategy

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
