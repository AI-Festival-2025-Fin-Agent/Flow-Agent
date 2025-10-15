"""
주식 뉴스 분석 시스템 메인 파일
"""

import logging
from datetime import datetime
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from src.news_searcher import NewsSearcher
from src.ai_analyzer import AIAnalyzer
from config.settings import SERVER_HOST, SERVER_PORT

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="📊 Stock Analysis API",
    description="주식 뉴스 기반 매수/매도 판단 API",
    version="1.0.0"
)

# 전역 인스턴스
news_searcher = NewsSearcher()
ai_analyzer = AIAnalyzer()


# 요청/응답 모델
class StockAnalysisRequest(BaseModel):
    stock_name: str
    news_count: int = 10


class StockAnalysisResponse(BaseModel):
    stock_name: str
    analysis_result: str
    news_count: int
    status: str
    timestamp: str


@app.get("/")
async def root():
    """API 상태 확인"""
    return {
        "message": "📊 Stock Analysis API",
        "status": "running",
        "endpoints": {
            "analyze": "/analyze - 종목 매수/매도 분석",
            "health": "/health - 헬스 체크"
        }
    }


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/analyze", response_model=StockAnalysisResponse)
async def analyze_stock(request: StockAnalysisRequest):
    """
    주식 매수/매도 판단 분석
    
    사용 예시:
    curl -X POST "http://localhost:8000/analyze" \
         -H "Content-Type: application/json" \
         -d '{"stock_name": "삼성전자", "news_count": 10}'
    """
    try:
        stock_name = request.stock_name.strip()
        
        if not stock_name:
            raise HTTPException(status_code=400, detail="종목명을 입력해주세요.")
        
        logger.info(f"🔍 {stock_name} 분석 시작")
        
        # 1. 뉴스 검색
        news_results = news_searcher.search_stock_news(
            stock_name, 
            display=request.news_count, 
            sort="date"
        )
        
        if not news_results or 'items' not in news_results or len(news_results['items']) == 0:
            return StockAnalysisResponse(
                stock_name=stock_name,
                analysis_result="❌ 관련 뉴스를 찾을 수 없습니다. 종목명을 확인해주세요.",
                news_count=0,
                status="no_news",
                timestamp=datetime.now().isoformat()
            )
        
        # 2. 뉴스 목록 정리
        news_list = ""
        for i, item in enumerate(news_results['items'], 1):
            formatted_item = news_searcher.format_news_item(item)
            news_list += f"{i}. 제목: {formatted_item['title']}\n"
            news_list += f"   내용: {formatted_item['description']}\n"
            news_list += f"   날짜: {formatted_item['formatted_date']}\n\n"
        
        # 3. AI 분석 실행
        analysis_result = ai_analyzer.analyze_buy_sell_decision(stock_name, news_list)
        
        logger.info(f"✅ {stock_name} 분석 완료")
        
        return StockAnalysisResponse(
            stock_name=stock_name,
            analysis_result=analysis_result,
            news_count=len(news_results['items']),
            status="success",
            timestamp=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"분석 중 오류 발생: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        return StockAnalysisResponse(
            stock_name=request.stock_name,
            analysis_result=f"❌ {error_msg}",
            news_count=0,
            status="error",
            timestamp=datetime.now().isoformat()
        )


def analyze_stock_cli(stock_name: str, news_count: int = 10):
    """CLI용 분석 함수"""
    try:
        print(f"🔍 {stock_name} 뉴스 분석 중...")
        
        # 뉴스 검색
        news_results = news_searcher.search_stock_news(stock_name, display=news_count, sort="date")
        
        if not news_results or 'items' not in news_results or len(news_results['items']) == 0:
            print("❌ 관련 뉴스를 찾을 수 없습니다.")
            return
        
        print(f"📰 {len(news_results['items'])}개 뉴스 발견")
        
        # 뉴스 목록 정리
        news_list = ""
        for i, item in enumerate(news_results['items'], 1):
            formatted_item = news_searcher.format_news_item(item)
            news_list += f"{i}. 제목: {formatted_item['title']}\n"
            news_list += f"   내용: {formatted_item['description']}\n"
            news_list += f"   날짜: {formatted_item['formatted_date']}\n\n"
        
        # AI 분석
        print("🤖 AI 분석 중...")
        analysis_result = ai_analyzer.analyze_buy_sell_decision(stock_name, news_list)
        
        print("\n" + "="*60)
        print(analysis_result)
        print("="*60)
        
    except Exception as e:
        print(f"❌ 분석 중 오류 발생: {str(e)}")


def run_server(host: str = SERVER_HOST, port: int = SERVER_PORT):
    """서버 실행"""
    print(f"🚀 서버 시작: http://{host}:{port}")
    print("📝 사용법:")
    print(f"   curl -X POST 'http://{host}:{port}/analyze' \\")
    print("        -H 'Content-Type: application/json' \\")
    print("        -d '{\"stock_name\": \"삼성전자\"}'")
    
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # CLI 모드
        stock_name = sys.argv[1]
        news_count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        analyze_stock_cli(stock_name, news_count)
    else:
        # 서버 모드
        run_server()