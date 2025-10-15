"""
Text2SQL을 위한 데이터베이스 스키마 정보 및 컬럼별 설명
"""

# 기본 테이블 구조
STOCK_PRICES_SCHEMA = """
CREATE TABLE stock_prices (
    trading_date TEXT,          -- 거래일 (YYYY-MM-DD 형식)
    ticker TEXT,                -- 종목 코드 (예: 005930.KS, 035420.KQ)
    stock_name TEXT,            -- 종목명 (예: 삼성전자, 네이버)
    market TEXT,                -- 시장 구분 (KOSPI/KOSDAQ)
    
    -- 가격 정보
    open_price REAL,            -- 시가 (시초가)
    high_price REAL,            -- 고가 (당일 최고가)
    low_price REAL,             -- 저가 (당일 최저가)
    close_price REAL,           -- 종가 (마감가)
    adj_close_price REAL,       -- 조정 종가
    prev_close_price REAL,      -- 전일 종가
    
    -- 변동 정보
    change REAL,                -- 전일 대비 변동액 (원)
    change_rate REAL,           -- 전일 대비 등락률 (%)
    
    -- 거래 정보
    trading_volume INTEGER      -- 거래량 (주)
);
"""

# 컬럼별 세부 설명
COLUMN_DESCRIPTIONS = {
    "거래량": {
        "columns": ["trading_volume"],
        "description": """
        거래량 관련 쿼리:
        - trading_volume: 해당 날짜에 거래된 주식 수량 (단위: 주)
        - 전날 대비 거래량 비교: LAG() 함수 사용
        - 거래량 증가율: ((오늘 거래량 - 전날 거래량) / 전날 거래량) * 100
        
        예시 SQL:
        -- 전날 대비 거래량 100% 이상 증가
        SELECT stock_name, trading_volume,
               LAG(trading_volume) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_volume,
               ((trading_volume - LAG(trading_volume) OVER (PARTITION BY ticker ORDER BY trading_date)) / 
                LAG(trading_volume) OVER (PARTITION BY ticker ORDER BY trading_date)) * 100 as volume_change_rate
        FROM stock_prices 
        WHERE volume_change_rate >= 100
        """,
        "sample_conditions": [
            "거래량이 100만주 이상",
            "전날 대비 거래량 50% 이상 증가", 
            "거래량 상위 10개",
            "평균 거래량의 2배 이상"
        ]
    },
    
    "주가": {
        "columns": ["open_price", "high_price", "low_price", "close_price", "adj_close_price"],
        "description": """
        주가 관련 쿼리:
        - open_price: 시가 (장 시작 가격)
        - high_price: 고가 (당일 최고 가격)  
        - low_price: 저가 (당일 최저 가격)
        - close_price: 종가 (장 마감 가격, 가장 일반적)
        - adj_close_price: 조정 종가 (분할/배당 반영)
        
        예시 SQL:
        -- 종가가 10만원 이상 20만원 이하
        SELECT stock_name, close_price 
        FROM stock_prices 
        WHERE close_price BETWEEN 100000 AND 200000
        
        -- 고가가 종가보다 10% 이상 높은 경우
        SELECT stock_name, high_price, close_price,
               ((high_price - close_price) / close_price) * 100 as high_close_diff
        FROM stock_prices 
        WHERE high_close_diff >= 10
        """,
        "sample_conditions": [
            "종가가 5만원 이상",
            "시가와 종가 차이가 5% 이상",
            "고가 기준 상위 10개",
            "가격 범위 검색"
        ]
    },
    
    "등락률": {
        "columns": ["change", "change_rate", "prev_close_price"],
        "description": """
        등락률 관련 쿼리:
        - change_rate: 전일 대비 등락률 (%, 음수=하락, 양수=상승)
        - change: 전일 대비 변동액 (원)
        - prev_close_price: 전일 종가 (비교 기준)
        
        계산 공식:
        change_rate = ((close_price - prev_close_price) / prev_close_price) * 100
        change = close_price - prev_close_price
        
        예시 SQL:
        -- 등락률 +5% 이상 상승
        SELECT stock_name, close_price, change_rate 
        FROM stock_prices 
        WHERE change_rate >= 5.0
        
        -- 하락률 상위 10개
        SELECT stock_name, change_rate 
        FROM stock_prices 
        WHERE change_rate < 0 
        ORDER BY change_rate ASC 
        LIMIT 10
        """,
        "sample_conditions": [
            "등락률 +3% 이상",
            "하락률 -5% 이하", 
            "상승률 상위 20개",
            "등락률 절댓값 10% 이상"
        ]
    },
    
    "복합조건": {
        "columns": ["trading_date", "ticker", "stock_name", "market", "trading_volume", "close_price", "change_rate"],
        "description": """
        복합 조건 쿼리 (여러 조건 동시 만족):
        - 날짜 조건: trading_date
        - 시장 구분: market ('KOSPI' 또는 'KOSDAQ')
        - 종목 조건: ticker, stock_name
        
        예시 SQL:
        -- 등락률 +2% 이상이면서 거래량 전날 대비 100% 이상 증가
        WITH volume_comparison AS (
            SELECT *,
                   LAG(trading_volume) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_volume
            FROM stock_prices 
            WHERE trading_date IN ('2024-09-10', '2024-09-11')
        )
        SELECT stock_name, close_price, change_rate, trading_volume,
               ((trading_volume - prev_volume) / prev_volume) * 100 as volume_change_rate
        FROM volume_comparison
        WHERE trading_date = '2024-09-11' 
          AND change_rate >= 2.0 
          AND ((trading_volume - prev_volume) / prev_volume) * 100 >= 100
        """,
        "sample_conditions": [
            "등락률 +2% 이상 + 거래량 100만주 이상",
            "KOSDAQ에서 종가 1만원~5만원 + 상승률 +5% 이상",
            "전날 대비 가격 10% 상승 + 거래량 2배 증가"
        ]
    }
}

# 시장별 티커 패턴
MARKET_PATTERNS = {
    "KOSPI": "%.KS",
    "KOSDAQ": "%.KQ", 
    "KONEX": "%.KN"
}

# 자주 사용되는 SQL 패턴
COMMON_PATTERNS = {
    "전날_대비_비교": """
    LAG(컬럼명) OVER (PARTITION BY ticker ORDER BY trading_date) as prev_컬럼명
    """,
    
    "증가율_계산": """
    ((현재값 - 이전값) / 이전값) * 100 as 증가율
    """,
    
    "순위_매기기": """
    ROW_NUMBER() OVER (ORDER BY 컬럼명 DESC) as ranking
    """,
    
    "시장_필터링": """
    WHERE ticker LIKE '%.KS'  -- KOSPI
    WHERE ticker LIKE '%.KQ'  -- KOSDAQ
    """
}