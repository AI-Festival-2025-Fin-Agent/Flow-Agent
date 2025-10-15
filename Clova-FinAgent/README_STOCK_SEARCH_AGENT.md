# Stock Search Agent - 질문 타입별 분기 전략 및 최적화 가이드

## 🎯 핵심 효율화 로직

### 1. 기본 Tool 기반 + 정확성을 위한 TEXT2SQL 보완
```python
# 기본: 미리 정의된 Tool 사용 (빠르고 안정적)
"get_stock_price", "search_volume", "get_rsi_signals" 등

# 정확성 보완: 복잡한 계산/집계는 TEXT2SQL로 처리
- "전체 시장 대비 비율 계산"
- "전날대비 거래량 변화율" 
- "복합 조건 검색"
→ 미리 정의된 Tool로 불가능한 정확한 계산
```

### 2. 파라미터 부족 시 Clarifier 노드로 재질문
```python
# 도구 실행 결과에서 에러 패턴 감지
error_keywords = [
    "질문을 이해할 수 없습니다",
    "날짜 정보를 찾을 수 없습니다", 
    "조건을 찾을 수 없습니다"
]

if validation_status == "param_missing" and retry_count < 2:
    return "clarifier"  # 사용자에게 구체적 정보 요청
```

### 3. 토큰 제한 대응: Result Filter 노드로 사전 차단
```python
# 문제: 검색 결과가 너무 많으면 generation_node에서 토큰 초과
# 해결: filter_node에서 미리 개수 제한

# 필터링 대상 도구들 (대량 결과 가능성)
TOOLS_NEED_FILTERING = {
    "search_price_change", "search_volume", "search_compound", 
    "get_rsi_signals", "text2sql"
}

# 지능형 제한 로직
if any(keyword in query for keyword in ['모두', '전체']):
    limit = 무제한  # 사용자가 명시적으로 전체 요청
elif re.search(r'(\d+)개', query):
    limit = 사용자지정개수
elif len(stock_like_lines) > 100:
    limit = 100  # 토큰 제한 방지
```

### 4. 3단계 정확성 보장 체계
1. **Tool 우선 실행** → 빠른 응답
2. **TEXT2SQL 보완** → 복잡한 계산 정확성 
3. **Clarifier 재질문** → 파라미터 부족 시 정확성 확보

## 1. 질문 타입 분류 및 분기 전략

### 1.1 질문 타입별 분류

#### A. 단순 조회형 질문
**패턴**: "종목의 날짜 정보는?"
```
예시:
- "삼성전자의 2024-11-06 종가는?"
- "SK하이닉스 찾아줘"
- "2024-11-06 KOSPI 지수는?"
```
**분기**: agent_node → parse_node → tools_node → generation_node
**도구 선택**: 1개 도구만 사용

#### B. 순위/랭킹형 질문
**패턴**: "상위/하위 N개", "1위", "순위"
```
예시:
- "2024-11-06 상승률 1위는?"
- "거래량 상위 10개 종목은?"
- "KOSPI에서 가장 비싼 종목 5개는?"
```
**분기**: agent_node → parse_node → tools_node → filter_decision → result_filter_node → generation_node
**도구 선택**: search_price_change, search_volume, search_price 등

#### C. 비교형 질문
**패턴**: "A vs B", "종목 vs 시장평균"
```
예시:  
- "삼성전자와 SK하이닉스 비교해줘"
- "셀트리온이 시장평균보다 어떤지?"
```
**분기**: agent_node → parse_node → tools_node (병렬) + text2sql_node → generation_node
**도구 선택**: 여러 도구 동시 호출 전략

#### D. 복합조건형 질문
**패턴**: "조건1 AND 조건2 AND 조건3"
```
예시:
- "등락률 +3% 이상이면서 거래량 100만주 이상인 종목은?"
- "RSI 70 이상이면서 가격이 1만원 이하인 종목은?"
```
**분기**: parse_node → tools_node (search_compound) → filter_decision → result_filter_node
**도구 선택**: search_compound 우선, 복잡한 경우 text2sql

#### E. 계산/집계형 질문
**패턴**: "전체 대비 비율", "전날 대비", "평균", "합계"
```
예시:
- "셀트리온 거래량이 전체 시장의 몇 %인가?"
- "전날대비 거래량 300% 이상 증가한 종목"
- "시장 평균 등락률은?"
```
**분기**: parse_node → text2sql_node → filter_decision → generation_node
**도구 선택**: text2sql 필수

#### F. 기술적 분석형 질문
**패턴**: "RSI", "볼린저", "이동평균", "골든크로스"
```
예시:
- "RSI 70 이상 과매수 종목은?"
- "데드크로스 발생한 종목은?"
- "20일 이동평균 돌파한 종목은?"
```
**분기**: parse_node → tools_node (technical) → filter_decision → result_filter_node
**도구 선택**: get_rsi_signals, get_cross_signals, get_ma_breakout 등

## 2. 각 노드별 정확성 향상 전략

### 2.1 agent_node - 도구 선택 정확성

#### 정확성 향상 방법:
1. **상세한 도구 설명 매핑**:
```python
descriptions = {
    "get_stock_price": "특정 종목의 특정날짜의 시가/고가/저가/종가/거래량/등락률을 조회",
    "search_price_change": "등락률 기준 검색. 상승률/하락률 순위 조회 및 등락률 범위 검색",
    "get_volume_surge": "거래량 급증 종목 검색. 20일 평균 대비 100%, 200%, 300%, 500% 이상 급증",
    "text2sql": "복잡한 계산이나 집계가 필요한 쿼리. 전날대비 비교, 시장 비율 계산"
}
```

2. **질문 타입별 전략 명시**:
```python
prompt = f"""
**질문 분석 및 도구 선택 전략**:
1. **단순 조회**: 1개 도구 사용
2. **비교 질문**: 여러 도구 동시 사용 (권장) - A vs B, 종목 vs 시장평균 등
3. **복잡한 집계**: TEXT2SQL 사용

**비교 질문 처리 예시 (여러 도구 동시 호출)**:
- 종목 vs 시장평균 → TOOL_CALL: {{"name": "get_stock_price", "args": "종목의 등락률"}} + TOOL_CALL: {{"name": "text2sql", "args": "시장 평균 등락률"}}
"""
```

3. **구체적 사용 예시 제공**:
- 40여개의 실제 질문-도구 매핑 예시
- 복합조건과 TEXT2SQL 구분 기준 명확화

### 2.2 parse_node - 파싱 정확성

#### 정확성 향상 방법:
1. **다중 패턴 파싱**:
```python
# 패턴 1: 표준 TOOL_CALL 형식
pattern1 = r'TOOL_CALL:\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})'

# 패턴 2: JSON 블록 또는 백틱 (TEXT2SQL용)  
pattern2 = r'```json\s*(\{[^}]*"action"[^}]*"text2sql"[^}]*\})\s*```'

# 패턴 3: TEXT2SQL action JSON
pattern3 = r'(\{[^{}]*"action"[^{}]*"text2sql"[^{}]*\})'

# 패턈 4: 일반 name/args JSON
pattern4 = r'(\{[^{}]*"name"[^{}]*"args"[^{}]*(?:\{[^{}]*\}[^{}]*)*\})'
```

2. **중첩 JSON 구조 지원**:
- 복잡한 args 객체 처리
- JSON 파싱 실패 시 대체 로직

### 2.3 tools_node - 실행 정확성

#### 정확성 향상 방법:
1. **파라미터 부족 감지**:
```python
error_keywords = [
    "질문을 이해할 수 없습니다",
    "날짜 정보를 찾을 수 없습니다", 
    "조건을 찾을 수 없습니다",
    "임계값을 찾을 수 없습니다",
    "파라미터를 추출할 수 없습니다"
]

if any(keyword in result for keyword in error_keywords):
    validation_status = "param_missing"
```

2. **상세 실행 로깅**:
```python
tool_result_detail = {
    "tool_name": tool_name,
    "tool_args": tool_args,
    "execution_time": exec_duration,
    "result_length": len(str(result)),
    "full_result": result,
    "status": validation_status,
    "timestamp": exec_end_time.isoformat()
}
```

### 2.4 text2sql_node - SQL 생성 정확성

#### 정확성 향상 방법:
1. **스키마 정보 자동 수집**:
```python
def _get_schema_for_columns(self, columns: List[str]) -> str:
    schema_parts = [STOCK_PRICES_SCHEMA]
    for column_type in columns:
        if column_type in COLUMN_DESCRIPTIONS:
            schema_parts.append(f"\n### {column_type} 관련 정보:")
```

2. **SQL 추출 및 검증**:
- 여러 SQL 패턴 감지
- 실행 전 기본 문법 검증

### 2.5 result_filter_node - 결과 정확성

#### 정확성 향상 방법:
1. **지능형 종목 패턴 감지**:
```python
stock_like_lines = []
for line in lines:
    if any([
        re.search(r'[\w가-힣]+\s*\([\w\d]+\)', line),  # "삼성전자 (005930)"
        re.search(r'^\d+\.\s*[\w가-힣]', line),      # "1. 삼성전자"
        re.search(r'[\w가-힣]+\s*\|\s*[\d,]+', line),  # "삼성전자 | 50,000"
    ]):
        stock_like_lines.append(line)
```

2. **사용자 의도 파악**:
```python
# 사용자가 "모두", "전체", "모든"을 요청한 경우 제한하지 않음
if any(keyword in query.lower() for keyword in ['모두', '전체', '모든']):
    should_limit = False
elif re.search(r'(\d+)개', query):
    # 구체적 개수 요청
    limit = int(match.group(1))
```

## 3. 토큰 제한 최적화 전략

### 3.1 2단계 모델 전략

#### 모델 역할 분리:
```python
# HCX-007 (더 강력, 더 비쌈): 중요한 작업
self.llm_main = ChatClovaX(model="HCX-007", temperature=0.1)
- 쿼리 분석 및 도구 선택 (agent_node)
- TEXT2SQL 생성 (text2sql_node)

# HCX-005 (가벼움, 저렴): 사소한 작업  
self.llm_simple = ChatClovaX(model="HCX-005", temperature=0.1)
- 파라미터 추출 (query_parser)
- 최종 응답 생성 (generation_node)
```

### 3.2 각 노드별 토큰 최적화

#### agent_node 최적화:
```python
# 도구 설명을 간결하게 정리
tool_descriptions = []
for tool in self.tools:
    tool_descriptions.append(f"- {tool.name}: {tool.description}")
tools_text = "\n".join(tool_descriptions)

# 불필요한 반복 설명 제거, 핵심 예시만 포함
```

#### parse_node 최적화:
- LLM 호출 없음 (정규식 파싱만 사용)
- 토큰 사용량 0

#### tools_node 최적화:
```python
# 도구별 개별 호출, LLM 사용 안함
tool_func = lambda query, name=tool_name: self.query_parser.parse_and_execute(name, query)
```

#### text2sql_node 최적화:
```python
# 필요한 스키마 정보만 선별적 포함
schema_info = self._get_schema_for_columns(columns)

# SQL 생성 시 간결한 프롬프트 사용
sql_prompt = self._build_sql_prompt(query, schema_info, query_type)
```

#### result_filter_node 최적화:
- LLM 호출 없음 (정규식 기반 필터링)
- 토큰 사용량 0

#### generation_node 최적화:
```python
# 간단한 템플릿 기반 응답 생성
generation_prompt = f"""사용자 질문에 대한 도구 실행 결과를 그대로 전달하세요.

사용자 질문: {query}
도구 실행 결과: {tool_result}

**필수 규칙**: 도구 결과를 그대로 복사해서 전달
답변:"""

# HCX-005 사용으로 비용 절감
response = llm_simple.invoke([HumanMessage(content=generation_prompt)])
```

## 4. 분기 결정 로직

### 4.1 should_continue (parse 후 분기)
```python
def should_continue(state: StockSearchState) -> str:
    tool_calls = state.get("tool_calls", [])
    
    if not tool_calls:
        return "generation"  # 도구 호출이 없으면 바로 응답 생성
    
    has_text2sql = any(call.get("name") == "text2sql" for call in tool_calls)
    has_regular_tools = any(call.get("name") != "text2sql" for call in tool_calls)
    
    if has_text2sql and has_regular_tools:
        return "tools"  # 일반 도구 먼저 실행
    elif has_text2sql:
        return "text2sql"
    elif has_regular_tools:
        return "tools"
    else:
        return "generation"
```

### 4.2 after_tools_routing (tools 후 분기)
```python
def after_tools_routing(state: StockSearchState) -> str:
    validation_status = state.get("validation_status", "success")
    retry_count = state.get("retry_count", 0)
    
    # 파라미터 부족 시 명확화 요청 (최대 2회)
    if validation_status == "param_missing" and retry_count < 2:
        return "clarifier"
    
    # text2sql이 남아있는지 확인
    has_text2sql = any(call.get("name") == "text2sql" for call in tool_calls)
    if has_text2sql:
        return "text2sql"
    
    return "filter_decision"
```

### 4.3 should_filter_results (필터링 결정)
```python
def should_filter_results(state: StockSearchState) -> str:
    tool_calls = state.get("tool_calls", [])
    
    # 필터링 필요 도구들
    TOOLS_NEED_FILTERING = {
        "search_price_change", "search_volume", "search_price", 
        "search_compound", "get_rsi_signals", "get_ma_breakout",
        "get_volume_surge", "get_cross_signals", "text2sql"
    }
    
    needs_filtering = any(
        call.get("name") in TOOLS_NEED_FILTERING 
        for call in tool_calls
    )
    
    return "result_filter" if needs_filtering else "generation"
```

## 5. 실제 질문별 처리 흐름

### 예시 1: "삼성전자의 2024-11-06 종가는?"
```
agent_node: get_stock_price 선택
↓
parse_node: TOOL_CALL 파싱
↓  
tools_node: get_stock_price 실행
↓
filter_decision: 필터링 불필요
↓
generation_node: 최종 응답
```

### 예시 2: "2024-11-06 상승률 상위 10개는?"
```
agent_node: search_price_change 선택
↓
parse_node: TOOL_CALL 파싱
↓
tools_node: search_price_change 실행 (상위 10개)
↓
filter_decision: 필터링 필요
↓
result_filter_node: 10개 제한 확인
↓  
generation_node: 최종 응답
```

### 예시 3: "전날대비 거래량 300% 이상 증가한 종목"
```
agent_node: text2sql 선택 (복잡한 계산)
↓
parse_node: TEXT2SQL 파싱
↓
text2sql_node: SQL 생성 및 실행
↓
filter_decision: 필터링 필요
↓
result_filter_node: 100개 제한 적용
↓
generation_node: 최종 응답
```

이러한 세밀한 분기 전략과 최적화를 통해 정확성을 높이고 토큰 사용량을 최소화했습니다.