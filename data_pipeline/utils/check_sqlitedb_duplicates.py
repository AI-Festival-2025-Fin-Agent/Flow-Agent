import sqlite3
from pathlib import Path

db_path = "/home/sese/Clova-FinAgent/stock_info.db"

if not Path(db_path).exists():
    print(f"파일이 존재하지 않습니다: {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 중복된 trading_date + ticker 확인
    cursor.execute('''
        SELECT trading_date, ticker, COUNT(*) as cnt
        FROM stock_prices
        GROUP BY trading_date, ticker
        HAVING cnt > 1
        ORDER BY cnt DESC
    ''')
    
    duplicates = cursor.fetchall()
    
    if duplicates:
        total_duplicates = sum(cnt - 1 for _, _, cnt in duplicates)  # 중복된 행 수 계산
        print(f"총 중복된 행 수: {total_duplicates}")
        print(f"{'trading_date':<12} {'ticker':<10} {'count':<5}")
        print("-"*30)
        for trading_date, ticker, cnt in duplicates[:20]:  # 상위 20개만 표시
            print(f"{trading_date:<12} {ticker:<10} {cnt:<5}")
    else:
        print("중복된 행이 없습니다.")
    
    conn.close()
