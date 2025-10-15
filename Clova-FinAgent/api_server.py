import os
import sys
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import logging
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from core.database_manager import DatabaseManager
from agents.stock_search_agent import StockSearchAgent

# Stock Analyzer imports
sys.path.insert(0, os.path.join(project_root, "stock_analyzer"))
from src.news_searcher import NewsSearcher
from src.ai_analyzer import AIAnalyzer

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="Stock Search API",
    description="주식 정보 검색을 위한 AI 에이전트 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 운영환경에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 요청/응답 모델 정의
class StockSearchRequest(BaseModel):
    question: str
    
class StockSearchResponse(BaseModel):
    answer: str

# Stock Analyzer 모델
class StockAnalysisRequest(BaseModel):
    stock_name: str
    news_count: int = 10

class StockAnalysisResponse(BaseModel):
    stock_name: str
    analysis_result: str
    news_count: int
    status: str
    timestamp: str

# 전역 변수로 에이전트 인스턴스 저장
stock_agent = None
news_searcher = None
ai_analyzer = None

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기화"""
    global stock_agent, news_searcher, ai_analyzer
    try:
        logger.info("Stock Search Agent 초기화 중...")
        
        # 데이터베이스 매니저 초기화
        db_manager = DatabaseManager(
            company_csv_path=os.path.join(project_root, "company_info.csv"),
            stock_db_path=os.path.join(project_root, "stock_info.db"), 
            market_db_path=os.path.join(project_root, "market_index.db"),
            technical_db_path=os.path.join(project_root, "technical_indicators.db")
        )
        
        # 주식 검색 에이전트 초기화
        stock_agent = StockSearchAgent(db_manager)
        logger.info("Stock Search Agent 초기화 완료")
        
        # Stock Analyzer 초기화
        logger.info("Stock Analyzer 초기화 중...")
        news_searcher = NewsSearcher()
        ai_analyzer = AIAnalyzer()
        logger.info("Stock Analyzer 초기화 완료")
        
    except Exception as e:
        logger.error(f"초기화 중 오류 발생: {str(e)}")
        raise e

@app.get("/")
async def root():
    """API 상태 확인"""
    return {
        "message": "Stock Search API Server",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "agent_initialized": stock_agent is not None
    }

@app.post("/search", response_model=StockSearchResponse)
async def search_stock(
    request: StockSearchRequest,
    authorization: str = Header(None, alias="Authorization"),
    request_id: str = Header(None, alias="X-NCP-CLOVASTUDIO-REQUEST-ID")
):
    """주식 정보 검색 API (간단한 형식)"""
    try:
        if not stock_agent:
            raise HTTPException(status_code=500, detail="Agent가 초기화되지 않았습니다.")
        
        if not request.question:
            raise HTTPException(status_code=400, detail="question 필드가 필요합니다.")
        
        logger.info(f"검색 요청: {request.question}")
        
        # 주식 검색 실행
        result = stock_agent.search(request.question)
        
        logger.info(f"검색 결과: {len(result)}자 응답 생성\n{result}\n############   검색 완료    ############")
        
        return StockSearchResponse(answer=result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"검색 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search", response_model=StockSearchResponse)
async def search_stock_get(
    question: str = Query(..., alias="question", description="검색할 주식 정보 질문")
):
    """주식 정보 검색 API (GET 방식, 간단한 형식)"""
    try:
        if not stock_agent:
            raise HTTPException(status_code=500, detail="Agent가 초기화되지 않았습니다.")
        
        if not question:
            raise HTTPException(status_code=400, detail="question 파라미터가 필요합니다.")
        
        logger.info(f"GET 검색 요청: {question}")
        
        # 주식 검색 실행
        result = stock_agent.search(question)
        
        logger.info(f"GET 검색 완료: {len(result)}자 응답 생성")
        
        return StockSearchResponse(answer=result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GET 검색 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tools")
async def get_available_tools():
    """사용 가능한 도구 목록 조회"""
    if not stock_agent:
        raise HTTPException(status_code=500, detail="Agent가 초기화되지 않았습니다.")
    
    tools_info = []
    for tool in stock_agent.tools:
        tools_info.append({
            "name": tool.name,
            "description": tool.description
        })
    
    return {
        "tools": tools_info,
        "total_count": len(tools_info)
    }

@app.post("/analyze", response_model=StockAnalysisResponse)
async def analyze_stock(request: StockAnalysisRequest):
    """
    주식 매수/매도 판단 분석
    
    사용 예시:
    curl -X POST "http://211.188.48.167:8000/analyze" \
         -H "Content-Type: application/json" \
         -d '{"stock_name": "삼성전자", "news_count": 10}'
    """
    try:
        if not news_searcher or not ai_analyzer:
            raise HTTPException(status_code=500, detail="Stock Analyzer가 초기화되지 않았습니다.")
        
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

if __name__ == "__main__":
    print(f"현재 작업 디렉토리: {os.getcwd()}")
    print(f"프로젝트 루트: {project_root}")
    
    # 필수 파일 존재 확인
    required_files = [
        "company_info.csv",
        "stock_info.db", 
        "market_index.db",
        "technical_indicators.db"
    ]
    
    for file_name in required_files:
        file_path = os.path.join(project_root, file_name)
        if os.path.exists(file_path):
            print(f"✓ {file_name} 존재")
        else:
            print(f"✗ {file_name} 없음: {file_path}")
    
    # 서버 실행
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 