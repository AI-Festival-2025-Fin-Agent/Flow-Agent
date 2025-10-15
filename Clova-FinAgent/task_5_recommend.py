#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
주식 뉴스 검색 및 AI 분석 시스템
"""

import requests
import urllib.parse
import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

# FastAPI imports
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# API Keys and URLs
NAVER_CLIENT_ID = "R5oZk9ZlnNsDxeUJdCnB"
NAVER_CLIENT_SECRET = "qQX4cGNs2V"
NAVER_NEWS_API_URL = "https://openapi.naver.com/v1/search/news.json"
GOOGLE_API_KEY = "AIzaSyCRUhHFdJVX7GXrYi1KOos1WotZIAqRjS4"

# 기본 설정
DEFAULT_DISPLAY = 10
MAX_DISPLAY = 100
DEFAULT_SORT = "sim"

# 주요 주식 종목 리스트
MAJOR_STOCKS = {
    "삼성전자": "005930",
    "SK하이닉스": "000660",
    "NAVER": "035420",
    "카카오": "035720",
    "LG에너지솔루션": "373220",
    "삼성바이오로직스": "207940",
    "현대차": "005380",
    "셀트리온": "068270",
    "POSCO홀딩스": "005490",
    "KB금융": "105560"
}

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NewsSearcher:
    """네이버 뉴스 검색 클래스"""

    def __init__(self, client_id: str = None, client_secret: str = None):
        """초기화"""
        self.client_id = client_id or NAVER_CLIENT_ID
        self.client_secret = client_secret or NAVER_CLIENT_SECRET

        if not self.client_id or not self.client_secret:
            raise ValueError("네이버 API 클라이언트 ID와 시크릿을 설정해주세요.")

    def search_news(self, query: str, display: int = 100, start: int = 1, sort: str = "sim") -> Dict:
        """뉴스 검색"""
        encoded_query = urllib.parse.quote(query)
        url = f"{NAVER_NEWS_API_URL}?query={encoded_query}&display={display}&start={start}&sort={sort}"
        
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
            "User-Agent": "StockNewsSearcher/1.0"
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"뉴스 검색 중 오류 발생: {e}")

    def search_stock_news(self, stock_name: str, display: int = 100, sort: str = "sim") -> Dict:
        """주식 종목 뉴스 검색"""
        search_query = f"{stock_name} 주식"
        return self.search_news(search_query, display, sort=sort)

    @staticmethod
    def clean_html_tags(text: str) -> str:
        """HTML 태그 제거"""
        if not text:
            return ""
        cleaned = re.sub(r'<[^>]+>', '', text)
        return cleaned.strip()

    @staticmethod
    def format_news_item(item: Dict) -> Dict:
        """뉴스 아이템 포맷팅"""
        return {
            'title': NewsSearcher.clean_html_tags(item.get('title', '')),
            'description': NewsSearcher.clean_html_tags(item.get('description', '')),
            'link': item.get('link', ''),
            'original_link': item.get('originallink', ''),
            'pub_date': item.get('pubDate', ''),
            'formatted_date': NewsSearcher.format_date(item.get('pubDate', ''))
        }

    @staticmethod
    def format_date(date_str: str) -> str:
        """날짜 포맷팅"""
        if not date_str:
            return ""
        try:
            from dateutil import parser
            dt = parser.parse(date_str)
            return dt.strftime("%Y-%m-%d %H:%M")
        except:
            return date_str 