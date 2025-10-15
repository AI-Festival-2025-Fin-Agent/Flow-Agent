print('============`finance_datareader.py`============')

import FinanceDataReader as fdr
from datetime import datetime
print(datetime.now())

print(fdr.__version__)
df = fdr.DataReader('KS11', '2020') 
print(df)
df_krx = fdr.StockListing('KRX')
print(df_krx)
with open("krx_list.csv", "w") as f:
    df_krx.to_csv(f)