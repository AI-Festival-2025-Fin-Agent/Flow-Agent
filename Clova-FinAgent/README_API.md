# Stock Search REST API

주식 정보 검색을 위한 AI 에이전트 REST API 서버입니다.

## 설치 및 실행

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정
`.env.example` 파일을 복사하여 `.env` 파일을 생성하고 API 키를 설정하세요.

```bash
cp .env.example .env
# .env 파일에서 NAVER_CLOVA_API_KEY 값을 실제 API 키로 변경
```

### 3. 서버 실행
```bash
python api_server.py
```

또는

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

## API 엔드포인트

### 1. 서버 상태 확인
- **GET** `/`
- **GET** `/health`

### 2. 주식 정보 검색
- **POST** `/search`

**요청 예시:**
```json
{
    "query": "삼성전자의 2024-11-06 종가는?"
}
```

**응답 예시:**
```json
{
    "result": "삼성전자의 2024년 11월 6일 종가는 58,600원입니다.",
    "success": true,
    "error": null
}
```

### 3. 사용 가능한 도구 목록 조회
- **GET** `/tools`

## 사용 예시

### curl 명령어
```bash
# 주식 가격 조회
curl -X POST "http://localhost:8000/search" \
     -H "Content-Type: application/json" \
     -d '{"query": "삼성전자의 최근 주가는?"}'

# 상승률 순위 조회
curl -X POST "http://localhost:8000/search" \
     -H "Content-Type: application/json" \
     -d '{"query": "2024-11-06 상승률 1위는?"}'

# RSI 과매수 종목 검색
curl -X POST "http://localhost:8000/search" \
     -H "Content-Type: application/json" \
     -d '{"query": "2024-11-06에 RSI가 70 이상인 과매수 종목을 알려줘"}'
```

### Python 클라이언트 예시
```python
import requests
import json

url = "http://localhost:8000/search"
headers = {"Content-Type": "application/json"}

# 검색 요청
data = {
    "query": "삼성전자의 2024-11-06 종가는?"
}

response = requests.post(url, headers=headers, json=data)
result = response.json()

print(f"성공: {result['success']}")
print(f"결과: {result['result']}")
```

## 지원하는 검색 유형

1. **주가 정보**: "삼성전자 주가", "005930 종가"
2. **순위 정보**: "상승률 1위", "거래량 순위"
3. **시장 통계**: "시장 통계", "상승/하락 종목수"
4. **기술적 지표**: "RSI 과매수", "볼린저 밴드", "이동평균 돌파"
5. **거래량 분석**: "거래량 급증", "거래대금 순위"
6. **조건부 검색**: "가격대별 종목", "거래량 임계값"

## 주의사항

- API 키가 정확히 설정되어야 합니다.
- 필수 데이터베이스 파일들이 존재해야 합니다:
  - `company_info.csv`
  - `stock_info.db`
  - `market_index.db` 
  - `technical_indicators.db`

## API 문서

서버 실행 후 다음 URL에서 자동 생성된 API 문서를 확인할 수 있습니다:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc` 