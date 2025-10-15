import pandas as pd
import yfinance as yf
from tqdm import tqdm
import pickle
import sqlite3
from datetime import datetime

def main():
    # ---------------------------
    # 1) 기본 설정
    # ---------------------------
    today_str = datetime.now().strftime('%Y%m%d')

    # company info 불러오기
    company_df = pd.read_csv("/home/sese/Flow-Agent/data_pipeline/company_info.csv")
    print(company_df.head())
    tickers = company_df['ticker'].tolist()
    print(tickers[:2])

    # ---------------------------
    # 2) Yahoo Finance 데이터 다운로드
    # ---------------------------
    all_tmp = []
    for ticker in tqdm(tickers):
        tmp = yf.download(ticker, period='1mo', progress=False, auto_adjust=False)
        all_tmp.append(tmp)

    # ---------------------------
    # 3) pickle 저장
    # ---------------------------
    pickle_filename = f"all_tmp_{today_str}.pkl"
    with open(pickle_filename, "wb") as f:
        pickle.dump(all_tmp, f)
    print(f"Pickle 저장 완료: {pickle_filename}")

    # ---------------------------
    # 4) CSV 파일로 첫 종목 저장
    # ---------------------------
    all_tmp[0].to_csv(f"all_tmp_{today_str}.csv")
    print(f"CSV 저장 완료: all_tmp_{today_str}.csv")

    # ---------------------------
    # 5) 데이터 전처리 및 SQLite 저장
    # ---------------------------
    company_map = {row['ticker']: row['stock_name'] for _, row in company_df.iterrows()}
    db_path = f'stock_info_{today_str}.db'
    conn = sqlite3.connect(db_path)

    all_stock_dfs = []
    for df in all_tmp:
        df_copy = df.copy()

        # 컬럼 평탄화 & 티커 추출
        if isinstance(df_copy.columns, pd.MultiIndex):
            df_copy.columns = df_copy.columns.droplevel(1)
            ticker = df.columns.get_level_values(1)[0]
        else:
            ticker = df_copy.attrs.get('ticker', 'UNKNOWN')

        # 컬럼명 정리
        df_copy = df_copy.rename(columns={
            'Price': 'adj_close_price',
            'Adj Close': 'adj_close_price',
            'Close': 'close_price',
            'High': 'high_price',
            'Low': 'low_price',
            'Open': 'open_price',
            'Volume': 'trading_volume',
        })

        df_copy.reset_index(inplace=True)
        df_copy.rename(columns={'Date': 'trading_date'}, inplace=True)
        df_copy['trading_date'] = pd.to_datetime(df_copy['trading_date']).dt.date

        # 파생 컬럼 계산
        df_copy['prev_close_price'] = df_copy['close_price'].shift(1)
        df_copy['change'] = df_copy['close_price'] - df_copy['prev_close_price']
        df_copy['change_rate'] = df_copy['change'] / df_copy['prev_close_price'] * 100

        # 티커/기타 정보 추가
        df_copy['ticker'] = ticker
        df_copy['stock_name'] = company_map.get(ticker, 'UNKNOWN')
        df_copy['market'] = 'KOSPI' if ticker.endswith('S') else 'KOSDAQ'

        all_stock_dfs.append(df_copy)

    final_df = pd.concat(all_stock_dfs, ignore_index=True)
    final_df.to_sql('stock_prices', conn, if_exists='replace', index=False)
    conn.close()

    print(f"SQLite DB '{db_path}'에 모든 종목 데이터 저장 완료!")
    print(f"최종 shape: {final_df.shape}")

# ---------------------------
# 실행부
# ---------------------------
if __name__ == "__main__":
    main()
#  nohup python pipeline_download_yfinance.py > log/251013.log 2>&1 &