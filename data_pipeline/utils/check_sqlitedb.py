import sqlite3
import pandas as pd

# DB 연결
conn = sqlite3.connect("/home/sese/Clova-FinAgent/stock_info.db")  # SQLite 파일 경로
#conn = sqlite3.connect("/home/sese/data_pipeline/stock_info.db")  # SQLite 파일 경로
# 연결 확인
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(stock_prices);")
columns = cursor.fetchall()
column_names = [col[1] for col in columns]
print(column_names)

print('\n\n')
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", tables)


cursor.execute("PRAGMA table_info(stock_prices);")
print('\n\n')
columns = cursor.fetchall()

# 컬럼 이름만 추출
column_names = [col[1] for col in columns]
print(column_names)



# SQL 쿼리로 조회
print('\n\n')
df = pd.read_sql_query("SELECT * FROM stock_prices LIMIT 5;", conn)
print(df)
