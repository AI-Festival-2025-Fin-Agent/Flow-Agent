"""
Text2SQL 노드 구현
복잡한 조건을 SQL로 변환하여 직접 데이터베이스 쿼리 실행
"""

import json
import sqlite3
import pandas as pd
from typing import Dict, Any, List
from langchain.schema import HumanMessage
from .sql_schemas import COLUMN_DESCRIPTIONS, STOCK_PRICES_SCHEMA, COMMON_PATTERNS

class Text2SQLNode:
    def __init__(self, db_path: str, llm):
        self.db_path = db_path
        self.llm = llm
    
    def execute_text2sql(self, query: str, columns: List[str], query_type: str) -> str:
        """TEXT2SQL 실행 메인 함수"""
        try:
            # 1. 컬럼별 스키마 정보 수집
            schema_info = self._get_schema_for_columns(columns)
            
            # 2. SQL 생성 프롬프트 구성
            sql_prompt = self._build_sql_prompt(query, schema_info, query_type)
            
            # 3. LLM으로 SQL 생성
            response = self.llm.invoke([HumanMessage(content=sql_prompt)])
            sql_query = self._extract_sql_from_response(response.content)
            
            print(f"[TEXT2SQL] 생성된 SQL: {sql_query}")
            
            # 4. SQL 실행
            results = self._execute_sql(sql_query)
            
            # 5. 결과 포맷팅
            formatted_result = self._format_results(results, query)
            
            return formatted_result
            
        except Exception as e:
            return f"TEXT2SQL 실행 중 오류 발생: {str(e)}"
    
    def _get_schema_for_columns(self, columns: List[str]) -> str:
        """선택된 컬럼 타입에 해당하는 스키마 정보 반환"""
        schema_parts = [STOCK_PRICES_SCHEMA]
        
        for column_type in columns:
            if column_type in COLUMN_DESCRIPTIONS:
                schema_parts.append(f"\n### {column_type} 관련 정보:")
                schema_parts.append(COLUMN_DESCRIPTIONS[column_type]["description"])
        
        # 공통 패턴 추가
        schema_parts.append("\n### 자주 사용되는 SQL 패턴:")
        for pattern_name, pattern_sql in COMMON_PATTERNS.items():
            schema_parts.append(f"\n{pattern_name}:")
            schema_parts.append(pattern_sql)
        
        return "\n".join(schema_parts)
    
    def _build_sql_prompt(self, query: str, schema_info: str, query_type: str) -> str:
        """SQL 생성을 위한 프롬프트 구성"""
        prompt = f"""당신은 주식 데이터베이스 전문가입니다. 다음 질문을 SQL 쿼리로 변환하세요.

### 데이터베이스 스키마:
{schema_info}

### 사용자 질문:
{query}

### 중요한 규칙:
1. 반드시 stock_prices 테이블만 사용하세요
2. 날짜는 'YYYY-MM-DD' 형식으로 처리하세요
3. 시장 구분: KOSPI는 ticker LIKE '%.KS', KOSDAQ는 ticker LIKE '%.KQ'
4. SQLite 데이터베이스를 사용하므로 'dual' 테이블은 사용하지 마세요
5. 계산이 필요한 경우 서브쿼리나 CTE(WITH절)를 사용하세요
6. 전날 대비 비교는 JOIN을 사용하세요:
   - 현재 날짜와 이전 날짜 데이터를 JOIN
   - 예: t1.trading_date = '2024-10-28' AND t2.trading_date = '2024-10-27'
7. 결과는 의미있는 컬럼들만 SELECT 하세요 (stock_name, close_price, change_rate, trading_volume 등)
8. LIMIT을 명시하지 않은 경우 상위 50개로 제한하세요
9. 퍼센트 계산: (new_value - old_value) / old_value >= 비율 (예: 1.0 = 100%)

### 예시 쿼리:

**1. 전날 대비 비교:**
```sql
-- 전날 대비 거래량 100% 증가한 종목
SELECT t1.stock_name, t1.trading_volume, t2.trading_volume as prev_volume,
       ROUND((t1.trading_volume - t2.trading_volume) * 100.0 / t2.trading_volume, 2) as growth_rate
FROM stock_prices t1
JOIN stock_prices t2 ON t1.ticker = t2.ticker
WHERE t1.trading_date = '2024-10-28' 
  AND t2.trading_date = '2024-10-27'
  AND (t1.trading_volume - t2.trading_volume) * 1.0 / t2.trading_volume >= 1.0
ORDER BY growth_rate DESC
LIMIT 50;
```

**2. 비율 계산 (SQLite 호환):**
```sql
-- 특정 종목의 거래량이 전체 시장 대비 차지하는 비율
WITH market_total AS (
    SELECT SUM(trading_volume) as total_volume
    FROM stock_prices 
    WHERE trading_date = '2025-05-23'
),
company_volume AS (
    SELECT trading_volume
    FROM stock_prices 
    WHERE stock_name = '셀트리온' AND trading_date = '2025-05-23'
)
SELECT 
    cv.trading_volume as company_volume,
    mt.total_volume as market_total,
    ROUND(cv.trading_volume * 100.0 / mt.total_volume, 4) as percentage
FROM company_volume cv, market_total mt;
```

### 출력 형식:
```sql
-- 생성된 SQL 쿼리만 반환
SELECT ...
```

SQL 쿼리:"""
        
        return prompt
    
    def _extract_sql_from_response(self, response: str) -> str:
        """LLM 응답에서 SQL 쿼리 추출"""
        # ```sql ... ``` 패턴 찾기
        import re
        sql_pattern = r'```sql\s*(.*?)\s*```'
        match = re.search(sql_pattern, response, re.DOTALL | re.IGNORECASE)
        
        if match:
            return match.group(1).strip()
        
        # 패턴이 없으면 SELECT로 시작하는 부분 찾기
        lines = response.split('\n')
        sql_lines = []
        in_sql = False
        
        for line in lines:
            line = line.strip()
            if line.upper().startswith('SELECT'):
                in_sql = True
            
            if in_sql:
                sql_lines.append(line)
                # SQL 쿼리가 끝나는 조건들
                if line.endswith(';') or (line and not line.upper().startswith(('SELECT', 'FROM', 'WHERE', 'GROUP', 'ORDER', 'HAVING', 'LIMIT', 'AND', 'OR', 'WITH'))):
                    break
        
        return '\n'.join(sql_lines).rstrip(';')
    
    def _execute_sql(self, sql_query: str) -> pd.DataFrame:
        """SQL 쿼리 실행"""
        conn = sqlite3.connect(self.db_path)
        try:
            df = pd.read_sql_query(sql_query, conn)
            return df
        finally:
            conn.close()
    
    def _format_results(self, df: pd.DataFrame, original_query: str) -> str:
        """결과를 사용자 친화적 형식으로 포맷팅"""
        if df.empty:
            return f"'{original_query}' 조건에 맞는 종목이 없습니다."
        
        # 결과 개수
        result_count = len(df)
        
        # 컬럼명 한글화
        column_mapping = {
            'stock_name': '종목명',
            'close_price': '종가',
            'open_price': '시가', 
            'high_price': '고가',
            'low_price': '저가',
            'change_rate': '등락률',
            'trading_volume': '거래량',
            'trading_date': '날짜',
            'ticker': '종목코드'
        }
        
        # 결과 포맷팅
        result_lines = [f"조건을 만족하는 종목 {result_count}개:"]
        result_lines.append("")
        
        for idx, row in df.head(50).iterrows():  # 최대 50개만 표시
            line_parts = []
            for col in df.columns:
                value = row[col]
                col_name = column_mapping.get(col, col)
                
                if col in ['close_price', 'open_price', 'high_price', 'low_price']:
                    line_parts.append(f"{col_name}: {value:,.0f}원")
                elif col == 'change_rate':
                    line_parts.append(f"{col_name}: {value:+.2f}%")
                elif col == 'trading_volume':
                    line_parts.append(f"{col_name}: {value:,}주")
                else:
                    line_parts.append(f"{col_name}: {value}")
            
            result_lines.append(f"{idx + 1}. {' / '.join(line_parts)}")
        
        if result_count > 50:
            result_lines.append(f"\n... 총 {result_count}개 중 상위 50개만 표시")
        
        return "\n".join(result_lines)