# -*- coding: utf-8 -*-
import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from langchain.tools import Tool
from langchain_naver import ChatClovaX
from langchain.schema import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

from core.database_manager import DatabaseManager
from core.query_parser import QueryParser
from agents.stock_search_agent import StockSearchAgent

# .env 파일 로드
load_dotenv()

class StockSearchState(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    result: str
    tool_calls: List[Dict[str, Any]]
    iterations: int
    validation_status: str
    clarification_needed: bool
    retry_count: int
    execution_log: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    node_traces: List[Dict[str, Any]]
    state_history: List[Dict[str, Any]]
    current_tool_index: int
    pending_tools: List[Dict[str, Any]]
    completed_tools: List[Dict[str, Any]]
    tool_execution_results: List[str]

class ParsingAgent:
    """Parse까지만 하는 간단한 에이전트"""

    def __init__(self, db_manager: DatabaseManager, enable_detailed_logging: bool = True):
        self.db_manager = db_manager
        self.enable_detailed_logging = enable_detailed_logging

        # 네이버 클로바 API 키 가져오기
        api_key = os.getenv("CLOVASTUDIO_API_KEY")
        if not api_key:
            raise ValueError("CLOVASTUDIO_API_KEY가 .env 파일에 설정되지 않았습니다.")

        self.llm_main = ChatClovaX(
            api_key=api_key,
            model="HCX-007",
            temperature=0.1
        )

        self.llm_simple = ChatClovaX(
            api_key=api_key,
            model="HCX-005",
            temperature=0.1
        )

        self.query_parser = QueryParser(self.llm_simple, db_manager)
        self.tools = self._create_tools()
        self.graph = self._create_graph()

    def _create_tools(self) -> List[Tool]:
        """원본 에이전트의 도구 생성 메서드 사용"""
        # 임시 원본 에이전트 생성해서 도구 가져오기
        temp_agent = StockSearchAgent(self.db_manager, enable_detailed_logging=False)
        return temp_agent._create_tools()

    def _parse_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        """원본 에이전트의 파싱 메서드 사용"""
        # 임시 원본 에이전트 생성해서 파싱 메서드 사용
        temp_agent = StockSearchAgent(self.db_manager, enable_detailed_logging=False)
        return temp_agent._parse_tool_calls(content)

    def _create_graph(self) -> StateGraph:
        """Parse까지만 하는 간단한 그래프"""

        tools = self.tools
        llm_main = self.llm_main

        def agent_node(state: StockSearchState) -> StockSearchState:
            """LLM 에이전트 노드"""
            messages = state["messages"]
            query = state["query"]

            print(f"[AGENT] LLM 에이전트: 질문 분석 중...")

            # 도구 설명 생성
            tool_descriptions = []
            for tool in tools:
                tool_descriptions.append(f"- {tool.name}: {tool.description}")

            tools_text = "\n".join(tool_descriptions)

            today = datetime.today()
            today_str = today.strftime('%Y-%m-%d')
            weekdays_kr = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
            weekday_kr = weekdays_kr[today.weekday()]

            prompt = f"""당신은 주식 정보 검색 전문가입니다. 사용자의 질문을 신중히 분석한 후 적절한 도구를 사용하세요.
참고: 오늘 날짜는 {today_str} ({weekday_kr})입니다.

**사용 가능한 도구들:**
{tools_text}

**응답 형식:**
도구가 필요한 경우 반드시 다음 형식을 사용하세요:
TOOL_CALL: {{"name": "도구명", "args": "인수"}}

**사용자 질문:** {query}

질문을 분석하고 필요한 도구를 호출하세요."""

            # LLM 응답 생성
            messages_for_llm = [HumanMessage(content=prompt)]
            response = llm_main.invoke(messages_for_llm)

            print(f"[LLM_RESPONSE] LLM 원본 응답: {response.content}")

            # 메시지 추가
            new_messages = messages + [HumanMessage(content=query), response]

            return {
                **state,
                "messages": new_messages
            }

        def parse_node(state: StockSearchState) -> StockSearchState:
            """도구 호출 파싱 노드"""
            messages = state["messages"]

            # 마지막 AI 메시지에서 도구 호출 파싱
            ai_response = ""
            for message in reversed(messages):
                if isinstance(message, AIMessage):
                    ai_response = message.content
                    break

            print(f"[PARSE] AI 응답에서 도구 호출 파싱 중...")

            # 도구 호출 파싱
            tool_calls = self._parse_tool_calls(ai_response)

            print(f"[PARSE] 파싱된 도구 호출: {len(tool_calls)}개")
            for i, tool_call in enumerate(tool_calls):
                print(f"[TOOL_CALL_{i}] {tool_call}")

            return {
                **state,
                "tool_calls": tool_calls
            }

        # 워크플로우 구성
        workflow = StateGraph(StockSearchState)

        # 노드 추가 (agent와 parse만)
        workflow.add_node("agent", agent_node)
        workflow.add_node("parse", parse_node)

        # 시작점 설정
        workflow.set_entry_point("agent")

        # 연결: agent → parse → END
        workflow.add_edge("agent", "parse")
        workflow.add_edge("parse", END)

        print("[GRAPH] 2개 노드 생성: agent → parse → END")

        return workflow.compile()

def test_parsing_agent():
    """ParsingAgent 테스트"""
    from core.database_manager import DatabaseManager

    # 데이터베이스 매니저 초기화
    db_manager = DatabaseManager(
        company_csv_path=os.path.join(project_root, "company_info.csv"),
        stock_db_path=os.path.join(project_root, "stock_info.db"),
        market_db_path=os.path.join(project_root, "market_index.db"),
        technical_db_path=os.path.join(project_root, "technical_indicators.db")
    )

    # 파싱 에이전트 초기화
    agent = ParsingAgent(db_manager)

    # 테스트 쿼리
    test_query = "삼성전자 2024-11-06 주가는?"

    # 초기 상태
    initial_state = StockSearchState(
        messages=[],
        query=test_query,
        result="",
        tool_calls=[],
        iterations=0,
        validation_status="pending",
        clarification_needed=False,
        retry_count=0,
        execution_log=[],
        tool_results=[],
        node_traces=[],
        state_history=[],
        current_tool_index=0,
        pending_tools=[],
        completed_tools=[],
        tool_execution_results=[]
    )

    # 그래프 실행
    final_state = None
    for step in agent.graph.stream(initial_state):
        for node_name, state in step.items():
            if node_name == "parse":
                final_state = state
                break

    # 결과 출력
    if final_state:
        tool_calls = final_state.get('tool_calls', [])
        print(f"\n=== 파싱 결과 ===")
        print(f"파싱된 도구: {len(tool_calls)}개")
        for i, tool in enumerate(tool_calls):
            print(f"  [{i+1}] {tool.get('name', 'Unknown')}: {tool.get('args', 'None')}")

if __name__ == "__main__":
    test_parsing_agent()