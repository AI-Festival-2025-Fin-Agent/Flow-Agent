"""
AI 분석 모듈
"""

import yaml
import logging
from typing import Dict, Any
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

from config.settings import GOOGLE_API_KEY, LLM_MODEL, LLM_TEMPERATURE, PROMPTS_FILE

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """AI 기반 뉴스 분석 클래스"""

    def __init__(self):
        """초기화"""
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            api_key=GOOGLE_API_KEY,
        )
        self.prompts = self._load_prompts()

    def _load_prompts(self) -> Dict[str, Any]:
        """YAML 프롬프트 파일 로드"""
        try:
            prompts_path = Path(__file__).parent.parent / PROMPTS_FILE
            with open(prompts_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"프롬프트 파일 로드 실패: {e}")
            return {}

    def _create_prompt_template(self, prompt_name: str) -> PromptTemplate:
        """프롬프트 템플릿 생성"""
        if prompt_name not in self.prompts:
            raise ValueError(f"프롬프트 '{prompt_name}'을 찾을 수 없습니다.")
        
        prompt_config = self.prompts[prompt_name]
        return PromptTemplate(
            template=prompt_config['template'],
            input_variables=prompt_config['input_variables']
        )

    def analyze_news(self, news_text: str) -> str:
        """개별 뉴스 분석"""
        try:
            prompt_template = self._create_prompt_template('news_analysis')
            chain = prompt_template | self.llm
            result = chain.invoke({"news_text": news_text})
            return result.content
        except Exception as e:
            logger.error(f"뉴스 분석 중 오류: {e}")
            return f"❌ 뉴스 분석 중 오류 발생: {str(e)}"

    def analyze_investment_summary(self, stock_name: str, news_list: str) -> str:
        """종합 투자 의견 분석"""
        try:
            prompt_template = self._create_prompt_template('investment_summary')
            chain = prompt_template | self.llm
            result = chain.invoke({"stock_name": stock_name, "news_list": news_list})
            return result.content
        except Exception as e:
            logger.error(f"투자 의견 분석 중 오류: {e}")
            return f"❌ 투자 의견 분석 중 오류 발생: {str(e)}"

    def analyze_buy_sell_decision(self, stock_name: str, news_list: str) -> str:
        """매수/매도 판단 분석"""
        try:
            # 개별 뉴스들을 먼저 간단히 분석
            analysis_details = self._analyze_news_details(news_list)
            
            prompt_template = self._create_prompt_template('buy_sell_analysis')
            chain = prompt_template | self.llm
            result = chain.invoke({
                "stock_name": stock_name,
                "news_list": news_list,
                "analysis_details": analysis_details
            })
            return result.content
        except Exception as e:
            logger.error(f"매수/매도 분석 중 오류: {e}")
            return f"❌ 매수/매도 분석 중 오류 발생: {str(e)}"

    def _analyze_news_details(self, news_list: str) -> str:
        """뉴스별 상세 분석"""
        try:
            # 간단한 뉴스별 감성 분석을 위한 프롬프트
            simple_prompt = """다음 뉴스들을 각각 분석해서 간단히 정리해주세요:

{news_list}

각 뉴스별로 다음 형식으로:
1. [뉴스 제목 요약] → 감성: 긍정/부정/중립, 영향: 상승요인/하락요인/중립
2. [뉴스 제목 요약] → 감성: 긍정/부정/중립, 영향: 상승요인/하락요인/중립
...
"""
            
            result = self.llm.invoke(simple_prompt.format(news_list=news_list))
            return result.content
        except Exception as e:
            logger.error(f"뉴스 상세 분석 중 오류: {e}")
            return "뉴스별 세부 분석 진행 중..."