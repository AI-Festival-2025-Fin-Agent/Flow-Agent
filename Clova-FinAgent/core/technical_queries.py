"""
기술적 쿼리 핵심 모듈
RSI, 볼린저 밴드, 이동평균, 거래량 분석 등 모든 기술적 지표 쿼리를 통합
"""

import pandas as pd
import logging
from typing import Dict, List, Any, Optional
from .database_manager import DatabaseManager


class TechnicalQueries:
    """기술적 쿼리 처리 및 시그널 감지"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
    
    def get_rsi_signals(self, date: str, rsi_min: float = None, rsi_max: float = None, limit: int = 30) -> str:
        """RSI 기반 신호 감지"""
        try:
            self.logger.info(f"RSI 신호 감지 - date: {date}, rsi_min: {rsi_min}, rsi_max: {rsi_max}")
            
            df = self.db_manager.search_rsi_stocks(date, rsi_min=rsi_min, rsi_max=rsi_max, limit=limit)
            
            # 조건 텍스트 생성
            if rsi_min and rsi_max:
                condition_text = f"RSI {rsi_min} 이상 {rsi_max} 이하"
            elif rsi_min:
                condition_text = f"RSI {rsi_min} 이상"
            elif rsi_max:
                condition_text = f"RSI {rsi_max} 이하"
            else:
                condition_text = "RSI 조건"
            
            if df.empty:
                return f"{date}에 {condition_text} 종목을 찾을 수 없습니다."
            
            # 종목명 매핑
            result_list = []
            for _, row in df.iterrows():
                ticker = row['ticker']
                rsi_value = row['rsi']
                
                company_df = self.db_manager.get_company_info(ticker=ticker)
                stock_name = company_df.iloc[0]['stock_name'] if not company_df.empty else ticker
                
                result_list.append(f"{stock_name}(RSI:{rsi_value:.1f})")
            
            result = f"{date} {condition_text} 종목: {', '.join(result_list)}"
            return result
            
        except Exception as e:
            self.logger.error(f"RSI 검색 중 오류: {str(e)}")
            return f"RSI 검색 중 오류 발생: {str(e)}"
    
    def get_bollinger_signals(self, date: str, band_type: str = "upper", limit: int = 30) -> str:
        """볼린저 밴드 터치 종목 검색"""
        try:
            self.logger.info(f"볼린저 밴드 신호 - date: {date}, band: {band_type}")
            
            df = self.db_manager.search_bollinger_touch_stocks(date, band_type, limit)
            
            if df.empty:
                band_korean = "상단" if band_type == "upper" else "하단"
                return f"{date}에 볼린저 밴드 {band_korean}에 터치한 종목을 찾을 수 없습니다."
            
            # 종목명 매핑
            result_list = []
            for _, row in df.iterrows():
                ticker = row['ticker']
                company_df = self.db_manager.get_company_info(ticker=ticker)
                stock_name = company_df.iloc[0]['stock_name'] if not company_df.empty else ticker
                result_list.append(stock_name)
            
            band_korean = "상단" if band_type == "upper" else "하단"
            result = f"{date} 볼린저 밴드 {band_korean} 터치 종목: {', '.join(result_list)}"
            return result
            
        except Exception as e:
            self.logger.error(f"볼린저 밴드 검색 중 오류: {str(e)}")
            return f"볼린저 밴드 검색 중 오류 발생: {str(e)}"
    
    def get_ma_breakout_stocks(self, date: str, ma_period: int = 20, breakout_ratio: float = 0.03, limit: int = 30) -> str:
        """이동평균선 돌파 종목 검색"""
        try:
            self.logger.info(f"이동평균 돌파 - date: {date}, MA{ma_period}, ratio: {breakout_ratio}")
            
            df = self.db_manager.search_ma_breakout_stocks(date, ma_period, breakout_ratio, limit)
            
            if df.empty:
                return f"{date}에 {ma_period}일 이동평균을 {breakout_ratio*100:.0f}% 이상 돌파한 종목을 찾을 수 없습니다."
            
            # 종목명과 돌파율 매핑
            result_list = []
            for _, row in df.iterrows():
                ticker = row['ticker']
                breakout_pct = row.get('breakout_ratio', 0) * 100
                
                company_df = self.db_manager.get_company_info(ticker=ticker)
                stock_name = company_df.iloc[0]['stock_name'] if not company_df.empty else ticker
                result_list.append(f"{stock_name}({breakout_pct:.2f}%)")
            
            result = f"{date} {ma_period}일 이동평균 {breakout_ratio*100:.0f}% 이상 돌파: {', '.join(result_list)}"
            return result
            
        except Exception as e:
            self.logger.error(f"MA 돌파 검색 중 오류: {str(e)}")
            return f"이동평균 돌파 검색 중 오류 발생: {str(e)}"
    
    def get_volume_surge_stocks(self, date: str, surge_ratio: float = 5.0, limit: int = 50) -> str:
        """거래량 급증 종목 검색"""
        try:
            self.logger.info(f"거래량 급증 검색 - date: {date}, ratio: {surge_ratio}")
            
            df = self.db_manager.search_volume_surge_stocks(date, surge_ratio, limit)
            
            if df.empty:
                return f"{date}에 거래량이 20일 평균 대비 {surge_ratio*100:.0f}% 이상 급증한 종목을 찾을 수 없습니다."
            
            # 종목명과 급증률 매핑
            result_list = []
            for _, row in df.iterrows():
                ticker = row['ticker']
                volume_ratio = row.get('volume_ratio', 0) * 100
                
                company_df = self.db_manager.get_company_info(ticker=ticker)
                stock_name = company_df.iloc[0]['stock_name'] if not company_df.empty else ticker
                result_list.append(f"{stock_name}({volume_ratio:.0f}%)")
            
            result = f"{date} 거래량 20일 평균 대비 {surge_ratio*100:.0f}% 이상 급증: {', '.join(result_list)}"
            return result
            
        except Exception as e:
            self.logger.error(f"거래량 급증 검색 중 오류: {str(e)}")
            return f"거래량 급증 검색 중 오류 발생: {str(e)}"
    
    def get_cross_signals(self, start_date: str, end_date: str, signal_type: str = "golden", limit: int = 20) -> str:
        """골든크로스/데드크로스 발생 종목 검색"""
        try:
            self.logger.info(f"크로스 신호 검색 - {start_date}~{end_date}, type: {signal_type}")
            
            df = self.db_manager.search_cross_signals(start_date, end_date, signal_type)
            
            if df.empty:
                signal_korean = "골든크로스" if signal_type == "golden" else "데드크로스"
                return f"{start_date}부터 {end_date}까지 {signal_korean}가 발생한 종목을 찾을 수 없습니다."
            
            # 종목명 매핑 (중복 제거)
            unique_tickers = df['ticker'].unique()[:limit]
            result_list = []
            
            for ticker in unique_tickers:
                company_df = self.db_manager.get_company_info(ticker=ticker)
                stock_name = company_df.iloc[0]['stock_name'] if not company_df.empty else ticker
                result_list.append(stock_name)
            
            signal_korean = "골든크로스" if signal_type == "golden" else "데드크로스"
            result = f"{start_date}부터 {end_date}까지 {signal_korean} 발생 종목: {', '.join(result_list)}"
            return result
            
        except Exception as e:
            self.logger.error(f"크로스 신호 검색 중 오류: {str(e)}")
            return f"크로스 신호 검색 중 오류 발생: {str(e)}"
    
    def count_cross_signals(self, ticker: str, start_date: str, end_date: str, signal_type: str = "both") -> str:
        """특정 종목의 크로스 신호 발생 횟수 계산"""
        try:
            self.logger.info(f"크로스 횟수 계산 - ticker: {ticker}, {start_date}~{end_date}")
            
            # 종목명을 티커로 변환
            if not ticker.isdigit() and '.' not in ticker:
                company_df = self.db_manager.get_company_info(stock_name=ticker)
                if not company_df.empty:
                    original_name = ticker
                    ticker = company_df.iloc[0]['ticker']
            
            if signal_type == "both":
                golden_count = self.db_manager.count_cross_signals(ticker, start_date, end_date, "golden")
                dead_count = self.db_manager.count_cross_signals(ticker, start_date, end_date, "dead")
                
                result = f"데드크로스 {dead_count}번, 골든크로스 {golden_count}번"
            elif signal_type == "golden":
                count = self.db_manager.count_cross_signals(ticker, start_date, end_date, "golden")
                result = f"{count}번"
            else:  # dead
                count = self.db_manager.count_cross_signals(ticker, start_date, end_date, "dead")
                result = f"{count}번"
            
            return result
            
        except Exception as e:
            self.logger.error(f"크로스 횟수 계산 중 오류: {str(e)}")
            return f"크로스 횟수 계산 중 오류 발생: {str(e)}"
    
    def search_by_price_range(self, date: str, min_price: float, max_price: float, market: str = None, limit: int = 50) -> str:
        """가격 범위별 종목 검색"""
        try:
            self.logger.info(f"가격 범위 검색 - date: {date}, {min_price}~{max_price}원")
            
            import sqlite3
            conn = sqlite3.connect(self.db_manager.stock_db_path)
            
            # 시장 필터 조건 추가
            market_condition = ""
            params = [date, min_price, max_price]
            
            if market == "KOSPI":
                market_condition = "AND ticker LIKE '%.KS'"
            elif market == "KOSDAQ":
                market_condition = "AND ticker LIKE '%.KQ'"
            
            query = f"""
            SELECT sp.ticker, sp.stock_name, sp.close_price, sp.market
            FROM stock_prices sp
            WHERE sp.trading_date = ? 
            AND sp.close_price BETWEEN ? AND ?
            {market_condition}
            ORDER BY sp.close_price DESC
            LIMIT {limit}
            """
            
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            
            if df.empty:
                market_text = f"{market} " if market else ""
                return f"{date}에 {market_text}종가가 {min_price:,.0f}원 이상 {max_price:,.0f}원 이하인 종목을 찾을 수 없습니다."
            
            result_list = []
            for _, row in df.iterrows():
                stock_name = row['stock_name']
                result_list.append(stock_name)
            
            market_text = f"{market} 시장에서 " if market else ""
            result = f"{date} {market_text}종가가 {min_price:,.0f}원 이상 {max_price:,.0f}원 이하인 종목: {', '.join(result_list)}"
            return result
            
        except Exception as e:
            self.logger.error(f"가격 범위 검색 중 오류: {str(e)}")
            return f"가격 범위 검색 중 오류 발생: {str(e)}"
    
    def search_by_price(self, date: str, min_price: float = None, max_price: float = None, market: str = None, 
                       limit: int = 50, search_type: str = '범위검색', price_type: str = '종가', result_type: str = '목록순위', ticker: str = None) -> str:
        """가격 기준 종목 검색 (순위 또는 범위 검색)"""
        try:
            self.logger.info(f"가격 기준 검색 - date: {date}, type: {search_type}, price_type: {price_type}")
            
            import sqlite3
            conn = sqlite3.connect(self.db_manager.stock_db_path)
            
            # 가격 컬럼 매핑
            price_column_map = {
                '시가': 'open_price',
                '고가': 'high_price', 
                '저가': 'low_price',
                '종가': 'close_price'
            }
            price_column = price_column_map.get(price_type, 'close_price')
            
            # 시장 필터 조건
            market_condition = ""
            if market == "KOSPI":
                market_condition = "AND ticker LIKE '%.KS'"
            elif market == "KOSDAQ":
                market_condition = "AND ticker LIKE '%.KQ'"
            
            if search_type == '순위검색':
                # 종목순위: 특정 종목의 가격 순위 조회
                if result_type == '종목순위' and ticker:
                    # 종목명을 티커로 변환
                    if not ticker.isdigit() and '.' not in ticker:
                        company_df = self.db_manager.get_company_info(stock_name=ticker)
                        if not company_df.empty:
                            ticker_code = company_df.iloc[0]['ticker']
                        else:
                            return f"'{ticker}' 종목을 찾을 수 없습니다."
                    else:
                        ticker_code = ticker
                    
                    # 해당 종목보다 높은 가격 종목 수 + 1 = 순위 (높은 가격 순)
                    rank_query = f"""
                    SELECT COUNT(*) + 1 as ranking,
                           (SELECT {price_column} FROM stock_prices 
                            WHERE trading_date = ? AND ticker = ? {market_condition.replace('AND ticker', 'AND t.ticker')}) as target_price
                    FROM stock_prices
                    WHERE trading_date = ? {market_condition}
                    AND {price_column} > (SELECT {price_column} FROM stock_prices 
                                         WHERE trading_date = ? AND ticker = ?)
                    """
                    
                    params = [date, ticker_code, date, date, ticker_code]
                    rank_df = pd.read_sql_query(rank_query, conn, params=params)
                    
                    if rank_df.empty or rank_df.iloc[0]['target_price'] is None:
                        return f"{date}에 '{ticker}' 종목의 데이터를 찾을 수 없습니다."
                    
                    ranking = rank_df.iloc[0]['ranking']
                    target_price = rank_df.iloc[0]['target_price']
                    
                    market_text = f"{market} 시장에서 " if market else ""
                    result = f"{date} {market_text}{ticker}의 {price_type} 순위: {ranking}위 ({target_price:,.0f}원)"
                
                else:  # 목록순위: 상위 N개 목록
                    # 순위 검색: 가격 높은 순/낮은 순
                    order_by = "DESC"  # 기본적으로 높은 가격 순
                    
                    query = f"""
                    SELECT ticker, stock_name, {price_column}, market
                    FROM stock_prices
                    WHERE trading_date = ? {market_condition}
                    ORDER BY {price_column} {order_by}
                    LIMIT {limit}
                    """
                    
                    df = pd.read_sql_query(query, conn, params=[date])
                    
                    if df.empty:
                        market_text = f"{market} " if market else ""
                        return f"{date}에 {market_text}{price_type} 데이터를 찾을 수 없습니다."
                    
                    result_list = []
                    for _, row in df.iterrows():
                        stock_name = row['stock_name']
                        price = row[price_column]
                        result_list.append(f"{stock_name}({price:,.0f}원)")
                    
                    market_text = f"{market} " if market else ""
                    result = f"{date} {market_text}{price_type} 상위 {limit}개: {', '.join(result_list)}"
                
            else:  # 범위검색
                # 범위 검색: min_price ~ max_price
                conditions = ["trading_date = ?"]
                params = [date]
                
                if min_price is not None:
                    conditions.append(f"{price_column} >= ?")
                    params.append(min_price)
                    
                if max_price is not None:
                    conditions.append(f"{price_column} <= ?") 
                    params.append(max_price)
                
                if market_condition:
                    conditions.append(market_condition.replace("AND ", ""))
                
                
                where_clause = " AND ".join(conditions)
                
                query = f"""
                SELECT ticker, stock_name, {price_column}, market
                FROM stock_prices
                WHERE {where_clause}
                ORDER BY {price_column} DESC
                LIMIT {limit}
                """
                
                df = pd.read_sql_query(query, conn, params=params)
                
                if df.empty:
                    # 조건 텍스트 생성
                    if min_price is not None and max_price is not None:
                        condition_text = f"{price_type}가 {min_price:,.0f}원 이상 {max_price:,.0f}원 이하"
                    elif min_price is not None:
                        condition_text = f"{price_type}가 {min_price:,.0f}원 이상"
                    elif max_price is not None:
                        condition_text = f"{price_type}가 {max_price:,.0f}원 이하"
                    else:
                        condition_text = f"{price_type} 조건"
                    
                    market_text = f"{market} " if market else ""
                    return f"{date}에 {market_text}{condition_text}인 종목을 찾을 수 없습니다."
                
                result_list = []
                for _, row in df.iterrows():
                    stock_name = row['stock_name']
                    price = row[price_column]
                    result_list.append(f"{stock_name}({price:,.0f}원)")
                
                # 조건 텍스트 생성
                if min_price is not None and max_price is not None:
                    condition_text = f"{price_type} {min_price:,.0f}원 이상 {max_price:,.0f}원 이하"
                elif min_price is not None:
                    condition_text = f"{price_type} {min_price:,.0f}원 이상"
                elif max_price is not None:
                    condition_text = f"{price_type} {max_price:,.0f}원 이하"
                else:
                    condition_text = f"{price_type} 조건"
                
                market_text = f"{market} 시장에서 " if market else ""
                result = f"{date} {market_text}{condition_text} 종목: {', '.join(result_list)}"
            
            conn.close()
            return result
            
        except Exception as e:
            self.logger.error(f"가격 기준 검색 중 오류: {str(e)}")
            return f"가격 기준 검색 중 오류 발생: {str(e)}"
    
    def search_compound(self, date: str, market: str = None, limit: int = 100, 
                       price_min: float = None, price_max: float = None,
                       change_rate_min: float = None, change_rate_max: float = None,
                       volume_min: int = None, rsi_min: float = None, rsi_max: float = None) -> str:
        """복합조건 검색 - 하나의 SQL 쿼리로 처리"""
        try:
            self.logger.info(f"복합조건 검색 - date: {date}, 조건 수: {sum(1 for x in [price_min, price_max, change_rate_min, change_rate_max, volume_min, rsi_min, rsi_max] if x is not None)}")
            
            import sqlite3
            conn = sqlite3.connect(self.db_manager.stock_db_path)
            
            # 기본 조건
            conditions = ["sp.trading_date = ?"]
            params = [date]
            
            # 가격 조건
            if price_min is not None:
                conditions.append("sp.close_price >= ?")
                params.append(price_min)
            
            if price_max is not None:
                conditions.append("sp.close_price <= ?")
                params.append(price_max)
            
            # 등락률 조건
            if change_rate_min is not None:
                conditions.append("sp.change_rate >= ?")
                params.append(change_rate_min)
            
            if change_rate_max is not None:
                conditions.append("sp.change_rate <= ?")
                params.append(change_rate_max)
            
            # 거래량 조건
            if volume_min is not None:
                conditions.append("sp.trading_volume >= ?")
                params.append(volume_min)
            
            # 시장 필터
            if market == "KOSPI":
                conditions.append("sp.ticker LIKE '%.KS'")
            elif market == "KOSDAQ":
                conditions.append("sp.ticker LIKE '%.KQ'")
            
            # RSI 조건이 있는 경우 technical_indicators 테이블 조인
            if rsi_min is not None or rsi_max is not None:
                # RSI 조건 추가
                if rsi_min is not None:
                    conditions.append("ti.rsi >= ?")
                    params.append(rsi_min)
                
                if rsi_max is not None:
                    conditions.append("ti.rsi <= ?")
                    params.append(rsi_max)
                
                # RSI 포함 쿼리
                where_clause = " AND ".join(conditions)
                query = f"""
                SELECT sp.ticker, sp.stock_name, sp.close_price, sp.change_rate, sp.trading_volume, ti.rsi
                FROM stock_prices sp
                JOIN technical_indicators ti ON sp.ticker = ti.ticker AND sp.trading_date = ti.date
                WHERE {where_clause}
                ORDER BY sp.change_rate DESC
                LIMIT {limit}
                """
            else:
                # 일반 쿼리 (RSI 없음)
                where_clause = " AND ".join(conditions)
                query = f"""
                SELECT sp.ticker, sp.stock_name, sp.close_price, sp.change_rate, sp.trading_volume
                FROM stock_prices sp
                WHERE {where_clause}
                ORDER BY sp.change_rate DESC
                LIMIT {limit}
                """
            
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            
            if df.empty:
                # 조건 텍스트 생성
                conditions_text = []
                if price_min is not None:
                    conditions_text.append(f"가격 {price_min:,.0f}원 이상")
                if price_max is not None:
                    conditions_text.append(f"가격 {price_max:,.0f}원 이하")
                if change_rate_min is not None:
                    conditions_text.append(f"등락률 {change_rate_min:+.1f}% 이상")
                if change_rate_max is not None:
                    conditions_text.append(f"등락률 {change_rate_max:+.1f}% 이하")
                if volume_min is not None:
                    conditions_text.append(f"거래량 {volume_min:,}주 이상")
                if rsi_min is not None:
                    conditions_text.append(f"RSI {rsi_min:.0f} 이상")
                if rsi_max is not None:
                    conditions_text.append(f"RSI {rsi_max:.0f} 이하")
                
                condition_str = ", ".join(conditions_text) if conditions_text else "조건"
                market_text = f"{market} " if market else ""
                return f"{date}에 {market_text}{condition_str}을/를 모두 만족하는 종목을 찾을 수 없습니다."
            
            # 결과 생성 (토큰 제한 고려)
            total_count = len(df)
            display_limit = min(25, total_count)  # 복합조건은 더 자세하므로 25개로 제한
            
            result_list = []
            for _, row in df.head(display_limit).iterrows():
                stock_name = row['stock_name']
                price = row['close_price']
                change_rate = row['change_rate']
                volume = row['trading_volume']
                
                if 'rsi' in row.index:
                    rsi = row['rsi']
                    result_list.append(f"{stock_name}(종가:{price:,.0f}원, 등락률:{change_rate:+.2f}%, 거래량:{volume:,}주, RSI:{rsi:.1f})")
                else:
                    result_list.append(f"{stock_name}(종가:{price:,.0f}원, 등락률:{change_rate:+.2f}%, 거래량:{volume:,}주)")
            
            # 조건 요약
            conditions_text = []
            if price_min is not None:
                conditions_text.append(f"가격 {price_min:,.0f}원 이상")
            if price_max is not None:
                conditions_text.append(f"가격 {price_max:,.0f}원 이하")
            if change_rate_min is not None:
                conditions_text.append(f"등락률 {change_rate_min:+.1f}% 이상")
            if change_rate_max is not None:
                conditions_text.append(f"등락률 {change_rate_max:+.1f}% 이하")
            if volume_min is not None:
                conditions_text.append(f"거래량 {volume_min:,}주 이상")
            if rsi_min is not None:
                conditions_text.append(f"RSI {rsi_min:.0f} 이상")
            if rsi_max is not None:
                conditions_text.append(f"RSI {rsi_max:.0f} 이하")
            
            condition_str = ", ".join(conditions_text) if conditions_text else "복합조건"
            market_text = f"{market} " if market else ""
            
            if total_count > display_limit:
                result = f"{date} {market_text}{condition_str}을/를 모두 만족하는 종목 (총 {total_count}개 중 {display_limit}개 표시): {', '.join(result_list)}"
            else:
                result = f"{date} {market_text}{condition_str}을/를 모두 만족하는 종목: {', '.join(result_list)}"
            return result
            
        except Exception as e:
            self.logger.error(f"복합조건 검색 중 오류: {str(e)}")
            return f"복합조건 검색 중 오류 발생: {str(e)}"
    
    def search_by_volume_threshold(self, date: str, min_volume: int, market: str = None, limit: int = 50) -> str:
        """거래량 절대값 기준 종목 검색"""
        try:
            self.logger.info(f"거래량 절대값 검색 - date: {date}, min: {min_volume:,}주")
            
            df = self.db_manager.search_stocks_by_volume(date, min_volume=min_volume, limit=limit)
            
            # 시장별 필터링
            if market and not df.empty:
                if market == "KOSPI":
                    df = df[df['ticker'].str.endswith('.KS')]
                elif market == "KOSDAQ":
                    df = df[df['ticker'].str.endswith('.KQ')]
            
            if df.empty:
                market_text = f"{market} " if market else ""
                return f"{date}에 {market_text}거래량이 {min_volume:,}주 이상인 종목을 찾을 수 없습니다."
            
            # 종목명 매핑
            result_list = []
            for _, row in df.iterrows():
                ticker = row['ticker']
                company_df = self.db_manager.get_company_info(ticker=ticker)
                stock_name = company_df.iloc[0]['stock_name'] if not company_df.empty else ticker
                result_list.append(stock_name)
            
            market_text = f"{market} 시장에서 " if market else ""
            result = f"{date} {market_text}거래량이 {min_volume:,}주 이상인 종목: {', '.join(result_list)}"
            return result
            
        except Exception as e:
            self.logger.error(f"거래량 절대값 검색 중 오류: {str(e)}")
            return f"거래량 절대값 검색 중 오류 발생: {str(e)}"
    
    def search_by_volume(self, date: str, min_volume: int = None, market: str = None, limit: int = 50, ranking_type: str = '임계값검색', result_type: str = '목록순위', ticker: str = None) -> str:
        """거래량 기준 종목 검색 (순위 또는 임계값 검색)"""
        try:
            self.logger.info(f"거래량 기준 검색 - date: {date}, type: {ranking_type}, limit: {limit}")
            
            # 순위 검색 모드인 경우
            if ranking_type == '거래량순위':
                import sqlite3
                conn = sqlite3.connect(self.db_manager.stock_db_path)
                
                # 시장 필터 조건
                market_condition = ""
                if market == "KOSPI":
                    market_condition = "AND ticker LIKE '%.KS'"
                elif market == "KOSDAQ":
                    market_condition = "AND ticker LIKE '%.KQ'"
                
                # 종목순위: 특정 종목의 거래량 순위 조회
                if result_type == '종목순위' and ticker:
                    # 종목명을 티커로 변환
                    if not ticker.isdigit() and '.' not in ticker:
                        company_df = self.db_manager.get_company_info(stock_name=ticker)
                        if not company_df.empty:
                            ticker_code = company_df.iloc[0]['ticker']
                        else:
                            return f"'{ticker}' 종목을 찾을 수 없습니다."
                    else:
                        ticker_code = ticker
                    
                    # 해당 종목보다 높은 거래량 종목 수 + 1 = 순위
                    rank_query = f"""
                    SELECT COUNT(*) + 1 as ranking,
                           (SELECT trading_volume FROM stock_prices 
                            WHERE trading_date = ? AND ticker = ? {market_condition.replace('AND ticker', 'AND t.ticker')}) as target_volume
                    FROM stock_prices
                    WHERE trading_date = ? {market_condition}
                    AND trading_volume > (SELECT trading_volume FROM stock_prices 
                                         WHERE trading_date = ? AND ticker = ?)
                    """
                    
                    params = [date, ticker_code, date, date, ticker_code]
                    rank_df = pd.read_sql_query(rank_query, conn, params=params)
                    
                    if rank_df.empty or rank_df.iloc[0]['target_volume'] is None:
                        return f"{date}에 '{ticker}' 종목의 데이터를 찾을 수 없습니다."
                    
                    ranking = rank_df.iloc[0]['ranking']
                    target_volume = rank_df.iloc[0]['target_volume']
                    
                    market_text = f"{market} 시장에서 " if market else ""
                    conn.close()
                    return f"{date} {market_text}{ticker}의 거래량 순위: {ranking}위 ({target_volume:,}주)"
                
                else:  # 목록순위: 상위 N개 목록
                    # basic_queries의 get_volume_ranking 로직 사용
                    df = self.db_manager.search_top_volume_stocks(date, market, limit)
                    conn.close()
                    
                    if df.empty:
                        market_text = f"{market} " if market else ""
                        return f"{date}에 {market_text}거래량 데이터를 찾을 수 없습니다."
                    
                    total_count = len(df)
                    display_limit = min(30, total_count)
                    
                    result_list = []
                    for _, row in df.head(display_limit).iterrows():
                        stock_name = row['stock_name']
                        volume = row['trading_volume']
                        result_list.append(f"{stock_name}({volume:,}주)")
                    
                    market_text = f"{market} " if market else ""
                    if total_count > display_limit:
                        result = f"{date} {market_text}거래량 상위 종목 (총 {total_count}개 중 {display_limit}개 표시): {', '.join(result_list)}"
                    else:
                        result = f"{date} {market_text}거래량 상위 {total_count}개: {', '.join(result_list)}"
                    return result
            
            else:  # 임계값검색
                # 기존 search_by_volume_threshold 로직 사용
                df = self.db_manager.search_stocks_by_volume(date, min_volume=min_volume, limit=limit)
                
                # 시장별 필터링
                if market and not df.empty:
                    if market == "KOSPI":
                        df = df[df['ticker'].str.endswith('.KS')]
                    elif market == "KOSDAQ":
                        df = df[df['ticker'].str.endswith('.KQ')]
                
                if df.empty:
                    market_text = f"{market} " if market else ""
                    return f"{date}에 {market_text}거래량이 {min_volume:,}주 이상인 종목을 찾을 수 없습니다."
                
                # 종목명 매핑 (토큰 제한 고려)
                total_count = len(df)
                display_limit = min(30, total_count)
                
                result_list = []
                for _, row in df.head(display_limit).iterrows():
                    ticker = row['ticker']
                    company_df = self.db_manager.get_company_info(ticker=ticker)
                    stock_name = company_df.iloc[0]['stock_name'] if not company_df.empty else ticker
                    result_list.append(stock_name)
                
                market_text = f"{market} 시장에서 " if market else ""
                if total_count > display_limit:
                    result = f"{date} {market_text}거래량이 {min_volume:,}주 이상인 종목 (총 {total_count}개 중 {display_limit}개 표시): {', '.join(result_list)}"
                else:
                    result = f"{date} {market_text}거래량이 {min_volume:,}주 이상인 종목: {', '.join(result_list)}"
                return result
            
        except Exception as e:
            self.logger.error(f"거래량 기준 검색 중 오류: {str(e)}")
            return f"거래량 기준 검색 중 오류 발생: {str(e)}"
    
    def search_by_price_change_rate(self, date: str, min_change_rate: float = None, max_change_rate: float = None, market: str = None, limit: int = 50, ranking_type: str = '범위검색', result_type: str = '목록순위', ticker: str = None) -> str:
        """등락률 기준 종목 검색 (순위 또는 범위 검색)"""
        try:
            self.logger.info(f"등락률 기준 검색 - date: {date}, type: {ranking_type}, limit: {limit}")
            
            import sqlite3
            conn = sqlite3.connect(self.db_manager.stock_db_path)
            
            # 순위 방식인 경우
            if ranking_type in ['상승률순위', '하락률순위']:
                # 시장 필터 조건
                market_condition = ""
                if market == "KOSPI":
                    market_condition = "AND ticker LIKE '%.KS'"
                elif market == "KOSDAQ":
                    market_condition = "AND ticker LIKE '%.KQ'"
                
                # 종목순위: 특정 종목의 순위 조회
                if result_type == '종목순위' and ticker:
                    # 종목명을 티커로 변환
                    if not ticker.isdigit() and '.' not in ticker:
                        company_df = self.db_manager.get_company_info(stock_name=ticker)
                        if not company_df.empty:
                            ticker_code = company_df.iloc[0]['ticker']
                        else:
                            return f"'{ticker}' 종목을 찾을 수 없습니다."
                    else:
                        ticker_code = ticker
                    
                    # 상승률순위: 해당 종목보다 높은 등락률 종목 수 + 1
                    # 하락률순위: 해당 종목보다 낮은 등락률 종목 수 + 1
                    if ranking_type == '상승률순위':
                        rank_query = f"""
                        SELECT COUNT(*) + 1 as ranking,
                               (SELECT change_rate FROM stock_prices 
                                WHERE trading_date = ? AND ticker = ? {market_condition.replace('AND ticker', 'AND t.ticker')}) as target_rate
                        FROM stock_prices
                        WHERE trading_date = ? {market_condition}
                        AND change_rate > (SELECT change_rate FROM stock_prices 
                                          WHERE trading_date = ? AND ticker = ?)
                        """
                    else:  # 하락률순위
                        rank_query = f"""
                        SELECT COUNT(*) + 1 as ranking,
                               (SELECT change_rate FROM stock_prices 
                                WHERE trading_date = ? AND ticker = ? {market_condition.replace('AND ticker', 'AND t.ticker')}) as target_rate
                        FROM stock_prices
                        WHERE trading_date = ? {market_condition}
                        AND change_rate < (SELECT change_rate FROM stock_prices 
                                          WHERE trading_date = ? AND ticker = ?)
                        """
                    
                    params = [date, ticker_code, date, date, ticker_code]
                    rank_df = pd.read_sql_query(rank_query, conn, params=params)
                    
                    if rank_df.empty or rank_df.iloc[0]['target_rate'] is None:
                        return f"{date}에 '{ticker}' 종목의 데이터를 찾을 수 없습니다."
                    
                    ranking = rank_df.iloc[0]['ranking']
                    target_rate = rank_df.iloc[0]['target_rate']
                    
                    market_text = f"{market} 시장에서 " if market else ""
                    rank_text = "상승률" if ranking_type == '상승률순위' else "하락률"
                    
                    return f"{date} {market_text}{ticker}의 {rank_text} 순위: {ranking}위 ({target_rate:+.2f}%)"
                
                else:  # 목록순위: 상위 N개 목록
                    # 상승률순위: change_rate DESC (높은 순)
                    # 하락률순위: change_rate ASC (낮은 순, 즉 마이너스 값이 더 큰 순)
                    order_by = "DESC" if ranking_type == '상승률순위' else "ASC"
                    
                    query = f"""
                    SELECT ticker, stock_name, close_price, change_rate, trading_volume, market
                    FROM stock_prices
                    WHERE trading_date = ? {market_condition}
                    ORDER BY change_rate {order_by}
                    LIMIT {limit}
                    """
                    
                    df = pd.read_sql_query(query, conn, params=[date])
            
            else:  # 범위검색
                # 기존 방식 유지
                conditions = ["trading_date = ?"]
                params = [date]
                
                if min_change_rate is not None:
                    conditions.append("change_rate >= ?")
                    params.append(min_change_rate)
                
                if max_change_rate is not None:
                    conditions.append("change_rate <= ?")
                    params.append(max_change_rate)
                
                # 시장 필터
                if market == "KOSPI":
                    conditions.append("ticker LIKE '%.KS'")
                elif market == "KOSDAQ":
                    conditions.append("ticker LIKE '%.KQ'")
                
                
                where_clause = " AND ".join(conditions)
                
                query = f"""
                SELECT ticker, stock_name, close_price, change_rate, trading_volume, market
                FROM stock_prices
                WHERE {where_clause}
                ORDER BY change_rate DESC
                LIMIT {limit}
                """
                
                df = pd.read_sql_query(query, conn, params=params)
            
            conn.close()
            
            if df.empty:
                if ranking_type == '상승률순위':
                    condition_text = f"상승률 순위 {limit}개"
                elif ranking_type == '하락률순위':
                    condition_text = f"하락률 순위 {limit}개"
                else:
                    # 범위검색 조건 텍스트 생성
                    if min_change_rate is not None and max_change_rate is not None:
                        condition_text = f"등락률이 {min_change_rate:+.1f}% 이상 {max_change_rate:+.1f}% 이하"
                    elif min_change_rate is not None:
                        condition_text = f"등락률이 {min_change_rate:+.1f}% 이상"
                    elif max_change_rate is not None:
                        condition_text = f"등락률이 {max_change_rate:+.1f}% 이하"
                    else:
                        condition_text = "등락률 조건"
                
                market_text = f" {market} 시장에서" if market else ""
                return f"{date}에{market_text} {condition_text}인 종목을 찾을 수 없습니다."
            
            # 결과 생성 (토큰 제한 고려)
            total_count = len(df)
            display_limit = min(30, total_count)  # 최대 30개까지만 표시
            
            # 간단한 종목명만 나열 (토큰 절약)
            result_list = []
            for _, row in df.head(display_limit).iterrows():
                stock_name = row['stock_name']
                result_list.append(stock_name)
            
            # 조건 텍스트 생성
            if ranking_type == '상승률순위':
                condition_text = f"상승률 순위"
            elif ranking_type == '하락률순위':
                condition_text = f"하락률 순위"
            else:
                if min_change_rate is not None and max_change_rate is not None:
                    condition_text = f"등락률 {min_change_rate:+.1f}% 이상 {max_change_rate:+.1f}% 이하"
                elif min_change_rate is not None:
                    condition_text = f"등락률 {min_change_rate:+.1f}% 이상"
                elif max_change_rate is not None:
                    condition_text = f"등락률 {max_change_rate:+.1f}% 이하"
                else:
                    condition_text = "등락률 조건"
            
            market_text = f" {market} 시장" if market else ""
            
            # 간단한 형태로 결과 반환
            if total_count > display_limit:
                result = f"{date}{market_text} {condition_text} 만족 종목 (총 {total_count}개): {', '.join(result_list)}, ...등"
            else:
                result = f"{date}{market_text} {condition_text} 만족 종목: {', '.join(result_list)}"
            
            return result
            
        except Exception as e:
            self.logger.error(f"등락률 기준 검색 중 오류: {str(e)}")
            return f"등락률 기준 검색 중 오류 발생: {str(e)}"
    
    def search_by_return_and_volume(self, date: str, min_return_rate: float, min_volume_change: float, market: str = None, limit: int = 50) -> str:
        """등락률 + 거래량 변화율 복합 조건 검색"""
        try:
            self.logger.info(f"등락률+거래량 복합 검색 - date: {date}, return: {min_return_rate}%, volume: {min_volume_change}%")
            
            # volume_ratio를 백분율에서 비율로 변환 (100% -> 1.0)
            volume_ratio = min_volume_change / 100.0
            
            # 직접 SQL 쿼리 실행 (두 DB를 별도로 접근)
            import sqlite3
            import pandas as pd
            
            # 1단계: stock_prices에서 등락률 조건 만족하는 종목 찾기
            stock_conn = sqlite3.connect(self.db_manager.stock_db_path)
            
            conditions = ["trading_date = ?", "change_rate >= ?"]
            params = [date, min_return_rate]
            
            # 시장 필터
            if market == "KOSPI":
                conditions.append("ticker LIKE '%.KS'")
            elif market == "KOSDAQ":
                conditions.append("ticker LIKE '%.KQ'")
            
            where_clause = " AND ".join(conditions)
            
            stock_query = f"""
            SELECT ticker, stock_name, close_price, change_rate, trading_volume, market
            FROM stock_prices
            WHERE {where_clause}
            ORDER BY change_rate DESC
            """
            
            stock_df = pd.read_sql_query(stock_query, stock_conn, params=params)
            stock_conn.close()
            
            if stock_df.empty:
                market_text = f" {market} 시장에서" if market else ""
                return f"{date}에{market_text} 등락률 {min_return_rate:+.1f}% 이상 종목을 찾을 수 없습니다."
            
            # 2단계: technical_indicators에서 거래량 조건 확인
            tech_conn = sqlite3.connect(self.db_manager.technical_db_path)
            
            # 등락률 조건을 만족하는 종목들의 ticker 리스트
            ticker_list = "', '".join(stock_df['ticker'].tolist())
            
            tech_query = f"""
            SELECT ticker, volume_ratio
            FROM technical_indicators
            WHERE trading_date = ? AND ticker IN ('{ticker_list}') AND volume_ratio >= ?
            """
            
            tech_df = pd.read_sql_query(tech_query, tech_conn, params=[date, volume_ratio])
            tech_conn.close()
            
            if tech_df.empty:
                market_text = f" {market} 시장에서" if market else ""
                return f"{date}에{market_text} 등락률 {min_return_rate:+.1f}% 이상이면서 거래량이 전날대비 {min_volume_change:.0f}% 이상 증가한 종목을 찾을 수 없습니다."
            
            # 3단계: 두 조건을 모두 만족하는 종목만 필터링
            merged_df = stock_df.merge(tech_df, on='ticker', how='inner')
            
            # 결과 수 제한
            if len(merged_df) > limit:
                merged_df = merged_df.head(limit)
            
            if merged_df.empty:
                market_text = f" {market} 시장에서" if market else ""
                return f"{date}에{market_text} 등락률 {min_return_rate:+.1f}% 이상이면서 거래량이 전날대비 {min_volume_change:.0f}% 이상 증가한 종목을 찾을 수 없습니다."
            
            # 결과 생성
            result_list = []
            for _, row in merged_df.iterrows():
                stock_name = row['stock_name']
                change_rate = row['change_rate']
                volume_ratio_pct = row['volume_ratio'] * 100
                result_list.append(f"{stock_name}({change_rate:+.1f}%, 거래량{volume_ratio_pct:.0f}%)")
            
            market_text = f" {market} 시장에서" if market else ""
            result = f"{date}{market_text} 등락률 {min_return_rate:+.1f}% 이상이면서 거래량 전날대비 {min_volume_change:.0f}% 이상 증가: {', '.join(result_list)}"
            return result
            
        except Exception as e:
            self.logger.error(f"등락률+거래량 복합 검색 중 오류: {str(e)}")
            return f"등락률+거래량 복합 검색 중 오류 발생: {str(e)}"