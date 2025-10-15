"""
Stock Analyzer 설정 파일
"""

import os

# API Keys
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# API URLs
NAVER_NEWS_API_URL = "https://openapi.naver.com/v1/search/news.json"

# 기본 설정
DEFAULT_DISPLAY = 20
MAX_DISPLAY = 100
DEFAULT_SORT = "date"  # sim: 정확도순, date: 날짜순

# LLM 설정
LLM_MODEL = "gemini-2.0-flash-exp"
LLM_TEMPERATURE = 0.1

# FastAPI 설정
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000

# 프롬프트 파일 경로
PROMPTS_FILE = "prompts/prompts.yaml"