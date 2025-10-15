import sqlite3
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta


class DatabaseManager:
    def __init__(self, company_csv_path: str, stock_db_path: str, market_db_path: str, technical_db_path: str):
        self.company_csv_path = company_csv_path
        self.stock_db_path = stock_db_path
        self.market_db_path = market_db_path
        self.technical_db_path = technical_db_path
        
    def get_company_info(self, ticker: str = None, stock_name: str = None) -> pd.DataFrame:
        """회사 정보 조회"""
        df = pd.read_csv(self.company_csv_path)
        
        if ticker:
            return df[df['ticker'] == ticker]
        elif stock_name:
            if df[df['stock_name'] == stock_name].any().any():
                return df[df['stock_name'] == stock_name]
                # 부분 일치 검색
            else:
                return df[df['stock_name'].str.contains(stock_name, na=False)]
        else:
            return df
    
    def get_stock_price(self, ticker: str, date: str = None, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """주가 정보 조회"""
        conn = sqlite3.connect(self.stock_db_path)

        suffixes = [".KS", ".KQ", ".KN"]
        tickers = [ticker] if "." in ticker else [ticker + sfx for sfx in suffixes]

        all_results = []
        for t in tickers:
            if date:
                query = """
                SELECT * FROM stock_prices 
                WHERE ticker = ? AND trading_date = ?
                """
                df = pd.read_sql_query(query, conn, params=[t, date])
            elif start_date and end_date:
                query = """
                SELECT * FROM stock_prices 
                WHERE ticker = ? AND trading_date BETWEEN ? AND ?
                ORDER BY trading_date
                """
                df = pd.read_sql_query(query, conn, params=[t, start_date, end_date])
            else:
                query = """
                SELECT * FROM stock_prices 
                WHERE ticker = ?
                ORDER BY trading_date DESC
                LIMIT 1
                """
                df = pd.read_sql_query(query, conn, params=[t])
            
            if not df.empty:
                all_results.append(df)

        conn.close()

        if all_results:
            return pd.concat(all_results, ignore_index=True)
        else:
            return pd.DataFrame()  # 빈 데이터프레임 반환

    
    def get_market_data(self, date: str = None, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """시장 지수 데이터 조회"""
        conn = sqlite3.connect(self.market_db_path)
        
        if date:
            query = """
            SELECT * FROM market_index 
            WHERE trading_date = ?
            """
            df = pd.read_sql_query(query, conn, params=[date])
        elif start_date and end_date:
            query = """
            SELECT * FROM market_index 
            WHERE trading_date BETWEEN ? AND ?
            ORDER BY trading_date
            """
            df = pd.read_sql_query(query, conn, params=[start_date, end_date])
        else:
            query = """
            SELECT * FROM market_index 
            ORDER BY trading_date DESC
            LIMIT 1
            """
            df = pd.read_sql_query(query, conn)
        
        conn.close()
        return df
    
    def get_technical_indicators(self, ticker: str, date: str = None, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """기술지표 데이터 조회"""
        conn = sqlite3.connect(self.technical_db_path)
        
        if date:
            query = """
            SELECT * FROM technical_indicators 
            WHERE ticker = ? AND trading_date = ?
            """
            df = pd.read_sql_query(query, conn, params=[ticker, date])
        elif start_date and end_date:
            query = """
            SELECT * FROM technical_indicators 
            WHERE ticker = ? AND trading_date BETWEEN ? AND ?
            ORDER BY trading_date
            """
            df = pd.read_sql_query(query, conn, params=[ticker, start_date, end_date])
        else:
            query = """
            SELECT * FROM technical_indicators 
            WHERE ticker = ?
            ORDER BY trading_date DESC
            LIMIT 1
            """
            df = pd.read_sql_query(query, conn, params=[ticker])
        
        conn.close()
        return df
    
    def search_stocks_by_volume(self, date: str, min_volume: int = None, volume_ratio: float = None, limit: int = None) -> pd.DataFrame:
        """거래량 조건으로 종목 검색"""
        conn = sqlite3.connect(self.stock_db_path)
        
        if volume_ratio:
            # 기술지표 DB에서 거래량 비율로 검색
            tech_conn = sqlite3.connect(self.technical_db_path)
            query = """
            SELECT ticker, trading_date, close_price, trading_volume, volume_ratio
            FROM technical_indicators 
            WHERE trading_date = ? AND volume_ratio >= ?
            ORDER BY volume_ratio DESC
            """
            params = [date, volume_ratio]
            if limit:
                query += f" LIMIT {limit}"
            df = pd.read_sql_query(query, tech_conn, params=params)
            tech_conn.close()
        elif min_volume:
            query = """
            SELECT * FROM stock_prices 
            WHERE trading_date = ? AND trading_volume >= ?
            ORDER BY trading_volume DESC
            """
            params = [date, min_volume]
            if limit:
                query += f" LIMIT {limit}"
            df = pd.read_sql_query(query, conn, params=params)
        else:
            query = """
            SELECT * FROM stock_prices 
            WHERE trading_date = ?
            ORDER BY trading_volume DESC
            """
            params = [date]
            if limit:
                query += f" LIMIT {limit}"
            df = pd.read_sql_query(query, conn, params=params)
        
        conn.close()
        return df
    
    def search_stocks_by_price_change(self, date: str, min_change_rate: float, min_volume_ratio: float = None) -> pd.DataFrame:
        """가격 변화율과 거래량으로 종목 검색"""
        conn = sqlite3.connect(self.stock_db_path)
        
        if min_volume_ratio:
            # 기술지표 DB와 조인하여 검색
            tech_conn = sqlite3.connect(self.technical_db_path)
            query = """
            SELECT s.ticker, s.stock_name, s.trading_date, s.close_price, s.change_rate, 
                   s.trading_volume, t.volume_ratio
            FROM stock_prices s
            JOIN technical_indicators t ON s.ticker = t.ticker AND s.trading_date = t.trading_date
            WHERE s.trading_date = ? AND s.change_rate >= ? AND t.volume_ratio >= ?
            ORDER BY s.change_rate DESC
            """
            df = pd.read_sql_query(query, tech_conn, params=[date, min_change_rate, min_volume_ratio])
            tech_conn.close()
        else:
            query = """
            SELECT * FROM stock_prices 
            WHERE trading_date = ? AND change_rate >= ?
            ORDER BY change_rate DESC
            """
            df = pd.read_sql_query(query, conn, params=[date, min_change_rate])
        
        conn.close()
        return df
    
    def search_rsi_stocks(self, date: str, rsi_min: float = None, rsi_max: float = None, limit: int = None) -> pd.DataFrame:
        """RSI 조건으로 종목 검색"""
        conn = sqlite3.connect(self.technical_db_path)
        
        if rsi_min and rsi_max:
            query = """
            SELECT ticker, trading_date, close_price, rsi
            FROM technical_indicators 
            WHERE trading_date = ? AND rsi BETWEEN ? AND ?
            ORDER BY rsi DESC
            """
            params = [date, rsi_min, rsi_max]
        elif rsi_min:
            query = """
            SELECT ticker, trading_date, close_price, rsi
            FROM technical_indicators 
            WHERE trading_date = ? AND rsi >= ?
            ORDER BY rsi DESC
            """
            params = [date, rsi_min]
        elif rsi_max:
            query = """
            SELECT ticker, trading_date, close_price, rsi
            FROM technical_indicators 
            WHERE trading_date = ? AND rsi <= ?
            ORDER BY rsi ASC
            """
            params = [date, rsi_max]
        else:
            query = """
            SELECT ticker, trading_date, close_price, rsi
            FROM technical_indicators 
            WHERE trading_date = ?
            ORDER BY rsi DESC
            """
            params = [date]
        
        if limit:
            query += f" LIMIT {limit}"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    
    def search_cross_signals(self, start_date: str, end_date: str, signal_type: str = 'golden') -> pd.DataFrame:
        """골든크로스/데드크로스 신호 검색"""
        conn = sqlite3.connect(self.technical_db_path)
        
        if signal_type == 'golden':
            query = """
            SELECT ticker, trading_date, close_price, ma5, ma20
            FROM technical_indicators 
            WHERE trading_date BETWEEN ? AND ? AND golden_cross = 1
            ORDER BY trading_date DESC
            """
        else:  # dead_cross
            query = """
            SELECT ticker, trading_date, close_price, ma5, ma20
            FROM technical_indicators 
            WHERE trading_date BETWEEN ? AND ? AND dead_cross = 1
            ORDER BY trading_date DESC
            """
        
        df = pd.read_sql_query(query, conn, params=[start_date, end_date])
        conn.close()
        return df
    
    def get_market_statistics(self, date: str) -> Dict[str, Any]:
        """시장 통계 정보 조회 (시장 평균 등락률 포함)"""
        conn = sqlite3.connect(self.stock_db_path)
        
        # 전체 통계 (종목수 + 평균 등락률)
        overall_stats = pd.read_sql_query(
            """SELECT 
                COUNT(DISTINCT ticker) as total_stocks,
                AVG(change_rate) as avg_change_rate,
                MAX(change_rate) as max_change_rate,
                MIN(change_rate) as min_change_rate,
                SUM(CASE WHEN change_rate > 0 THEN 1 ELSE 0 END) as up_stocks,
                SUM(CASE WHEN change_rate < 0 THEN 1 ELSE 0 END) as down_stocks,
                SUM(trading_volume * close_price) as total_trading_value
               FROM stock_prices 
               WHERE trading_date = ?""",
            conn, params=[date]
        )
        
        # 상승/하락 종목 평균 등락률
        avg_rates = pd.read_sql_query(
            """SELECT 
                AVG(CASE WHEN change_rate > 0 THEN change_rate END) as up_avg_change_rate,
                AVG(CASE WHEN change_rate < 0 THEN change_rate END) as down_avg_change_rate
               FROM stock_prices 
               WHERE trading_date = ?""",
            conn, params=[date]
        )
        
        # 시장별 통계
        market_stats = pd.read_sql_query(
            """SELECT market, COUNT(*) as count, AVG(change_rate) as avg_change_rate
               FROM stock_prices 
               WHERE trading_date = ? 
               GROUP BY market""",
            conn, params=[date]
        )
        
        conn.close()
        
        # 결과 정리
        overall = overall_stats.iloc[0] if not overall_stats.empty else {}
        avg_data = avg_rates.iloc[0] if not avg_rates.empty else {}
        
        market_dict = dict(zip(market_stats['market'], market_stats['count']))
        market_avg_dict = dict(zip(market_stats['market'], market_stats['avg_change_rate']))
        
        return {
            'total_stocks': int(overall.get('total_stocks', 0)),
            'up_stocks': int(overall.get('up_stocks', 0)),
            'down_stocks': int(overall.get('down_stocks', 0)),
            'flat_stocks': int(overall.get('total_stocks', 0)) - int(overall.get('up_stocks', 0)) - int(overall.get('down_stocks', 0)),
            'kospi_stocks': market_dict.get('KOSPI', 0),
            'kosdaq_stocks': market_dict.get('KOSDAQ', 0),
            # 중요한 추가 정보들
            'avg_change_rate': float(overall.get('avg_change_rate', 0.0)),  # 시장 평균 등락률
            'max_change_rate': float(overall.get('max_change_rate', 0.0)),
            'min_change_rate': float(overall.get('min_change_rate', 0.0)),
            'up_avg_change_rate': float(avg_data.get('up_avg_change_rate') or 0.0),
            'down_avg_change_rate': float(avg_data.get('down_avg_change_rate') or 0.0),
            'total_trading_value': float(overall.get('total_trading_value', 0.0)),
            'kospi_avg_change_rate': float(market_avg_dict.get('KOSPI', 0.0)),
            'kosdaq_avg_change_rate': float(market_avg_dict.get('KOSDAQ', 0.0))
        }
    
    def search_top_volume_stocks(self, date: str, market: str = None, limit: int = 10) -> pd.DataFrame:
        """거래량 상위 종목 검색"""
        conn = sqlite3.connect(self.stock_db_path)
        
        if market:
            query = """
            SELECT ticker, stock_name, trading_volume, close_price, change_rate
            FROM stock_prices 
            WHERE trading_date = ? AND market = ?
            ORDER BY trading_volume DESC
            LIMIT ?
            """
            params = [date, market, limit]
        else:
            query = """
            SELECT ticker, stock_name, trading_volume, close_price, change_rate
            FROM stock_prices 
            WHERE trading_date = ?
            ORDER BY trading_volume DESC
            LIMIT ?
            """
            params = [date, limit]
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    
    def search_top_price_change_stocks(self, date: str, market: str = None, ascending: bool = False, limit: int = 10) -> pd.DataFrame:
        """등락률 상위/하위 종목 검색"""
        conn = sqlite3.connect(self.stock_db_path)
        
        order_clause = "ASC" if ascending else "DESC"
        
        if market:
            query = f"""
            SELECT ticker, stock_name, close_price, change_rate, trading_volume
            FROM stock_prices 
            WHERE trading_date = ? AND market = ?
            ORDER BY change_rate {order_clause}
            LIMIT ?
            """
            params = [date, market, limit]
        else:
            query = f"""
            SELECT ticker, stock_name, close_price, change_rate, trading_volume
            FROM stock_prices 
            WHERE trading_date = ?
            ORDER BY change_rate {order_clause}
            LIMIT ?
            """
            params = [date, limit]
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    
    def search_top_trading_value_stocks(self, date: str, market: str = None, limit: int = 10) -> pd.DataFrame:
        """거래대금 상위 종목 검색"""
        conn = sqlite3.connect(self.stock_db_path)
        
        if market:
            query = """
            SELECT ticker, stock_name, close_price, trading_volume, 
                   (close_price * trading_volume) as trading_value, change_rate
            FROM stock_prices 
            WHERE trading_date = ? AND market = ?
            ORDER BY trading_value DESC
            LIMIT ?
            """
            params = [date, market, limit]
        else:
            query = """
            SELECT ticker, stock_name, close_price, trading_volume, 
                   (close_price * trading_volume) as trading_value, change_rate
            FROM stock_prices 
            WHERE trading_date = ?
            ORDER BY trading_value DESC
            LIMIT ?
            """
            params = [date, limit]
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    
    def search_top_market_cap_stocks(self, date: str, market: str = None, limit: int = 10) -> pd.DataFrame:
        """시가총액 상위 종목 검색 (근사치 - 상장주식수 정보가 없어서 거래량 * 주가로 대체)"""
        conn = sqlite3.connect(self.stock_db_path)
        
        if market:
            query = """
            SELECT ticker, stock_name, close_price, trading_volume, 
                   (close_price * trading_volume) as approx_market_cap, change_rate
            FROM stock_prices 
            WHERE trading_date = ? AND market = ?
            ORDER BY close_price DESC
            LIMIT ?
            """
            params = [date, market, limit]
        else:
            query = """
            SELECT ticker, stock_name, close_price, trading_volume, 
                   (close_price * trading_volume) as approx_market_cap, change_rate
            FROM stock_prices 
            WHERE trading_date = ?
            ORDER BY close_price DESC
            LIMIT ?
            """
            params = [date, limit]
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    
    def get_kospi_index(self, date: str) -> pd.DataFrame:
        """KOSPI 지수 조회"""
        conn = sqlite3.connect(self.market_db_path)
        
        query = """
        SELECT * FROM market_index 
        WHERE trading_date = ? AND market_index_name = 'KOSPI'
        """
        df = pd.read_sql_query(query, conn, params=[date])
        conn.close()
        return df
    
    def get_total_trading_value(self, date: str) -> float:
        """전체 시장 거래대금 조회"""
        conn = sqlite3.connect(self.stock_db_path)
        
        query = """
        SELECT SUM(close_price * trading_volume) as total_trading_value
        FROM stock_prices 
        WHERE trading_date = ?
        """
        result = pd.read_sql_query(query, conn, params=[date])
        conn.close()
        
        return result['total_trading_value'].iloc[0] if not result.empty else 0
    
    def search_volume_surge_stocks(self, date: str, surge_ratio: float = 5.0, limit: int = 20) -> pd.DataFrame:
        """20일 평균 대비 거래량 급증 종목 검색"""
        conn = sqlite3.connect(self.technical_db_path)
        
        query = """
        SELECT ticker, trading_date, close_price, trading_volume, 
               volume_ratio, (volume_ratio * 100) as surge_percentage
        FROM technical_indicators 
        WHERE trading_date = ? AND volume_ratio >= ?
        ORDER BY volume_ratio DESC
        LIMIT ?
        """
        df = pd.read_sql_query(query, conn, params=[date, surge_ratio, limit])
        conn.close()
        return df
    
    def search_bollinger_touch_stocks(self, date: str, band_type: str = "upper", limit: int = 15) -> pd.DataFrame:
        """볼린저 밴드 터치 종목 검색 - 더 정확한 터치 기준 적용"""
        conn = sqlite3.connect(self.technical_db_path)
        
        if band_type == "upper":
            # 상단 밴드 터치: 고가나 종가가 볼린저 상단 밴드에 매우 근접하거나 돌파
            query = """
            SELECT ticker, trading_date, close_price, bb_upper, bb_middle, bb_lower,
                   ABS(close_price - bb_upper) as touch_distance,
                   ((close_price - bb_upper) / bb_upper * 100) as deviation_pct
            FROM technical_indicators 
            WHERE trading_date = ? 
            AND (close_price >= bb_upper * 0.9995 OR close_price <= bb_upper * 1.0005)
            ORDER BY ABS(close_price - bb_upper) ASC
            LIMIT ?
            """
        else:  # lower
            # 하단 밴드 터치: 저가나 종가가 볼린저 하단 밴드에 매우 근접하거나 하회
            query = """
            SELECT ticker, trading_date, close_price, bb_upper, bb_middle, bb_lower,
                   ABS(close_price - bb_lower) as touch_distance,
                   ((bb_lower - close_price) / bb_lower * 100) as deviation_pct
            FROM technical_indicators 
            WHERE trading_date = ? 
            AND (close_price <= bb_lower * 1.0005 OR close_price >= bb_lower * 0.9995)
            ORDER BY ABS(close_price - bb_lower) ASC
            LIMIT ?
            """
        
        df = pd.read_sql_query(query, conn, params=[date, limit])
        conn.close()
        return df
    
    def search_ma_breakout_stocks(self, date: str, ma_period: int = 20, breakout_ratio: float = 0.03, limit: int = 15) -> pd.DataFrame:
        """이동평균 돌파 종목 검색"""
        conn = sqlite3.connect(self.technical_db_path)
        
        ma_column = f"ma{ma_period}"
        
        query = f"""
        SELECT ticker, trading_date, close_price, {ma_column},
               ((close_price - {ma_column}) / {ma_column} * 100) as breakout_percentage
        FROM technical_indicators 
        WHERE trading_date = ? AND close_price > {ma_column} * (1 + ?)
        ORDER BY breakout_percentage DESC
        LIMIT ?
        """
        df = pd.read_sql_query(query, conn, params=[date, breakout_ratio, limit])
        conn.close()
        return df
    
    def count_cross_signals(self, ticker: str, start_date: str, end_date: str, signal_type: str = "golden") -> int:
        """특정 종목의 골든크로스/데드크로스 횟수 조회"""
        conn = sqlite3.connect(self.technical_db_path)
        
        column_name = "golden_cross" if signal_type == "golden" else "dead_cross"
        
        query = f"""
        SELECT COUNT(*) as count
        FROM technical_indicators 
        WHERE ticker = ? AND trading_date BETWEEN ? AND ? AND {column_name} = 1
        """
        result = pd.read_sql_query(query, conn, params=[ticker, start_date, end_date])
        conn.close()
        
        return result['count'].iloc[0] if not result.empty else 0
    
    def search_cross_signals(self, start_date: str, end_date: str, signal_type: str = "golden") -> pd.DataFrame:
        """골든크로스/데드크로스 발생 종목 검색"""
        conn = sqlite3.connect(self.technical_db_path)
        
        column_name = "golden_cross" if signal_type == "golden" else "dead_cross"
        
        query = f"""
        SELECT ticker, trading_date, close_price, ma5, ma20
        FROM technical_indicators 
        WHERE trading_date BETWEEN ? AND ? AND {column_name} = 1
        ORDER BY trading_date DESC, ticker
        """
        df = pd.read_sql_query(query, conn, params=[start_date, end_date])
        conn.close()
        return df