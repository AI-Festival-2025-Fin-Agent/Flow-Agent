#!/usr/bin/env python3
"""
기존 DB에 새로운 데이터 삽입 후 중복 제거 스크립트
- stock_info: 삽입 후 trading_date+ticker 기준 중복 제거
- technical_indicators: 기존 방식 유지
- 기존/삽입 전후/중복 제거 후 행 수를 자세히 로깅
"""

import sqlite3
import logging
from pathlib import Path
import shutil

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def merge_new_data(
    target_ti_db_path: str,
    target_stock_db_path: str,
    source_ti_db_path: str,
    source_stock_db_path: str
):
    """새로운 데이터만 기존 데이터베이스에 추가, stock_info는 삽입 후 중복 제거"""

    # 파일 존재 확인
    for db_path in [target_ti_db_path, source_ti_db_path, source_stock_db_path]:
        if not Path(db_path).exists():
            logger.error(f"파일이 존재하지 않습니다: {db_path}")
            return False

    try:
        # ================================
        # 1. technical_indicators 병합
        # ================================
        logger.info("=== technical_indicators.db 병합 시작 ===")
        conn_ti = sqlite3.connect(target_ti_db_path)
        cursor_ti = conn_ti.cursor()
        cursor_ti.execute(f'ATTACH DATABASE "{source_ti_db_path}" AS source_ti')

        cursor_ti.execute('''
            INSERT OR IGNORE INTO main.technical_indicators (
                ticker, trading_date, close_price, trading_volume, rsi, ma5, ma10, ma20,
                ma60, ma120, bb_upper, bb_middle, bb_lower, macd, macd_signal,
                macd_histogram, golden_cross, dead_cross, volume_ma20, volume_ratio
            )
            SELECT
                s.ticker, s.trading_date, s.close_price, s.trading_volume, s.rsi, s.ma5, s.ma10, s.ma20,
                s.ma60, s.ma120, s.bb_upper, s.bb_middle, s.bb_lower, s.macd, s.macd_signal,
                s.macd_histogram, s.golden_cross, s.dead_cross, s.volume_ma20, s.volume_ratio
            FROM source_ti.technical_indicators s
        ''')

        ti_rows_added = cursor_ti.rowcount
        cursor_ti.execute('SELECT COUNT(*) FROM technical_indicators')
        total_ti_rows = cursor_ti.fetchone()[0]
        conn_ti.commit()
        conn_ti.close()
        logger.info(f"technical_indicators.db 총 행 수: {total_ti_rows:,} (새로 추가: {ti_rows_added:,})")

        # ================================
        # 2. stock_info 병합
        # ================================
        logger.info("=== stock_info.db 병합 시작 ===")

        if not Path(target_stock_db_path).exists():
            logger.info("stock_info.db가 없어 복사 중...")
            shutil.copy2(source_stock_db_path, target_stock_db_path)
            logger.info("stock_info.db 복사 완료")
        else:
            conn_stock = sqlite3.connect(target_stock_db_path)
            cursor_stock = conn_stock.cursor()
            cursor_stock.execute(f'ATTACH DATABASE "{source_stock_db_path}" AS source')

            # 1) 삽입 전 행 수 확인
            cursor_stock.execute('SELECT COUNT(*) FROM stock_prices')
            before_stock_rows = cursor_stock.fetchone()[0]
            logger.info(f"stock_info.db 삽입 전 행 수: {before_stock_rows:,}")

            # 2) source 데이터 전부 삽입 (속도 빠름)
            cursor_stock.execute('''
                INSERT INTO main.stock_prices (
                    trading_date, adj_close_price, close_price, high_price, low_price,
                    open_price, trading_volume, prev_close_price, change, change_rate,
                    ticker, stock_name, market
                )
                SELECT *
                FROM source.stock_prices
            ''')
            inserted_count = cursor_stock.rowcount
            cursor_stock.execute('SELECT COUNT(*) FROM stock_prices')
            after_insert_rows = cursor_stock.fetchone()[0]
            logger.info(f"stock_info.db 삽입 후 행 수: {after_insert_rows:,} (삽입된 행: {inserted_count:,})")

            # 3) 중복 제거: trading_date + ticker 기준, 가장 먼저 들어온 행만 남김
            cursor_stock.execute('''
                DELETE FROM stock_prices
                WHERE rowid NOT IN (
                    SELECT MIN(rowid)
                    FROM stock_prices
                    GROUP BY trading_date, ticker
                )
            ''')
            deleted_count = conn_stock.total_changes
            cursor_stock.execute('SELECT COUNT(*) FROM stock_prices')
            after_delete_rows = cursor_stock.fetchone()[0]
            conn_stock.commit()
            conn_stock.close()
            logger.info(f"중복 제거 후 행 수: {after_delete_rows:,} (삭제된 중복: {deleted_count:,})")

        return True

    except sqlite3.Error as e:
        logger.error(f"SQLite 오류: {e}")
        return False
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}")
        return False

if __name__ == "__main__":
    success = merge_new_data(
        target_ti_db_path="/home/sese/Flow-Agent/Clova-FinAgent/technical_indicators.db",
        target_stock_db_path="/home/sese/Flow-Agent/Clova-FinAgent/stock_info.db",
        source_ti_db_path="/home/sese/Flow-Agent/data_pipeline/technical_indicators_20251013.db",
        source_stock_db_path="/home/sese/Flow-Agent/data_pipeline/stock_info_20251013.db"
    )
    if success:
        print("✅ 데이터 병합 및 중복 제거 완료!")
    else:
        print("❌ 데이터 병합 중 오류 발생!")
# nohup python pipeline_merge_from_orig.py > log/251013_merge.log 2>&1 &
