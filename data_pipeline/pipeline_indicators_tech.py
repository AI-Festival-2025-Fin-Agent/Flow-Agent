import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    print("Warning: talib not available. Using pandas implementation.")


class TechnicalIndicatorCalculator:
    def __init__(self, stock_db_path: str, output_db_path: str):
        self.stock_db_path = stock_db_path
        self.output_db_path = output_db_path
        
    def get_stock_data(self, ticker: str = None) -> pd.DataFrame:
        """주식 데이터 조회"""
        conn = sqlite3.connect(self.stock_db_path)
        
        if ticker:
            query = """
            SELECT * FROM stock_prices 
            WHERE ticker = ? 
            ORDER BY trading_date
            """
            df = pd.read_sql_query(query, conn, params=[ticker])
        else:
            query = """
            SELECT * FROM stock_prices 
            ORDER BY ticker, trading_date
            """
            df = pd.read_sql_query(query, conn)
        
        conn.close()
        return df
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """RSI 계산"""
        if TALIB_AVAILABLE:
            return talib.RSI(prices.values, timeperiod=period)
        else:
            # pandas로 RSI 계산
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.values
    
    def calculate_moving_averages(self, prices: pd.Series) -> Dict[str, pd.Series]:
        """이동평균선 계산"""
        if TALIB_AVAILABLE:
            return {
                'ma5': talib.SMA(prices.values, timeperiod=5),
                'ma10': talib.SMA(prices.values, timeperiod=10),
                'ma20': talib.SMA(prices.values, timeperiod=20),
                'ma60': talib.SMA(prices.values, timeperiod=60),
                'ma120': talib.SMA(prices.values, timeperiod=120)
            }
        else:
            return {
                'ma5': prices.rolling(window=5).mean().values,
                'ma10': prices.rolling(window=10).mean().values,
                'ma20': prices.rolling(window=20).mean().values,
                'ma60': prices.rolling(window=60).mean().values,
                'ma120': prices.rolling(window=120).mean().values
            }
    
    def calculate_bollinger_bands(self, prices: pd.Series, period: int = 20) -> Dict[str, pd.Series]:
        """볼린저 밴드 계산"""
        if TALIB_AVAILABLE:
            upper, middle, lower = talib.BBANDS(prices.values, timeperiod=period)
            return {
                'bb_upper': upper,
                'bb_middle': middle,
                'bb_lower': lower
            }
        else:
            # pandas로 볼린저 밴드 계산
            sma = prices.rolling(window=period).mean()
            std = prices.rolling(window=period).std()
            return {
                'bb_upper': (sma + (std * 2)).values,
                'bb_middle': sma.values,
                'bb_lower': (sma - (std * 2)).values
            }
    
    def calculate_macd(self, prices: pd.Series) -> Dict[str, pd.Series]:
        """MACD 계산"""
        if TALIB_AVAILABLE:
            macd, macd_signal, macd_hist = talib.MACD(prices.values)
            return {
                'macd': macd,
                'macd_signal': macd_signal,
                'macd_histogram': macd_hist
            }
        else:
            # pandas로 MACD 계산
            ema12 = prices.ewm(span=12).mean()
            ema26 = prices.ewm(span=26).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9).mean()
            histogram = macd - signal
            return {
                'macd': macd.values,
                'macd_signal': signal.values,
                'macd_histogram': histogram.values
            }
    
    def detect_golden_dead_cross(self, ma5: pd.Series, ma20: pd.Series) -> Dict[str, pd.Series]:
        """골든크로스/데드크로스 감지"""
        golden_cross = (ma5 > ma20) & (ma5.shift(1) <= ma20.shift(1))
        dead_cross = (ma5 < ma20) & (ma5.shift(1) >= ma20.shift(1))
        
        return {
            'golden_cross': golden_cross,
            'dead_cross': dead_cross
        }
    
    def calculate_volume_indicators(self, volume: pd.Series) -> Dict[str, pd.Series]:
        """거래량 지표 계산"""
        if TALIB_AVAILABLE:
            volume_ma20 = talib.SMA(volume.values, timeperiod=20)
            volume_ratio = volume / volume_ma20
        else:
            volume_ma20 = volume.rolling(window=20).mean()
            volume_ratio = volume / volume_ma20
        
        return {
            'volume_ma20': volume_ma20.values if hasattr(volume_ma20, 'values') else volume_ma20,
            'volume_ratio': volume_ratio.values if hasattr(volume_ratio, 'values') else volume_ratio
        }
    
    def calculate_all_indicators(self, ticker: str) -> pd.DataFrame:
        """특정 종목의 모든 기술지표 계산"""
        df = self.get_stock_data(ticker)
        if df.empty:
            return pd.DataFrame()
        
        result_df = df[['ticker', 'trading_date', 'close_price', 'trading_volume']].copy()
        
        # RSI
        result_df['rsi'] = self.calculate_rsi(df['close_price'])
        
        # 이동평균선
        mas = self.calculate_moving_averages(df['close_price'])
        for key, values in mas.items():
            result_df[key] = values
        
        # 볼린저 밴드
        bb = self.calculate_bollinger_bands(df['close_price'])
        for key, values in bb.items():
            result_df[key] = values
        
        # MACD
        macd = self.calculate_macd(df['close_price'])
        for key, values in macd.items():
            result_df[key] = values
        
        # 골든크로스/데드크로스
        crosses = self.detect_golden_dead_cross(result_df['ma5'], result_df['ma20'])
        for key, values in crosses.items():
            result_df[key] = values
        
        # 거래량 지표
        volume_indicators = self.calculate_volume_indicators(df['trading_volume'])
        for key, values in volume_indicators.items():
            result_df[key] = values
        
        return result_df
    
    def create_technical_indicators_db(self):
        """기술지표 DB 생성"""
        conn = sqlite3.connect(self.output_db_path)
        cursor = conn.cursor()
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS technical_indicators (
            ticker TEXT,
            trading_date TEXT,
            close_price REAL,
            trading_volume INTEGER,
            rsi REAL,
            ma5 REAL,
            ma10 REAL,
            ma20 REAL,
            ma60 REAL,
            ma120 REAL,
            bb_upper REAL,
            bb_middle REAL,
            bb_lower REAL,
            macd REAL,
            macd_signal REAL,
            macd_histogram REAL,
            golden_cross BOOLEAN,
            dead_cross BOOLEAN,
            volume_ma20 REAL,
            volume_ratio REAL,
            PRIMARY KEY (ticker, trading_date)
        )
        """
        
        cursor.execute(create_table_sql)
        conn.commit()
        conn.close()
    
    def save_indicators_to_db(self, df: pd.DataFrame):
        """기술지표를 DB에 저장"""
        conn = sqlite3.connect(self.output_db_path)
        df.to_sql('technical_indicators', conn, if_exists='append', index=False)
        conn.close()
    
    def process_all_stocks(self):
        """모든 종목의 기술지표 계산 및 저장"""
        # 기술지표 DB 생성
        self.create_technical_indicators_db()
        
        # 모든 종목 리스트 가져오기
        conn = sqlite3.connect(self.stock_db_path)
        tickers = pd.read_sql_query("SELECT DISTINCT ticker FROM stock_prices", conn)['ticker'].tolist()
        conn.close()
        
        print(f"총 {len(tickers)}개 종목의 기술지표를 계산합니다...")
        
        for i, ticker in enumerate(tickers, 1):
            try:
                print(f"[{i}/{len(tickers)}] {ticker} 처리 중...")
                indicator_df = self.calculate_all_indicators(ticker)
                
                if not indicator_df.empty:
                    self.save_indicators_to_db(indicator_df)
                    print(f"{ticker} 완료")
                else:
                    print(f"{ticker} 데이터 없음")
                    
            except Exception as e:
                print(f"{ticker} 처리 중 오류: {e}")
                continue
        
        print("모든 기술지표 계산 완료!")


if __name__ == "__main__":
    calculator = TechnicalIndicatorCalculator(
        stock_db_path="stock_info_20251013.db",
        output_db_path="technical_indicators_20251013.db"
    )
    
    calculator.process_all_stocks()
#  nohup python pipeline_indicators_tech.py > log/251013_tech.log 2>&1 &

