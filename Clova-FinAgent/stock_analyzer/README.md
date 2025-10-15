# Stock Analyzer

주식 뉴스 기반 매수/매도 판단 AI 분석 시스템

## API 요청 방식

### 종목 분석
```bash
curl -X POST "http://localhost:8000/analyze" \
     -H "Content-Type: application/json" \
     -d '{"stock_name": "삼성전자", "news_count": 10}'
```

### 응답 예시
```json
{
  "stock_name": "삼성전자",
  "analysis_result": "## 📊 삼성전자 투자 분석\n\n### 뉴스 감성 분석\n...",
  "news_count": 10,
  "status": "success",
  "timestamp": "2025-01-31T12:00:00"
}
```

### 헬스 체크
```bash
curl http://localhost:8000/health
```