import sqlite3
from pathlib import Path

db_path = "/home/sese/Clova-FinAgent/stock_info.db"

if not Path(db_path).exists():
    print(f"파일이 존재하지 않습니다: {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 중복된 trading_date + ticker 중 가장 오래된 행 삭제
    cursor.execute('''
        DELETE FROM stock_prices
        WHERE rowid NOT IN (
            SELECT MAX(rowid)
            FROM stock_prices
            GROUP BY trading_date, ticker
        )
    ''')
    
    deleted_count = conn.total_changes
    conn.commit()
    print(f"총 {deleted_count}개의 중복 행 삭제 완료")
    
    conn.close()
