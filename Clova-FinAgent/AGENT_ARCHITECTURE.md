# StockSearchAgent 구조 분석서

## 📊 전체 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────┐
│                    StockSearchAgent                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   LLM Models    │  │   QueryParser   │  │ DatabaseManager │  │
│  │                 │  │                 │  │                 │  │
│  │ • HCX-007 (주요) │  │ • 16개 도구매핑  │  │ • 4개 DB 연결   │  │
│  │ • HCX-005 (보조) │  │ • 파라미터 추출  │  │ • 종목/시장정보  │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 🔄 LangGraph 워크플로우

```
사용자 입력
    │
    ▼
┌─────────────────┐
│   agent_node    │ ◄── LLM이 질문 분석 및 도구 선택
│ (LLM 분석)      │
└─────────────────┘
    │
    ▼ should_continue()
┌─────────────────┐     tool_calls 있음?
│                 │ ────────────┬─── YES ──┐
│                 │             │          │
│                 │             └─── NO ───┼──► END
└─────────────────┘                        │
    │                                      │
    ▼                                      │
┌─────────────────┐                        │
│   tool_node     │ ◄── 도구 실행 및 검증   │
│ (도구 실행)      │                        │
└─────────────────┘                        │
    │                                      │
    ▼ should_clarify()                     │
┌─────────────────┐                        │
│  검증 결과는?    │                        │
└─────────────────┘                        │
    │                                      │
    ├─── param_missing + retry<2 ──┐       │
    │                               │       │
    ├─── success ──────────────┐    │       │
    │                          │    │       │
    └─── error ────────────────┼────┼───────┘
                               │    │
                               ▼    ▼
                    ┌─────────────────┐  ┌─────────────────┐
                    │ generation_node │  │ clarifier_node  │
                    │   (응답 생성)    │  │  (명확화 요청)   │
                    └─────────────────┘  └─────────────────┘
                               │                   │
                               ▼                   ▼
                             END                 END
```

## 🛠️ 도구 분류 및 분기처리

### 📈 기본 정보 조회 도구
```
get_stock_price          ┌─ 개별 종목 정보
get_market_stats         ├─ 시장 전체 통계  
get_market_index         ├─ KOSPI/KOSDAQ 지수
search_company           └─ 회사명 검색
```

### 🔍 조건별 검색 도구
```
search_price             ┌─ 가격 기준 (순위/범위)
search_price_change      ├─ 등락률 기준 (상승률/하락률)
search_volume            ├─ 거래량 기준 (순위/임계값)
search_trading_value_ranking └─ 거래대금 순위
```

### 📊 기술분석 도구  
```
get_rsi_signals          ┌─ RSI 과매수/과매도
get_bollinger_signals    ├─ 볼린저 밴드 터치
get_ma_breakout          ├─ 이동평균 돌파
get_volume_surge         ├─ 거래량 급증
get_cross_signals        ├─ 골든크로스/데드크로스 (목록)
count_cross_signals      ├─ 골든크로스/데드크로스 (횟수)
search_compound          └─ 복합조건 검색
```

### 🗄️ 고급 분석 도구
```
TEXT2SQL                 └─ 복잡한 계산/집계 (LLM→SQL 변환)
```

## 🎯 사용자 입력별 분기처리 로직

### 1단계: LLM 질문 분석
```
사용자 질문 입력
    │
    ▼
┌─────────────────────────────────────────┐
│          LLM 질문 분석                   │
├─────────────────────────────────────────┤
│  • 단순 조회     → 1개 도구 사용         │
│  • 비교 질문     → 여러 도구 동시 사용    │  
│  • 복잡한 집계   → TEXT2SQL 사용         │
└─────────────────────────────────────────┘
    │
    ▼
도구 호출 패턴 결정
```

### 2단계: 도구 호출 패턴

#### 🎯 단일 도구 호출
```
"삼성전자 주가"              → get_stock_price
"상승률 순위"               → search_price_change  
"RSI 과매수 종목"           → get_rsi_signals
"거래량 급증 종목"          → get_volume_surge
```

#### 🎯 다중 도구 동시 호출
```
"삼성전자 vs LG전자"        → get_stock_price(삼성전자) 
                            + get_stock_price(LG전자)
                            
"종목 vs 시장평균"          → get_stock_price(종목)
                            + TEXT2SQL(시장평균)
```

#### 🎯 TEXT2SQL 사용
```
"전체 시장 대비 비율"       → TEXT2SQL: 비율 계산
"전날 대비 거래량 100% 증가" → TEXT2SQL: 전날 비교  
"복잡한 집계 분석"          → TEXT2SQL: SQL 직접 생성
```

## 🔧 파라미터 추출 및 검증 시스템

### 파라미터 추출 과정
```
도구 선택 완료
    │
    ▼
┌─────────────────────────────────────────┐
│        LLM 파라미터 추출                 │
├─────────────────────────────────────────┤
│  • 각 도구별 JSON 스키마 적용            │
│  • 규칙 기반 매핑 (날짜, 종목명 등)       │
│  • 기본값 적용 (날짜: 2024-11-06)       │
└─────────────────────────────────────────┘
    │
    ▼
도구 실행
    │
    ▼
┌─────────────────────────────────────────┐
│           결과 검증                      │
├─────────────────────────────────────────┤
│  파라미터 부족 감지 키워드:               │
│  • "질문을 이해할 수 없습니다"            │
│  • "날짜 정보를 찾을 수 없습니다"         │
│  • "조건을 찾을 수 없습니다"             │
└─────────────────────────────────────────┘
    │
    ▼
validation_status 설정
```

### 검증 결과별 분기
```
validation_status
    │
    ├─── success ──────────┐
    │                      │
    ├─── param_missing ────┼─── retry_count < 2? 
    │                      │           │
    └─── tool_error ───────┘           ├─── YES → clarifier_node
                                       │
                                       └─── NO → END
                                       
                           generation_node
```

## 📋 실행 흐름 예시

### 예시 1: 성공적인 단순 조회
```
INPUT: "삼성전자 주가"
    │
    ▼ agent_node
LLM 분석: get_stock_price 선택
    │
    ▼ tool_node  
파라미터 추출: ticker="삼성전자", date="2024-11-06"
도구 실행: 성공
validation_status = "success"
    │
    ▼ generation_node
사용자 친화적 응답 생성
    │
    ▼
OUTPUT: "삼성전자(005930.KS)의 2024-11-06 종가는 58,400원입니다..."
```

### 예시 2: 파라미터 부족으로 명확화 요청
```
INPUT: "상승률 높은 종목"
    │
    ▼ agent_node
LLM 분석: search_price_change 선택
    │
    ▼ tool_node
파라미터 추출: 날짜 정보 부족
도구 실행: "날짜 정보를 찾을 수 없습니다"
validation_status = "param_missing"
    │
    ▼ clarifier_node
구체적 정보 요청
    │
    ▼
OUTPUT: "질문을 더 구체적으로 해주세요. 정확한 날짜가 필요합니다..."
```

### 예시 3: 복합 조건 검색
```
INPUT: "등락률 +3% 이상이면서 거래량 100만주 이상"
    │
    ▼ agent_node
LLM 분석: search_compound 선택
    │
    ▼ tool_node
파라미터 추출: date="2024-11-06", change_rate_min=3.0, volume_min=1000000
도구 실행: 복합조건 쿼리 성공
validation_status = "success"
    │
    ▼ generation_node
조건 만족 종목 목록 포맷팅
    │
    ▼
OUTPUT: "조건을 만족하는 종목 15개: 1. 종목A (종가: 12,500원...) ..."
```

## 🗃️ 데이터베이스 구조

### 데이터베이스 연결
```
DatabaseManager
    │
    ├─ stock_info.db           (주가 정보)
    │   └─ stock_prices 테이블
    │
    ├─ market_index.db         (시장 지수)  
    │   └─ market_index 테이블
    │
    ├─ technical_indicators.db (기술지표)
    │   └─ technical_indicators 테이블
    │
    └─ company_info.csv        (기업 정보)
```

### 주요 테이블 스키마
```
stock_prices:
├─ ticker (종목코드)
├─ stock_name (종목명)  
├─ trading_date (거래날짜)
├─ open_price, high_price, low_price, close_price
├─ trading_volume (거래량)
├─ change_rate (등락률)
└─ market (KOSPI/KOSDAQ)

technical_indicators:
├─ ticker, trading_date
├─ rsi, ma5, ma20, ma60, ma120
├─ bb_upper, bb_middle, bb_lower
├─ volume_ratio
├─ golden_cross, dead_cross
└─ macd, macd_signal, macd_histogram
```

## 🎛️ 설정 및 모델

### LLM 모델 구성
```
┌─────────────────┐    ┌─────────────────┐
│   llm_main      │    │   llm_simple    │
│   (HCX-007)     │    │   (HCX-005)     │
├─────────────────┤    ├─────────────────┤
│ • 쿼리 분석     │    │ • 최종 응답 생성 │
│ • 도구 선택     │    │ • 파라미터 추출  │
│ • TEXT2SQL 생성 │    │                 │
└─────────────────┘    └─────────────────┘
```

### 상태 관리
```
StockSearchState:
├─ messages: 대화 메시지
├─ query: 사용자 질문
├─ result: 실행 결과
├─ tool_calls: 도구 호출 목록
├─ iterations: 반복 횟수
├─ validation_status: 검증 상태
├─ clarification_needed: 명확화 필요 여부
├─ retry_count: 재시도 횟수
├─ execution_log: 실행 로그 (상세)
├─ tool_results: 도구 실행 결과 (상세)  
├─ node_traces: 노드별 실행 추적
└─ state_history: 상태 변화 이력
```

## 🔍 핵심 특징

### ✅ 장점
- **지능적 분기처리**: LLM이 질문 유형을 판단하여 최적 도구 선택
- **동시 도구 실행**: 비교 질문 시 여러 도구 병렬 처리로 효율성 향상
- **자동 파라미터 추출**: 자연어를 구조화된 파라미터로 자동 변환
- **강력한 오류 처리**: 파라미터 부족 시 사용자에게 구체적 정보 요청
- **확장 가능한 구조**: 새로운 도구 추가가 용이한 모듈화 설계

### ⚠️ 복잡성
- **다층 구조**: Agent → QueryParser → 다중 DB 연결
- **상태 관리**: 복잡한 상태 추적 및 로깅 시스템
- **LLM 의존성**: 파라미터 추출과 도구 선택의 LLM 의존도 높음

---

> 💡 **결론**: 이 에이전트는 사용자의 자연어 질문을 16개의 전문 도구와 TEXT2SQL을 통해 처리하는 정교한 주식 분석 시스템입니다. LangGraph 기반의 상태 관리와 지능적 분기처리를 통해 복잡한 금융 질의응답을 효과적으로 해결합니다.