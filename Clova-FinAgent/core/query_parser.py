"""
쿼리 파싱 핵심 모듈
사용자 쿼리를 분석하고 필요한 파라미터를 추출하여 적절한 기능으로 연결
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional
from langchain.schema import HumanMessage
from .basic_queries import BasicQueries
from .technical_queries import TechnicalQueries


class QueryParser:
    """통합 쿼리 파싱 및 실행"""
    
    def __init__(self, llm, db_manager):
        self.llm = llm
        self.basic_queries = BasicQueries(db_manager)
        self.technical_queries = TechnicalQueries(db_manager)
        self.logger = logging.getLogger(__name__)
        
        # 도구 매핑
        self.tool_mappings = {
            "get_stock_price": self._handle_stock_price,
            "get_market_stats": self._handle_market_stats,
            "get_market_index": self._handle_market_index,

            "search_company": self._handle_company_search,
            "search_price": self._handle_price_search,
            "search_price_change": self._handle_price_change_search,
            "search_volume": self._handle_volume_search,
            "search_trading_value_ranking": self._handle_trading_ranking,

            "get_rsi_signals": self._handle_rsi_signals,
            "get_bollinger_signals": self._handle_bollinger_signals,
            "get_ma_breakout": self._handle_ma_breakout,
            "get_volume_surge": self._handle_volume_surge,
            "get_cross_signals": self._handle_cross_signals,
            "count_cross_signals": self._handle_cross_count,
            "search_compound": self._handle_compound_search,
            "text2sql": self._handle_text2sql
        }
    
    def parse_and_execute(self, tool_name: str, query: str) -> str:
        """쿼리 파싱 후 해당 도구 실행"""
        try:
            self.logger.info(f"쿼리 실행 시작: {tool_name} - {query}")
            
            if tool_name not in self.tool_mappings:
                return f"알 수 없는 도구: {tool_name}"
            
            handler = self.tool_mappings[tool_name]
            result = handler(query)
            
            self.logger.info(f"쿼리 실행 완료: {tool_name}")
            return result
            
        except Exception as e:
            self.logger.error(f"쿼리 실행 중 오류: {str(e)}")
            return f"{tool_name} 실행 중 오류: {str(e)}"
    
    def _extract_parameters(self, query: str, schema: str, rules: str) -> Dict[str, Any]:
        """LLM을 사용한 파라미터 추출"""
        prompt = f"""다음 질문에서 필요한 파라미터를 추출하세요:
주의: 학습된 날짜 이후의 파라미터를 추출해야 할 수도 있습니다.

질문: {query}

JSON으로만 응답: {schema}

{rules}

반드시 JSON 형식으로만 응답하고 다른 설명은 하지 마세요."""
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content.strip()
            
            # JSON 추출 시도
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content)
            if json_match:
                return json.loads(json_match.group())
            
            # 직접 파싱 시도
            return json.loads(content)
            
        except Exception as e:
            self.logger.warning(f"파라미터 추출 실패: {e}")
            return {}
    
    # 각 도구별 핸들러 메서드들
    def _handle_stock_price(self, query: str) -> str:
        """주가 조회 처리"""
        params = self._extract_parameters(
            query,
            '{"ticker": "종목코드나종목명", "date": "YYYY-MM-DD"}',
            "종목명인 경우 그대로 유지하고, 질문에 날짜가 명시되어 있지 않으면 '2025-09-15' 사용"
        )
        ticker = params.get("ticker", "005930")
        date = params.get("date", "2025-09-15")
        
        return self.basic_queries.get_stock_price_info(ticker, date)
    
    def _handle_company_search(self, query: str) -> str:
        """회사 검색 처리"""
        # 간단한 정규식으로 회사명 추출
        return self.basic_queries.search_company_by_name(query)
    
    def _handle_market_stats(self, query: str) -> str:
        """시장 통계 처리"""
        params = self._extract_parameters(
            query,
            '{"date": "YYYY-MM-DD"}',
            "질문에 날짜가 명시되어 있지 않으면 '2025-09-15' 사용"
        )
        date = params.get("date", "2025-09-15")
        
        return self.basic_queries.get_market_statistics(date)
    
    
    def _handle_trading_ranking(self, query: str) -> str:
        """거래대금 순위 처리"""
        params = self._extract_parameters(
            query,
            '{"date": "YYYY-MM-DD", "limit": 10}',
            "질문에 날짜가 명시되어 있지 않으면 '2025-09-15', 개수가 없으면 10 사용"
        )
        date = params.get("date", "2025-09-15")
        limit = params.get("limit", 10)
        
        return self.basic_queries.get_trading_value_ranking(date, limit)
    
    
    def _handle_market_index(self, query: str) -> str:
        """시장 지수 처리 (KOSPI/KOSDAQ)"""
        params = self._extract_parameters(
            query,
            '{"date": "YYYY-MM-DD", "market": "KOSPI"}',
            """규칙:
- date: 질문에 날짜가 명시되어 있지 않으면 "2025-09-15" 사용
- market: "KOSPI" 또는 "KOSDAQ" (기본값: "KOSPI")
  예: "KOSDAQ 지수", "코스닥" → "KOSDAQ"
  예: "KOSPI 지수", "코스피" → "KOSPI\""""
        )
        date = params.get("date", "2025-09-15")
        market = params.get("market", "KOSPI")
        
        return self.basic_queries.get_market_index(date, market)
    
    def _handle_rsi_signals(self, query: str) -> str:
        """RSI 신호 처리"""
        params = self._extract_parameters(
            query,
            '{"date": "YYYY-MM-DD", "rsi_min": null, "rsi_max": null}',
            """규칙:
- date: 질문에 날짜가 명시되어 있지 않으면 "2025-09-15" 사용
- rsi_min: RSI 최소값 (예: "RSI 70 이상", "과매수" → 70.0)
- rsi_max: RSI 최대값 (예: "RSI 30 이하", "과매도" → 30.0)
- 과매수만 언급되면 rsi_min: 70.0, 과매도만 언급되면 rsi_max: 30.0"""
        )
        date = params.get('date', '2025-09-15')
        rsi_min = params.get('rsi_min')
        rsi_max = params.get('rsi_max')
        
        return self.technical_queries.get_rsi_signals(date, rsi_min, rsi_max)
    
    def _handle_bollinger_signals(self, query: str) -> str:
        """볼린저 밴드 신호 처리"""
        params = self._extract_parameters(
            query,
            '{"date": "YYYY-MM-DD", "band_type": "upper|lower"}',
            "질문에 날짜가 명시되어 있지 않으면 '2025-09-15' 사용, '상단'/'upper' → 'upper', '하단'/'lower' → 'lower'"
        )
        date = params.get('date', '2025-09-15')
        band_type = params.get('band_type', 'upper')
        
        return self.technical_queries.get_bollinger_signals(date, band_type)
    
    def _handle_ma_breakout(self, query: str) -> str:
        """이동평균 돌파 처리"""
        params = self._extract_parameters(
            query,
            '{"date": "YYYY-MM-DD", "ma_period": 20, "breakout_ratio": 0.03}',
            """규칙:
- date: 질문에 날짜가 명시되어 있지 않으면 "2025-09-15" 사용
- ma_period: "5일"/"MA5" → 5, "20일"/"MA20" → 20, "60일"/"MA60" → 60, 없으면 20 사용
- breakout_ratio: "1%" → 0.01, "3%" → 0.03, "5%" → 0.05, "10%" → 0.10, 없으면 0.03 사용"""
        )
        date = params.get('date', '2025-09-15')
        ma_period = params.get('ma_period', 20)
        breakout_ratio = params.get('breakout_ratio', 0.03)
        
        return self.technical_queries.get_ma_breakout_stocks(date, ma_period, breakout_ratio)
    
    def _handle_volume_surge(self, query: str) -> str:
        """거래량 급증 처리"""
        params = self._extract_parameters(
            query,
            '{"date": "YYYY-MM-DD", "surge_ratio": 5.0}',
            "질문에 날짜가 명시되어 있지 않으면 '2025-09-15' 사용, '100%' → 1.0, '200%' → 2.0, '500%' → 5.0"
        )
        date = params.get('date', '2025-09-15')
        surge_ratio = params.get('surge_ratio', 5.0)
        
        return self.technical_queries.get_volume_surge_stocks(date, surge_ratio)
    
    def _handle_cross_signals(self, query: str) -> str:
        """크로스 신호 처리"""
        params = self._extract_parameters(
            query,
            '{"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "signal_type": "golden|dead"}',
            """규칙:
- start_date: 시작날짜, 없으면 "2024-01-01" 사용
- end_date: 종료날짜, 없으면 "2024-12-31" 사용
- signal_type: "데드크로스" → "dead", "골든크로스" → "golden" """
        )
        start_date = params.get('start_date', '2024-01-01')
        end_date = params.get('end_date', '2024-12-31')
        signal_type = params.get('signal_type', 'golden')
        
        return self.technical_queries.get_cross_signals(start_date, end_date, signal_type)
    
    def _handle_cross_count(self, query: str) -> str:
        """크로스 횟수 처리"""
        params = self._extract_parameters(
            query,
            '{"ticker": "종목명", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "signal_type": "golden|dead|both"}',
            """규칙:
- ticker: 종목명을 추출, 없으면 "삼성전자" 사용
- start_date: 시작날짜, 없으면 "2024-06-01" 사용
- end_date: 종료날짜, 없으면 "2025-06-30" 사용
- signal_type: "골든크로스"만 → "golden", "데드크로스"만 → "dead", 둘다 → "both" """
        )
        ticker = params.get('ticker', '삼성전자')
        start_date = params.get('start_date', '2024-06-01')
        end_date = params.get('end_date', '2025-06-30')
        signal_type = params.get('signal_type', 'both')
        
        return self.technical_queries.count_cross_signals(ticker, start_date, end_date, signal_type)
    
    
    
    def _handle_price_change_search(self, query: str) -> str:
        """등락률 기준 검색 처리"""
        params = self._extract_parameters(
            query,
            '{"date": "YYYY-MM-DD", "ranking_type": "상승률순위|하락률순위|범위검색", "result_type": "목록순위|종목순위", "ticker": null, "limit": 5, "min_change_rate": null, "max_change_rate": null, "market": "KOSPI|KOSDAQ|null"}',
            """규칙:
- date: 질문에 날짜가 명시되어 있지 않으면 "2025-09-15" 사용
- ranking_type: "상승률 높은", "상승률순위" → "상승률순위", "하락률 높은", "하락률순위" → "하락률순위", 범위 조건 → "범위검색"
- result_type: "상위 10개", "목록" → "목록순위", "삼성전자가 몇 등", "순위" → "종목순위"
- ticker: 종목명이나 코드 추출 (종목순위일 때만 필수)
- limit: "5개", "10개" → 5, 10 (기본값 5, 목록순위일 때만)
- min_change_rate: "5% 이상", "+10% 이상" → 5.0, 10.0 (범위검색일 때만)
- max_change_rate: "-10% 이하", "5% 이하" → -10.0, 5.0 (범위검색일 때만)
- market: "KOSPI" → "KOSPI", "KOSDAQ" → "KOSDAQ", 없으면 null 사용"""
        )
        date = params.get('date', '2025-09-15')
        ranking_type = params.get('ranking_type', '범위검색')
        result_type = params.get('result_type', '목록순위')
        ticker = params.get('ticker')
        limit = params.get('limit', 50)
        min_change_rate = params.get('min_change_rate')
        max_change_rate = params.get('max_change_rate')
        market = params.get('market')
        
        return self.technical_queries.search_by_price_change_rate(date, min_change_rate, max_change_rate, market, limit, ranking_type, result_type, ticker)
    
    def _handle_volume_search(self, query: str) -> str:
        """거래량 기준 검색 처리"""
        params = self._extract_parameters(
            query,
            '{"date": "YYYY-MM-DD", "ranking_type": "거래량순위|임계값검색", "result_type": "목록순위|종목순위", "ticker": null, "limit": 10, "min_volume": null, "market": "KOSPI|KOSDAQ|null"}',
            """규칙:
- date: 질문에 날짜가 명시되어 있지 않으면 "2025-09-15" 사용
- ranking_type: "거래량 순위", "거래량 상위" → "거래량순위", "100만주 이상", "임계값" → "임계값검색"
- result_type: "상위 10개", "목록" → "목록순위", "삼성전자가 몇 등", "순위" → "종목순위"
- ticker: 종목명이나 코드 추출 (종목순위일 때만 필수)
- limit: "10개", "20개" → 10, 20 (기본값 10, 목록순위일 때만)
- min_volume: "100만주", "500만주" → 1000000, 5000000 (임계값검색일 때만)
- market: "KOSPI" → "KOSPI", "KOSDAQ" → "KOSDAQ", 없으면 null 사용"""
        )
        date = params.get('date', '2025-09-15')
        ranking_type = params.get('ranking_type', '임계값검색')
        result_type = params.get('result_type', '목록순위')
        ticker = params.get('ticker')
        limit = params.get('limit', 50)
        min_volume = params.get('min_volume')
        market = params.get('market')
        
        return self.technical_queries.search_by_volume(date, min_volume, market, limit, ranking_type, result_type, ticker)
    
    def _handle_price_search(self, query: str) -> str:
        """가격 기준 검색 처리"""
        params = self._extract_parameters(
            query,
            '{"date": "YYYY-MM-DD", "search_type": "순위검색|범위검색", "result_type": "목록순위|종목순위", "ticker": null, "price_type": "시가|고가|저가|종가", "limit": 10, "min_price": null, "max_price": null, "market": "KOSPI|KOSDAQ|null"}',
            """규칙:
- date: 질문에 날짜가 명시되어 있지 않으면 "2025-09-15" 사용
- search_type: "가장 비싼", "순위", "상위" → "순위검색", "1만원~5만원", "범위", "이상", "이하" → "범위검색"
- result_type: "상위 10개", "목록" → "목록순위", "삼성전자가 몇 등", "순위" → "종목순위"
- ticker: 종목명이나 코드 추출 (종목순위일 때만 필수)
- price_type: "시가" → "시가", "고가" → "고가", "저가" → "저가", "종가" → "종가" (기본값: 종가)
- limit: "10개", "20개" → 10, 20 (기본값 10, 목록순위일 때만)
- min_price: "1만원", "5만원" → 10000, 50000 (범위검색일 때만)
- max_price: "10만원", "50만원" → 100000, 500000 (범위검색일 때만)
- market: "KOSPI" → "KOSPI", "KOSDAQ" → "KOSDAQ", 없으면 null 사용"""
        )
        date = params.get('date', '2025-09-15')
        search_type = params.get('search_type', '범위검색')
        result_type = params.get('result_type', '목록순위')
        ticker = params.get('ticker')
        price_type = params.get('price_type', '종가')
        limit = params.get('limit', 50)
        min_price = params.get('min_price')
        max_price = params.get('max_price')
        market = params.get('market')
        
        return self.technical_queries.search_by_price(date, min_price, max_price, market, limit, search_type, price_type, result_type, ticker)
    
    def _handle_compound_search(self, query: str) -> str:
        """복합조건 검색 처리"""
        params = self._extract_parameters(
            query,
            '{"date": "YYYY-MM-DD", "market": "KOSPI|KOSDAQ|null", "limit": 10, "price_min": null, "price_max": null, "change_rate_min": null, "change_rate_max": null, "volume_min": null, "rsi_min": null, "rsi_max": null}',
            """규칙:
- date: 질문에 날짜가 명시되어 있지 않으면 "2025-09-15" 사용
- market: "KOSPI" → "KOSPI", "KOSDAQ" → "KOSDAQ", 없으면 null 사용
- limit: "10개", "20개" → 10, 20 (기본값 10)
- price_min: "1만원 이상" → 10000 (가격 최소값)
- price_max: "5만원 이하" → 50000 (가격 최대값)
- change_rate_min: "+3% 이상" → 3.0 (등락률 최소값)
- change_rate_max: "+10% 이하" → 10.0 (등락률 최대값)
- volume_min: "100만주 이상" → 1000000 (거래량 최소값)
- rsi_min: "RSI 70 이상" → 70.0 (RSI 최소값)
- rsi_max: "RSI 30 이하" → 30.0 (RSI 최대값)"""
        )
        
        date = params.get('date', '2025-09-15')
        market = params.get('market')
        limit = params.get('limit', 50)
        price_min = params.get('price_min')
        price_max = params.get('price_max')
        change_rate_min = params.get('change_rate_min')
        change_rate_max = params.get('change_rate_max')
        volume_min = params.get('volume_min')
        rsi_min = params.get('rsi_min')
        rsi_max = params.get('rsi_max')
        
        return self.technical_queries.search_compound(
            date=date,
            market=market,
            limit=limit,
            price_min=price_min,
            price_max=price_max,
            change_rate_min=change_rate_min,
            change_rate_max=change_rate_max,
            volume_min=volume_min,
            rsi_min=rsi_min,
            rsi_max=rsi_max
        )
    
    def _handle_text2sql(self, query: str) -> str:
        """TEXT2SQL 더미 핸들러 - 실제 처리는 별도 노드에서 수행"""
        return f"TEXT2SQL 쿼리가 별도 노드에서 처리됩니다: {query}"
