import yfinance as yf


ticker = "005930.KS"
tmp = yf.download(ticker, period='1mo', progress=False, auto_adjust=False)
print(tmp)


print()
x = yf.download(ticker, start="2025-09-29", end="2025-09-30", interval="1d")
print(x)