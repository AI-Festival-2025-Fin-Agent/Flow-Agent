"""
기본 쿼리 핵심 모듈
기본적인 주식 정보 조회 및 데이터 제공 기능들을 통합
"""

import pandas as pd
import logging
from typing import Dict, List, Any, Optional
from .database_manager import DatabaseManager


class BasicQueries:
    """기본 쿼리 처리 및 조회"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
    
    def _format_ticker(self, ticker: str) -> List[str]:
        """종목 코드에 시장 접미사 추가"""
        if '.' in ticker:
            return [ticker]
        return [f"{ticker}.KS", f"{ticker}.KQ", f"{ticker}.KN"]
    
    def get_stock_price_info(self, ticker: str, date: str = None) -> str:
        """특정 종목 특정날짜의 가격 정보 조회"""
        try:
            self.logger.info(f"주가 조회 시작 - ticker: {ticker}, date: {date}")
            
            # 종목명인 경우 검색해서 티커 찾기
            if not ticker.isdigit() and '.' not in ticker:
                company_df = self.db_manager.get_company_info(stock_name=ticker)
                if not company_df.empty:
                    ticker = company_df.iloc[0]['ticker']
            
            tickers_to_try = self._format_ticker(ticker)
            df = None
            
            for ticker_formatted in tickers_to_try:
                df = self.db_manager.get_stock_price(ticker_formatted, date)
                if not df.empty:
                    break
            
            if df is None or df.empty:
                return f"{ticker} 종목의 {date} 가격 정보를 찾을 수 없습니다."
            
            row = df.iloc[0]
            result = f"{row['stock_name']}의 {row['trading_date']} 가격 정보:\n"
            result += f"- 시가: {row['open_price']:,.0f}원\n"
            result += f"- 고가: {row['high_price']:,.0f}원\n"
            result += f"- 저가: {row['low_price']:,.0f}원\n"
            result += f"- 종가: {row['close_price']:,.0f}원\n"
            result += f"- 거래량: {row['trading_volume']:,}주\n"
            result += f"- 등락률: {row['change_rate']:.2f}%"
            
            return result
        except Exception as e:
            self.logger.error(f"가격 정보 조회 중 오류: {str(e)}")
            return f"가격 정보 조회 중 오류 발생: {str(e)}"
    
    def search_company_by_name(self, stock_name: str) -> str:
        """회사명으로 종목 검색"""
        try:
            df = self.db_manager.get_company_info(stock_name=stock_name)
            if df.empty:
                return f"'{stock_name}' 관련 종목을 찾을 수 없습니다."
            
            result = f"'{stock_name}' 검색 결과:\n"
            for _, row in df.iterrows():
                result += f"- {row['stock_name']} ({row['ticker']}) - {row['market_type']}\n"
            
            return result
        except Exception as e:
            return f"회사 검색 중 오류 발생: {str(e)}"
    
    def get_market_statistics(self, date: str) -> str:
        """시장 통계 정보 조회 (시장 평균 등락률 포함)"""
        try:
            self.logger.info(f"시장 통계 조회 - date: {date}")
            stats = self.db_manager.get_market_statistics(date)
            
            result = f"{date} 시장 통계:\n"
            result += f"- 전체 종목수: {stats['total_stocks']}개\n"
            result += f"- 상승 종목수: {stats['up_stocks']}개\n"
            result += f"- 하락 종목수: {stats['down_stocks']}개\n"
            result += f"- 보합 종목수: {stats['flat_stocks']}개\n"
            result += f"- KOSPI 종목수: {stats['kospi_stocks']}개\n"
            result += f"- KOSDAQ 종목수: {stats['kosdaq_stocks']}개\n"
            # 중요한 추가 정보들
            result += f"- **시장 평균 등락률: {stats['avg_change_rate']:.4f}%**\n"
            result += f"- 최고 등락률: {stats['max_change_rate']:.4f}%\n"
            result += f"- 최저 등락률: {stats['min_change_rate']:.4f}%\n"
            result += f"- 상승 종목 평균 등락률: {stats['up_avg_change_rate']:.4f}%\n"
            result += f"- 하락 종목 평균 등락률: {stats['down_avg_change_rate']:.4f}%\n"
            result += f"- KOSPI 평균 등락률: {stats['kospi_avg_change_rate']:.4f}%\n"
            result += f"- KOSDAQ 평균 등락률: {stats['kosdaq_avg_change_rate']:.4f}%\n"
            result += f"- 전체 거래대금: {stats['total_trading_value']:,.0f}원"
            
            return result
        except Exception as e:
            self.logger.error(f"시장 통계 조회 중 오류: {str(e)}")
            return f"시장 통계 조회 중 오류 발생: {str(e)}"

    def get_price_change_ranking(self, date: str, limit: int = 50) -> str:
        """등락률 상위 종목 조회"""
        try:
            self.logger.info(f"등락률 순위 조회 - date: {date}, limit: {limit}")
            df = self.db_manager.search_top_price_change_stocks(date, None, False, limit)
            
            if df.empty:
                return f"{date}에 등락률 데이터를 찾을 수 없습니다."
            
            result_list = []
            for _, row in df.iterrows():
                result_list.append(f"{row['stock_name']}({row['change_rate']:.2f}%)")
            
            result = f"{date} 상승률 상위 {len(df)}개: {', '.join(result_list)}"
            return result
        except Exception as e:
            self.logger.error(f"등락률 조회 중 오류: {str(e)}")
            return f"등락률 조회 중 오류 발생: {str(e)}"

    def get_trading_value_ranking(self, date: str, limit: int = 30) -> str:
        """거래대금 상위 종목 조회"""
        try:
            self.logger.info(f"거래대금 순위 조회 - date: {date}, limit: {limit}")
            df = self.db_manager.search_top_trading_value_stocks(date, None, limit)
            
            if df.empty:
                return f"{date}에 거래대금 데이터를 찾을 수 없습니다."
            
            result_list = []
            for _, row in df.iterrows():
                trading_value = row['trading_value'] / 100000000  # 억원 단위
                result_list.append(f"{row['stock_name']}({trading_value:.0f}억원)")
            
            result = f"{date} 거래대금 상위 {len(df)}개: {', '.join(result_list)}"
            return result
        except Exception as e:
            self.logger.error(f"거래대금 조회 중 오류: {str(e)}")
            return f"거래대금 조회 중 오류 발생: {str(e)}"

    def get_volume_ranking(self, date: str, market: str = None, limit: int = 50) -> str:
        """거래량 상위 종목 조회"""
        try:
            self.logger.info(f"거래량 순위 조회 - date: {date}, market: {market}, limit: {limit}")
            df = self.db_manager.search_top_volume_stocks(date, market, limit)
            
            if df.empty:
                market_text = f"{market} " if market else ""
                return f"{date}에 {market_text}거래량 데이터를 찾을 수 없습니다."
            
            result_list = []
            for _, row in df.iterrows():
                volume = row['trading_volume']
                result_list.append(f"{row['stock_name']}({volume:,}주)")
            
            market_text = f"{market} " if market else ""
            result = f"{date} {market_text}거래량 상위 {len(df)}개: {', '.join(result_list)}"
            return result
        except Exception as e:
            self.logger.error(f"거래량 조회 중 오류: {str(e)}")
            return f"거래량 조회 중 오류 발생: {str(e)}"

    def get_market_index(self, date: str, market: str = "KOSPI") -> str:
        """시장 지수 조회 (KOSPI/KOSDAQ)"""
        try:
            self.logger.info(f"{market} 지수 조회 - date: {date}")
            
            # market 파라미터 정규화
            market = market.upper()
            if market not in ["KOSPI", "KOSDAQ"]:
                market = "KOSPI"  # 기본값
            
            # 통합된 시장 데이터 조회
            df = self.db_manager.get_market_data(date)
            
            if df.empty:
                return f"{date}의 시장 지수 데이터를 찾을 수 없습니다."
            
            # 해당 시장 지수 필터링
            market_df = df[df['market_index_name'] == market]
            
            if market_df.empty:
                return f"{date}의 {market} 지수 데이터를 찾을 수 없습니다."
            
            row = market_df.iloc[0]
            index_value = row['close_price']
            
            return f"{date} {market} 지수: {index_value:.2f}"
        except Exception as e:
            self.logger.error(f"{market} 지수 조회 중 오류: {str(e)}")
            return f"{market} 지수 조회 중 오류 발생: {str(e)}"

    def get_kospi_index(self, date: str) -> str:
        """KOSPI 지수 조회 (호환성 유지)"""
        return self.get_market_index(date, "KOSPI")