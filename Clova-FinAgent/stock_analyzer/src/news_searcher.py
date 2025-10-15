"""
네이버 뉴스 검색 모듈
"""

import requests
import urllib.parse
import re
from datetime import datetime
from typing import Dict, List
from dateutil import parser

from config.settings import (
    NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NAVER_NEWS_API_URL,
    DEFAULT_DISPLAY, DEFAULT_SORT
)


class NewsSearcher:
    """네이버 뉴스 검색 클래스"""

    def __init__(self, client_id: str = None, client_secret: str = None):
        """초기화"""
        self.client_id = client_id or NAVER_CLIENT_ID
        self.client_secret = client_secret or NAVER_CLIENT_SECRET

        if not self.client_id or not self.client_secret:
            raise ValueError("네이버 API 클라이언트 ID와 시크릿을 설정해주세요.")

    def search_news(
        self, 
        query: str, 
        display: int = DEFAULT_DISPLAY, 
        start: int = 1, 
        sort: str = DEFAULT_SORT
    ) -> Dict:
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

    def search_stock_news(self, stock_name: str, display: int = DEFAULT_DISPLAY, sort: str = DEFAULT_SORT) -> Dict:
        """주식 종목 뉴스 검색"""
        search_query = f"{stock_name} 주식"
        return self.search_news(search_query, display, sort=sort)

    def search_market_news(self, display: int = 30) -> Dict:
        """전체 주식 시장 뉴스 검색"""
        search_query = "주식 시장 코스피 코스닥"
        return self.search_news(search_query, display, sort="date")

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
            dt = parser.parse(date_str)
            return dt.strftime("%Y-%m-%d %H:%M")
        except:
            return date_str