import re
import os
import json
import sys
import logging
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
from core.text2sql_node import Text2SQLNode

# .env 파일 로드
load_dotenv()




class StockSearchState(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    result: str
    tool_calls: List[Dict[str, Any]]
    iterations: int
    validation_status: str  # "success", "param_missing", "tool_error"
    clarification_needed: bool
    retry_count: int
    # 상세 추적을 위한 새로운 필드들
    execution_log: List[Dict[str, Any]]  # 실행 로그
    tool_results: List[Dict[str, Any]]  # 도구 실행 결과 상세
    node_traces: List[Dict[str, Any]]   # 노드별 실행 추적
    state_history: List[Dict[str, Any]] # 상태 변화 이력
    # 개별 도구 노드 실행을 위한 필드들
    current_tool_index: int  # 현재 실행 중인 도구 인덱스
    pending_tools: List[Dict[str, Any]]  # 실행 대기 중인 도구들
    completed_tools: List[Dict[str, Any]]  # 완료된 도구들
    tool_execution_results: List[str]  # 각 도구 실행 결과들




class StockSearchAgent:
    def __init__(self, db_manager: DatabaseManager, model_name: str = "hcx-005", enable_detailed_logging: bool = True):
        self.db_manager = db_manager
        self.model_name = model_name
        self.enable_detailed_logging = enable_detailed_logging
        
        # 도구별 필터링 필요 여부
        self.TOOLS_NEED_FILTERING = {
            "search_price_change", "search_volume", "search_price", 
            "search_compound", "get_rsi_signals", "get_ma_breakout",
            "get_volume_surge", "get_cross_signals", "text2sql"
        }
        
        # 네이버 클로바 API 키 가져오기
        api_key = os.getenv("CLOVASTUDIO_API_KEY")
        if not api_key:
            raise ValueError("CLOVASTUDIO_API_KEY가 .env 파일에 설정되지 않았습니다.")
        
        # 2단계 모델 설정: 중요한 작업용(HCX-007), 사소한 작업용(HCX-005)
        self.llm_main = ChatClovaX(
            api_key=api_key,
            model="HCX-007",  # 쿼리 분석, 도구 선택 등 중요한 작업
            temperature=0.1
        )
        
        self.llm_simple = ChatClovaX(
            api_key=api_key,
            model="HCX-005",  # 최종 응답 생성 등 사소한 작업
            temperature=0.1
        )
        
        # 통합 쿼리 파서 초기화 (중요한 작업이므로 main 모델 사용) -> rate limit으로 simple 모델
        self.query_parser = QueryParser(self.llm_simple, db_manager)
        
        # TEXT2SQL 노드 초기화 (중요한 작업이므로 main 모델 사용)
        self.text2sql_node = Text2SQLNode(db_manager.stock_db_path, self.llm_main)
        
        self.tools = self._create_tools()
        self.graph = self._create_graph()
    
    def _log_state_change(self, state: StockSearchState, node_name: str, change_description: str) -> StockSearchState:
        """상태 변화 로깅"""
        if not self.enable_detailed_logging:
            return state
            
        timestamp = datetime.now().isoformat()
        
        # 노드 실행 추적
        node_trace = {
            "timestamp": timestamp,
            "node_name": node_name,
            "description": change_description,
            "iterations": state.get("iterations", 0),
            "validation_status": state.get("validation_status", "pending"),
            "tool_calls_count": len(state.get("tool_calls", []))
        }
        
        # 상태 스냅샷
        state_snapshot = {
            "timestamp": timestamp,
            "node_name": node_name,
            "query": state.get("query", ""),
            "result_length": len(str(state.get("result", ""))),
            "iterations": state.get("iterations", 0),
            "validation_status": state.get("validation_status", "pending"),
            "clarification_needed": state.get("clarification_needed", False),
            "retry_count": state.get("retry_count", 0),
            "messages_count": len(state.get("messages", []))
        }
        
        # 로그 추가
        updated_state = {
            **state,
            "node_traces": state.get("node_traces", []) + [node_trace],
            "state_history": state.get("state_history", []) + [state_snapshot]
        }
        
        return updated_state
    
    def _log_execution(self, message: str, level: str = "INFO", extra_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """실행 로그 생성"""
        if not self.enable_detailed_logging:
            return {}
            
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "extra_data": extra_data or {}
        }
        
        return log_entry
    
    
    def _create_tools(self) -> List[Tool]:
        """통합 쿼리 파서 기반 도구 생성"""
        tools = []
        
        # QueryParser의 tool_mappings에서 도구 목록 가져오기
        for tool_name in self.query_parser.tool_mappings.keys():
            # 도구 설명 정의
            descriptions = {
                "get_stock_price": "특정 종목의 특정날짜의 시가/고가/저가/종가/거래량/등락률을 조회합니다. 종목명(삼성전자)이나 코드(005930)로 검색 가능",
                "get_market_index": "시장 지수를 조회합니다. KOSPI나 KOSDAQ 지수값을 날짜별로 조회 가능",
                "get_market_stats": "시장 통계를 조회합니다. 제공 정보: 전체/상승/하락/보합 종목수, KOSPI/KOSDAQ 종목수, 시장 평균 등락률, 최고/최저 등락률, 전체 거래대금, 상승/하락 종목 평균 등락률",

                "search_company": "회사명으로 종목을 검색합니다. 부분 검색도 가능",
                "search_price": "가격 기준 검색을 수행합니다. 가격 순위 조회 및 가격 범위 검색 모두 가능. 시가/고가/저가/종가 지원",
                "search_price_change": "등락률 기준 검색을 수행합니다. 상승률/하락률 순위 조회 및 등락률 범위 검색 모두 가능",
                "search_volume": "거래량 기준 검색을 수행합니다. 거래량 순위 조회 및 거래량 임계값 검색 모두 가능",
                "search_trading_value_ranking": "거래대금 순위를 조회합니다. 거래대금 상위 종목들",

                "get_rsi_signals": "RSI 기반 과매수/과매도 신호를 감지합니다. RSI 70 이상 과매수, 30 이하 과매도 종목 검색",
                "get_bollinger_signals": "볼린저 밴드 상단/하단 터치 종목을 검색합니다. 볼린저 밴드 신호 감지",
                "get_ma_breakout": "이동평균선 돌파 종목을 검색합니다. 5일, 20일, 60일 이동평균 돌파 분석",
                "get_volume_surge": "거래량 급증 종목을 검색합니다. 20일 평균 대비 100%, 200%, 300%, 500% 이상 급증 (※전날대비/어제대비/하루대비는 TEXT2SQL 사용)",

                "get_cross_signals": "특정 기간 동안 골든크로스/데드크로스가 발생한 종목 목록을 검색합니다. '어떤 종목이 데드크로스 발생했는지' 질문에 사용",
                "count_cross_signals": "특정 종목 하나의 골든크로스/데드크로스 발생 횟수를 계산합니다. '삼성전자가 몇 번 데드크로스 발생했는지' 질문에 사용",
                "search_compound": "복합조건 검색을 수행합니다. 가격, 등락률, 거래량, RSI 등 여러 조건을 동시에 만족하는 종목을 검색",
                "text2sql": "복잡한 계산이나 집계가 필요한 쿼리를 처리합니다. 전날대비 비교, 시장 비율 계산, 복잡한 조건 검색 등에 사용",
            }
            
            # Tool 객체 생성
            tool = Tool(
                name=tool_name,
                description=descriptions.get(tool_name, f"{tool_name} 도구"),
                func=lambda query, name=tool_name: self.query_parser.parse_and_execute(name, query)
            )
            tools.append(tool)
            
        print(f"[TOOLS] 통합 쿼리 파서에서 {len(tools)}개 도구 생성 완료")
        return tools


    def agent_node(self, state: StockSearchState) -> StockSearchState:
        """LLM 에이전트 노드"""
        messages = state["messages"]
        query = state["query"]
        
        # 상태 변화 로깅
        state = self._log_state_change(state, "agent_node", "LLM 에이전트 노드 시작")
        
        print(f"[AGENT] LLM 에이전트: 질문 분석 중...")
        
        # 실행 로그 추가
        execution_log = state.get("execution_log", [])
        log_entry = self._log_execution(
            "LLM 에이전트 노드 실행 시작",
            "INFO",
            {
                "query": query,
                "messages_count": len(messages),
                "iterations": state.get("iterations", 0)
            }
        )
        if log_entry:
            execution_log.append(log_entry)
        
        # 도구 설명 생성
        tool_descriptions = []
        for tool in self.tools:
            tool_descriptions.append(f"- {tool.name}: {tool.description}")
        
        tools_text = "\n".join(tool_descriptions)
        
        today = datetime.today()
        today_str = today.strftime('%Y-%m-%d')
        weekday_str = today.strftime('%A')  # 영어 요일, 예: 'Monday'
        # 한국어 요일로 변환하려면
        weekdays_kr = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        weekday_kr = weekdays_kr[today.weekday()]

        prompt = f"""당신은 주식 정보 검색 전문가입니다. 사용자의 질문을 신중히 분석한 후 적절한 도구를 사용하세요.
참고: 오늘 날짜는 {today_str} ({weekday_kr})입니다. 사용자는 이 날짜를 기준으로 질문할 수도 있고, 다른 날짜를 명시할 수도 있습니다. 질문에 명시된 날짜가 있다면 그 날짜를 우선으로 사용하세요.

**질문 분석 및 도구 선택 전략**:
1. **단순 조회**: 1개 도구 사용
2. **비교 질문**: 여러 도구 동시 사용 (권장) - A vs B, 종목 vs 시장평균 등
3. **복잡한 집계**: TEXT2SQL 사용

**비교 질문 처리 예시 (여러 도구 동시 호출)**:
- 종목 vs 시장평균 → TOOL_CALL: {{"name": "get_stock_price", "args": "종목의 등락률"}} + TOOL_CALL: {{"name": "text2sql", "args": "시장 평균 등락률"}}
- A vs B 비교 → TOOL_CALL: {{"name": "get_stock_price", "args": "A 조회"}} + TOOL_CALL: {{"name": "get_stock_price", "args": "B 조회"}}

사용 가능한 도구들:
{tools_text}

사용자 질문: {query}

**도구 호출 형식:**
- 단일 도구: TOOL_CALL: {{"name": "도구명", "args": "질문"}}
- 여러 도구: 각각 별도 줄에 TOOL_CALL 작성

**여러 도구 호출 예시:**
TOOL_CALL: {{"name": "get_stock_price", "args": "삼성전자 2025-11-06 주가"}}
TOOL_CALL: {{"name": "get_stock_price", "args": "SK하이닉스 2025-11-06 주가"}}

**상세 사용 예시**:
- 삼성전자 주가 → TOOL_CALL: {{"name": "get_stock_price", "args": "삼성전자의 2025-11-06 주가는?"}}
- 상승률 순위 → TOOL_CALL: {{"name": "search_price_change", "args": "2025-11-06에 상승률 상위 10개 종목은?"}}
- 하락률 순위 → TOOL_CALL: {{"name": "search_price_change", "args": "2025-09-05에서 KOSDAQ에서 하락률 높은 종목 5개는?"}}
- 회사 검색 → TOOL_CALL: {{"name": "search_company", "args": "SK하이닉스"}}
- RSI 과매수 → TOOL_CALL: {{"name": "get_rsi_signals", "args": "2025-11-06에 RSI가 70 이상인 과매수 종목을 알려줘"}}
- 이동평균 돌파 → TOOL_CALL: {{"name": "get_ma_breakout", "args": "2025-11-06에 종가가 20일 이동평균보다 10% 이상 높은 종목을 알려줘"}}
- 데드크로스 → TOOL_CALL: {{"name": "get_cross_signals", "args": "2025-01-01부터 2025-12-31까지 데드크로스가 발생한 종목을 알려줘"}}
- 거래량 순위 → TOOL_CALL: {{"name": "search_volume", "args": "2025-11-06에 KOSPI 거래량 상위 10개 종목은?"}}
- 거래량 임계값 → TOOL_CALL: {{"name": "search_volume", "args": "2025-11-06에 거래량이 100만주 이상인 종목을 보여줘"}}
- 종목 거래량순위 → TOOL_CALL: {{"name": "search_volume", "args": "삼성전자가 2025-11-06에 거래량 몇 등인지?"}}
- 가격 순위 → TOOL_CALL: {{"name": "search_price", "args": "2025-11-06에 KOSPI에서 가장 비싼 종목 10개는?"}}
- 가격 범위 → TOOL_CALL: {{"name": "search_price", "args": "2025-11-06에 종가가 1만원 이상 5만원 이하인 종목을 보여줘"}}
- 거래량 급증 → TOOL_CALL: {{"name": "get_volume_surge", "args": "2025-11-06에 거래량이 20일 평균 대비 500% 이상 급증한 종목을 알려줘"}}
- KOSDAQ 지수 → TOOL_CALL: {{"name": "get_market_index", "args": "2025-11-06 KOSDAQ 지수는?"}}

**복합조건 질문**:
- 등락률+거래량 → TOOL_CALL: {{"name": "search_compound", "args": "2025-11-06에 등락률이 +3% 이상이면서 거래량이 100만주 이상인 종목은?"}}
- 가격+등락률 → TOOL_CALL: {{"name": "search_compound", "args": "2025-11-06에 종가가 1만원 이상 5만원 이하이면서 등락률이 +2% 이상인 종목은?"}}
- 거래량+가격+RSI → TOOL_CALL: {{"name": "search_compound", "args": "2025-11-06에 거래량이 500만주 이상이면서 종가가 2만원 이하이고 RSI가 70 이상인 종목은?"}}

**TEXT2SQL (복잡한 계산/집계)**:
- 전체 시장 대비 비율 → TOOL_CALL: {{"name": "text2sql", "args": "2025-05-23에 셀트리온 거래량이 전체 시장 거래량의 몇 %인가"}}
- 전날 대비 증감 → TOOL_CALL: {{"name": "text2sql", "args": "2025-01-09에 거래량이 전날대비 300% 이상 증가한 종목을 모두 보여줘"}}

**비교 질문은 여러 도구를 동시에 호출하세요**. 질문에 답할 수 있는 적절한 도구를 선택하거나 TEXT2SQL이 필요한지 판단하여 호출하세요."""



        if '네이버' in prompt:
            prompt+= '\n- 네이버의 종목명은 NAVER입니다.'
        
        # LLM 호출 로그
        llm_log = self._log_execution(
            "LLM 호출 시작",
            "INFO", 
            {"prompt_length": len(prompt)}
        )
        if llm_log:
            execution_log.append(llm_log)

        response = self.llm_main.invoke([HumanMessage(content=prompt)])  # 중요한 작업: HCX-007
        print(f"[LLM_RESPONSE] LLM 원본 응답: {response.content}")
        
        # LLM 응답 로그
        llm_response_log = self._log_execution(
            "LLM 응답 수신",
            "INFO",
            {
                "response_length": len(response.content),
                "response_preview": response.content[:200] + "..." if len(response.content) > 200 else response.content
            }
        )
        if llm_response_log:
            execution_log.append(llm_response_log)
        
        new_messages = messages + [
            HumanMessage(content=query),
            AIMessage(content=response.content)
        ]
        
        updated_state = {
            **state,
            "messages": new_messages,
            "iterations": state["iterations"] + 1,
            "execution_log": execution_log
        }
        
        # 최종 상태 변화 로깅
        return self._log_state_change(updated_state, "agent_node", "LLM 에이전트 노드 완료")

        
    def parse_node(self, state: StockSearchState) -> StockSearchState:
        """도구 호출 파싱 전용 노드"""
        messages = state["messages"]
        
        # 상태 변화 로깅
        state = self._log_state_change(state, "parse_node", "도구 호출 파싱 노드 시작")
        
        # 마지막 AI 메시지에서 도구 호출 파싱
        ai_response = ""
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                ai_response = message.content
                break
        
        print(f"[PARSE] AI 응답에서 도구 호출 파싱 중...")
        
        # 실행 로그 추가
        execution_log = state.get("execution_log", [])
        
        # 도구 호출 파싱
        tool_calls = self._parse_tool_calls(ai_response)
        print(f"[PARSE] 파싱된 도구 호출: {len(tool_calls)}개")
        if tool_calls:
            for i, call in enumerate(tool_calls):
                print(f"[TOOL_CALL_{i}] {call}")
        
        # 도구 호출 파싱 로그
        parse_log = self._log_execution(
            f"도구 호출 파싱 완료: {len(tool_calls)}개 발견",
            "INFO",
            {"tool_calls": tool_calls, "ai_response_length": len(ai_response)}
        )
        if parse_log:
            execution_log.append(parse_log)
        
        # 도구 호출을 pending_tools에 저장
        updated_state = {
            **state,
            "tool_calls": tool_calls,
            "pending_tools": tool_calls,  # 실행 대기 중인 도구들
            "current_tool_index": 0,      # 현재 도구 인덱스 초기화
            "completed_tools": [],        # 완료된 도구들 초기화
            "tool_execution_results": [], # 도구 실행 결과들 초기화
            "execution_log": execution_log
        }
        
        # 최종 상태 변화 로깅
        return self._log_state_change(updated_state, "parse_node", "도구 호출 파싱 노드 완료")

    def tools_node(self, state: StockSearchState) -> StockSearchState:
        """일반 도구들 실행 노드 (text2sql 제외)"""
        tool_calls = state.get("tool_calls", [])
        messages = state.get("messages", [])
        
        # 상태 변화 로깅
        state = self._log_state_change(state, "tools_node", "일반 도구들 실행 노드 시작")
        
        # text2sql이 아닌 도구들만 필터링
        regular_tools = [call for call in tool_calls if call.get("name") != "text2sql"]
        
        if not regular_tools:
            print("[SKIP] 실행할 일반 도구가 없음")
            return {**state, "validation_status": "success"}
        
        print(f"[TOOLS] 일반 도구 실행: {len(regular_tools)}개")
        
        # 실행 로그 추가
        execution_log = state.get("execution_log", [])
        tool_results = state.get("tool_results", [])
        tool_execution_results = state.get("tool_execution_results", [])
        
        results = []
        validation_status = "success"
        
        for tool_call in regular_tools:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args", "")
            
            print(f"[EXEC] {tool_name} 실행 중...")
            
            try:
                exec_start_time = datetime.now()
                
                # 도구 함수 찾기
                tool_func = None
                for tool in self.tools:
                    if tool.name == tool_name:
                        tool_func = tool.func
                        break
                
                if tool_func:
                    result = tool_func(tool_args)
                    
                    # 파라미터 부족 오류 감지
                    error_keywords = [
                        "질문을 이해할 수 없습니다",
                        "날짜 정보를 찾을 수 없습니다", 
                        "조건을 찾을 수 없습니다",
                        "임계값을 찾을 수 없습니다",
                        "파라미터를 추출할 수 없습니다"
                    ]
                    
                    if any(keyword in result for keyword in error_keywords):
                        validation_status = "param_missing"
                    
                    exec_end_time = datetime.now()
                    exec_duration = (exec_end_time - exec_start_time).total_seconds()
                    
                    # 결과 저장
                    tool_result_detail = {
                        "tool_name": tool_name,
                        "tool_args": tool_args,
                        "execution_time": exec_duration,
                        "result_length": len(str(result)),
                        "full_result": result,
                        "status": validation_status,
                        "timestamp": exec_end_time.isoformat()
                    }
                    tool_results.append(tool_result_detail)
                    results.append(f"{tool_name} 결과: {result}")
                    tool_execution_results.append(f"{tool_name} 결과: {result}")
                    
                    print(f"[OK] {tool_name} 완료")
                else:
                    result = f"알 수 없는 도구: {tool_name}"
                    results.append(result)
                    tool_execution_results.append(result)
                    validation_status = "tool_error"
                    print(f"[UNKNOWN] {tool_name}")
                    
            except Exception as e:
                result = f"{tool_name} 오류: {str(e)}"
                results.append(result)
                tool_execution_results.append(result)
                validation_status = "tool_error"
                print(f"[FAIL] {tool_name}: {str(e)}")
        
        tool_result = "\n\n".join(results)
        new_messages = messages + [AIMessage(content=tool_result)]
        
        updated_state = {
            **state,
            "messages": new_messages,
            "result": tool_result,
            "validation_status": validation_status,
            "execution_log": execution_log,
            "tool_results": tool_results,
            "tool_execution_results": tool_execution_results
        }
        
        return self._log_state_change(updated_state, "tools_node", "일반 도구들 실행 노드 완료")


    def _create_graph(self) -> StateGraph:
        """LangGraph 워크플로우 생성 (개별 도구 노드 포함)"""
        
        # 중첩 함수에서 사용할 수 있도록 지역 변수로 저장
        tools = self.tools
        llm_main = self.llm_main      # 중요한 작업: 쿼리 분석, 도구 선택
        llm_simple = self.llm_simple  # 사소한 작업: 최종 응답 생성
        
                
        def text2sql_node(state: StockSearchState) -> StockSearchState:
            """TEXT2SQL 전용 노드"""
            tool_calls = state.get("tool_calls", [])
            messages = state.get("messages", [])
            
            # 상태 변화 로깅
            state = self._log_state_change(state, "text2sql_node", "TEXT2SQL 노드 시작")
            
            # text2sql 도구들만 필터링
            text2sql_calls = [call for call in tool_calls if call.get("name") == "text2sql"]
            
            if not text2sql_calls:
                print("[SKIP] TEXT2SQL 호출이 없음")
                return {**state, "validation_status": "success"}
            
            print(f"[TEXT2SQL] TEXT2SQL 실행: {len(text2sql_calls)}개")
            
            # 실행 로그 추가
            execution_log = state.get("execution_log", [])
            tool_results = state.get("tool_results", [])
            tool_execution_results = state.get("tool_execution_results", [])
            
            results = []
            validation_status = "success"
            
            for text2sql_call in text2sql_calls:
                tool_args = text2sql_call.get("args", "")
                
                try:
                    exec_start_time = datetime.now()
                    
                    # 원본 질문을 그대로 사용 (JSON 파싱 제거)
                    original_query = tool_args if tool_args else state["query"]
                    
                    print(f"[TEXT2SQL] 원본 질문: {original_query}")
                    
                    # TEXT2SQL 노드 실행 (컬럼과 query_type은 내부에서 추출)
                    result = self.text2sql_node.execute_text2sql(original_query, [], '복합조건')
                    
                    exec_end_time = datetime.now()
                    exec_duration = (exec_end_time - exec_start_time).total_seconds()
                    
                    # 결과 저장
                    tool_result_detail = {
                        "tool_name": "text2sql",
                        "tool_args": tool_args,
                        "execution_time": exec_duration,
                        "result_length": len(str(result)),
                        "full_result": result,
                        "status": "success",
                        "timestamp": exec_end_time.isoformat()
                    }
                    tool_results.append(tool_result_detail)
                    results.append(f"text2sql 결과: {result}")
                    tool_execution_results.append(f"text2sql 결과: {result}")
                    
                    print(f"[OK] TEXT2SQL 완료")
                        
                except Exception as e:
                    result = f"text2sql 오류: {str(e)}"
                    results.append(result)
                    tool_execution_results.append(result)
                    validation_status = "tool_error"
                    print(f"[FAIL] TEXT2SQL: {str(e)}")
            
            tool_result = "\n\n".join(results)
            new_messages = messages + [AIMessage(content=tool_result)]
            
            updated_state = {
                **state,
                "messages": new_messages,
                "result": tool_result,
                "validation_status": validation_status,
                "execution_log": execution_log,
                "tool_results": tool_results,
                "tool_execution_results": tool_execution_results
            }
            
            return self._log_state_change(updated_state, "text2sql_node", "TEXT2SQL 노드 완료")

        def should_continue(state: StockSearchState) -> str:
            """다음 단계 결정 - text2sql vs 일반 tools vs 종료"""
            tool_calls = state.get("tool_calls", [])
            
            if not tool_calls:
                return "generation"  # 도구 호출이 없으면 바로 응답 생성
            
            # text2sql이 있는지 확인
            has_text2sql = any(call.get("name") == "text2sql" for call in tool_calls)
            has_regular_tools = any(call.get("name") != "text2sql" for call in tool_calls)
            
            if has_text2sql and has_regular_tools:
                # 둘 다 있으면 일반 도구 먼저 실행
                return "tools"
            elif has_text2sql:
                return "text2sql"
            elif has_regular_tools:
                return "tools"
            else:
                return "generation"
        
        def after_tools_routing(state: StockSearchState) -> str:
            """일반 도구 실행 후 라우팅"""
            tool_calls = state.get("tool_calls", [])
            validation_status = state.get("validation_status", "success")
            retry_count = state.get("retry_count", 0)
            
            # 파라미터 부족 시 명확화 요청
            if validation_status == "param_missing" and retry_count < 2:
                return "clarifier"
            
            # text2sql이 남아있는지 확인
            has_text2sql = any(call.get("name") == "text2sql" for call in tool_calls)
            if has_text2sql:
                return "text2sql"
            
            return "filter_decision"
        
        def after_text2sql_routing(state: StockSearchState) -> str:
            """TEXT2SQL 실행 후 라우팅"""
            validation_status = state.get("validation_status", "success")
            retry_count = state.get("retry_count", 0)
            
            # 파라미터 부족 시 명확화 요청
            if validation_status == "param_missing" and retry_count < 2:
                return "clarifier"
            
            return "filter_decision"
        
        def should_filter_results(state: StockSearchState) -> str:
            """결과 필터링 필요 여부 판단"""
            tool_calls = state.get("tool_calls", [])
            
            # 실행된 도구 중 필터링이 필요한 도구가 있는지 확인
            needs_filtering = any(
                call.get("name") in self.TOOLS_NEED_FILTERING 
                for call in tool_calls
            )
            
            print(f"[FILTER_DECISION] 필터링 필요: {needs_filtering}")
            if needs_filtering:
                executed_tools = [call.get("name") for call in tool_calls]
                print(f"[FILTER_DECISION] 실행된 도구들: {executed_tools}")
            
            return "result_filter" if needs_filtering else "generation"
        
        def clarifier_node(state: StockSearchState) -> StockSearchState:
            """명확화 요청 노드"""
            messages = state["messages"]
            query = state["query"]
            
            print(f"[CLARIFY] 파라미터 부족으로 명확화 요청")
            
            clarification_prompt = f"""질문을 더 구체적으로 해주세요. 

원본 질문: {query}

다음과 같은 정보가 필요합니다:
- 정확한 날짜 (예: 2025-11-06)
- 구체적인 조건 (예: RSI 70 이상, 거래량 100만주 이상)
- 시장 구분이 필요한 경우 KOSPI 또는 KOSDAQ 명시

예시:
- "2025-11-06 RSI 70 이상 과매수 종목은?"
- "2025-11-06 KOSPI 시장에서 가격이 1만원 이상 5만원 이하인 종목은?"
- "2025-01-01부터 2025-12-31까지 골든크로스 발생 종목은?"""
            
            new_messages = messages + [AIMessage(content=clarification_prompt)]
            
            return {
                **state,
                "messages": new_messages,
                "result": clarification_prompt,
                "clarification_needed": True
            }
        
        
        def result_filter_node(state: StockSearchState) -> StockSearchState:
            """결과 필터링 노드 - 종목 리스트가 너무 많을 때 제한"""
            messages = state["messages"]
            query = state["query"]
            result = state.get("result", "")
            
            # 상태 변화 로깅
            state = self._log_state_change(state, "result_filter", "결과 필터링 노드 시작")
            
            print(f"[FILTER] 결과 필터링 중...")
            
            # 실행 로그 추가
            execution_log = state.get("execution_log", [])
            filter_log = self._log_execution(
                "결과 필터링 시작",
                "INFO",
                {"original_result_length": len(result)}
            )
            if filter_log:
                execution_log.append(filter_log)
            
            # 결과를 줄 단위로 분석
            lines = [line.strip() for line in result.split('\n') if line.strip()]
            
            # 종목 패턴 감지 (간단한 휴리스틱)
            stock_like_lines = []
            for line in lines:
                # 종목명 패턴들
                if any([
                    re.search(r'[\w가-힣]+\s*\([\w\d]+\)', line),  # "삼성전자 (005930)"
                    re.search(r'^\d+\.\s*[\w가-힣]', line),      # "1. 삼성전자"
                    re.search(r'[\w가-힣]+\s*\|\s*[\d,]+', line),  # "삼성전자 | 50,000"
                    (len(line) > 5 and len(line) < 100 and any(c in '가나다라마바사아자차카타파하' for c in line))
                ]):
                    stock_like_lines.append(line)
            
            print(f"[FILTER] 종목 라인 감지: {len(stock_like_lines)}개")
            
            # 결과 제한 로직 개선
            should_limit = False
            limit = len(stock_like_lines)  # 기본적으로 모든 결과 표시
            
            # 사용자가 "모두", "전체", "모든"을 요청한 경우 제한하지 않음
            if any(keyword in query.lower() for keyword in ['모두', '전체', '모든']):
                should_limit = False
                limit = len(stock_like_lines)  # 모든 결과 표시
            elif re.search(r'(\d+)개', query):
                # 구체적 개수 요청이 있으면 그 개수만
                match = re.search(r'(\d+)개', query)
                limit = int(match.group(1))
                should_limit = True
            elif len(stock_like_lines) > 100:
                # 100개 초과시에만 제한 (기존 50에서 100으로 증가)
                limit = 100
                should_limit = True
            
            if should_limit and len(stock_like_lines) > limit:
                # 결과 재구성 (제한 적용)
                header_lines = [line for line in lines if line not in stock_like_lines]
                filtered_stocks = stock_like_lines[:limit]
                
                filtered_result = '\n'.join(header_lines + filtered_stocks)
                if len(stock_like_lines) > limit:
                    filtered_result += f"\n\n... 등 총 {len(stock_like_lines)}개 종목이 있습니다."
                
                print(f"[FILTER] {len(stock_like_lines)}개 → {limit}개로 제한")
                
                # 필터링 로그
                filter_complete_log = self._log_execution(
                    f"결과 필터링 완료: {len(stock_like_lines)}개 → {limit}개",
                    "INFO",
                    {
                        "original_count": len(stock_like_lines),
                        "filtered_count": limit,
                        "filtered_result_length": len(filtered_result)
                    }
                )
                if filter_complete_log:
                    execution_log.append(filter_complete_log)
                
                updated_state = {
                    **state,
                    "result": filtered_result,
                    "execution_log": execution_log
                }
            else:
                print(f"[FILTER] 모든 결과 표시: {len(stock_like_lines)}개")
                # 필터링 없이 모든 결과 표시 로그
                no_filter_log = self._log_execution(
                    f"모든 결과 표시: {len(stock_like_lines)}개",
                    "INFO",
                    {"total_count": len(stock_like_lines)}
                )
                if no_filter_log:
                    execution_log.append(no_filter_log)
                
                updated_state = {
                    **state,
                    "execution_log": execution_log
                }
            
            # 최종 상태 변화 로깅
            return self._log_state_change(updated_state, "result_filter", "결과 필터링 노드 완료")
        
        def generation_node(state: StockSearchState) -> StockSearchState:
            """최종 응답 생성 노드"""
            messages = state["messages"]
            query = state["query"]
            
            # 모든 도구 실행 결과를 합치기
            tool_execution_results = state.get("tool_execution_results", [])
            tool_result = "\n\n".join(tool_execution_results) if tool_execution_results else state.get("result", "")
            
            print(f"[GENERATION] 사용자 친화적 응답 생성 중...")
            
            generation_prompt = f"""사용자 질문에 대한 도구 실행 결과를 그대로 전달하세요.

사용자 질문: {query}

도구 실행 결과:
{tool_result}

**필수 규칙**:
- 도구 결과를 그대로 복사해서 전달
- 절대로 종목 개수를 줄이지 말 것
- "총 38개 중 30개 표시"라고 나와있으면 → 30개 모두 나열
- 임의로 5개, 10개로 제한하지 말 것
- 날짜 정보가 있으면 포함

답변 형식:
{query.replace('모두 보여줘', '')}에 대한 결과는 다음과 같습니다:

[도구 결과에 나온 모든 종목을 그대로 나열]

답변:"""
            
            response = llm_main.invoke([HumanMessage(content=generation_prompt)])  # 사소한 작업: HCX-005
            final_answer = response.content
            
            print(f"[FINAL] 최종 응답 생성 완료: {len(final_answer)}자")
            
            new_messages = messages + [AIMessage(content=final_answer)]
            
            return {
                **state,
                "messages": new_messages,
                "result": final_answer
            }

        # 단계별 그래프 구성
        workflow = StateGraph(StockSearchState)
        
        # 노드들 추가
        workflow.add_node("agent", self.agent_node)      # 1. LLM 응답 생성
        workflow.add_node("parse", self.parse_node)      # 2. 도구 호출 파싱
        workflow.add_node("tools", self.tools_node)      # 3a. 일반 도구들 실행
        workflow.add_node("text2sql", text2sql_node)  # 3b. TEXT2SQL 실행
        workflow.add_node("filter_decision", lambda state: state)  # 4. 필터링 결정 (더미 노드)
        workflow.add_node("result_filter", result_filter_node)  # 5a. 결과 필터링
        workflow.add_node("clarifier", clarifier_node)  # 5b. 명확화 요청
        workflow.add_node("generation", generation_node)  # 6. 최종 응답 생성
        
        print("[GRAPH] 8개 노드 생성: agent → parse → tools/text2sql → filter_decision → result_filter/generation")
        
        # 시작점 설정
        workflow.set_entry_point("agent")
        
        # agent → parse (항상)
        workflow.add_edge("agent", "parse")
        
        # parse에서 분기
        workflow.add_conditional_edges(
            "parse", 
            should_continue,
            {
                "tools": "tools",
                "text2sql": "text2sql", 
                "generation": "generation",
                END: END
            }
        )
        
        # tools 노드 후 분기
        workflow.add_conditional_edges(
            "tools",
            after_tools_routing,
            {
                "clarifier": "clarifier",
                "text2sql": "text2sql",
                "filter_decision": "filter_decision"
            }
        )
        
        # text2sql 노드 후 분기
        workflow.add_conditional_edges(
            "text2sql",
            after_text2sql_routing,
            {
                "clarifier": "clarifier", 
                "filter_decision": "filter_decision"
            }
        )
        
        # filter_decision 노드 후 분기
        workflow.add_conditional_edges(
            "filter_decision",
            should_filter_results,
            {
                "result_filter": "result_filter",
                "generation": "generation"
            }
        )
        
        # 최종 노드들의 엣지
        workflow.add_edge("result_filter", "generation")
        workflow.add_edge("clarifier", END)
        workflow.add_edge("generation", END)
        
        compiled_graph = workflow.compile()
        
        # 그래프 시각화 이미지 저장
        try:
            compiled_graph.get_graph().draw_mermaid_png(output_file_path="stock_search_workflow.png")
            print("[GRAPH] 워크플로우 그래프 저장: stock_search_workflow.png")
        except Exception as e:
            print(f"[GRAPH] 그래프 저장 실패: {e}")
        
        return compiled_graph
    
    def _parse_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        """AI 응답에서 도구 호출 파싱 (개선된 버전)"""
        tool_calls = []
        
        # 패턴 1: 표준 TOOL_CALL: 형식
        pattern1 = r'TOOL_CALL:\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})'
        matches1 = re.findall(pattern1, content, re.DOTALL)
        
        # 패턴 2: JSON 블록 또는 백틱 (TEXT2SQL용)
        pattern2 = r'```json\s*(\{[^}]*"action"[^}]*"text2sql"[^}]*\})\s*```|```json\s*(\{[^}]*\})\s*```|→\s*`(\{[^`]*\})`|`(\{[^`]*\})`'
        matches2 = re.findall(pattern2, content, re.DOTALL)
        
        # 패턴 3: TEXT2SQL action이 포함된 JSON 객체 (백틱 없이)
        pattern3 = r'(\{[^{}]*"action"[^{}]*"text2sql"[^{}]*\})'
        matches3 = re.findall(pattern3, content, re.DOTALL)
        
        # 패턴 4: name과 args가 포함된 일반 JSON 객체 (중첩 중괄호 지원)
        pattern4 = r'(\{[^{}]*"name"[^{}]*"args"[^{}]*(?:\{[^{}]*\}[^{}]*)*\})'
        matches4 = re.findall(pattern4, content, re.DOTALL)
        
        # 패턴 5: TEXT2SQL 액션 패턴 (중첩 중괄호 지원)
        pattern5 = r'TEXT2SQL:\s*(\{[^{}]*"action"[^{}]*"text2sql"[^{}]*(?:\{[^{}]*\}[^{}]*)*\})'
        matches5 = re.findall(pattern5, content, re.DOTALL)
        
        # 패턴 1 처리 (표준)
        for match in matches1:
            try:
                clean_match = match.strip()
                tool_call = json.loads(clean_match)
                if 'name' in tool_call and 'args' in tool_call:
                    tool_calls.append(tool_call)
            except json.JSONDecodeError:
                continue
        
        # 패턴 2 처리 (JSON 블록과 백틱) - 항상 실행
        for match_groups in matches2:
            for match in match_groups:
                if match:
                    try:
                        tool_call = json.loads(match.strip())
                        # TEXT2SQL 액션 체크
                        if 'action' in tool_call and tool_call['action'] == 'text2sql':
                            tool_calls.append({
                                'name': 'text2sql',
                                'args': json.dumps(tool_call)
                            })
                        # 일반 도구 호출 체크
                        elif 'name' in tool_call and 'args' in tool_call:
                            tool_calls.append(tool_call)
                    except json.JSONDecodeError:
                        continue
        
        # 패턴 3 처리 (TEXT2SQL action JSON) - 항상 실행
        for match in matches3:
            try:
                clean_match = match.strip()
                text2sql_call = json.loads(clean_match)
                if 'action' in text2sql_call and text2sql_call['action'] == 'text2sql':
                    # TEXT2SQL을 특별한 도구 호출로 변환
                    tool_calls.append({
                        'name': 'text2sql',
                        'args': json.dumps(text2sql_call)
                    })
            except json.JSONDecodeError:
                continue
        
        # 패턴 4 처리 (일반 도구 호출 JSON) - 항상 실행
        for match in matches4:
            try:
                clean_match = match.strip()
                tool_call = json.loads(clean_match)
                if 'name' in tool_call and 'args' in tool_call:
                    # args가 객체인 경우 전체 질문으로 변환
                    if isinstance(tool_call['args'], dict):
                        # 질문을 재구성
                        args_dict = tool_call['args']
                        if '종목명' in args_dict and '날짜' in args_dict:
                            tool_call['args'] = f"{args_dict['종목명']}의 {args_dict['날짜']} 시가는?"
                        else:
                            tool_call['args'] = str(args_dict)
                    tool_calls.append(tool_call)
            except json.JSONDecodeError:
                continue
        
        # 패턴 5 처리 (TEXT2SQL: 형식) - 항상 실행
        for match in matches5:
            try:
                clean_match = match.strip()
                text2sql_call = json.loads(clean_match)
                if 'action' in text2sql_call and text2sql_call['action'] == 'text2sql':
                    # TEXT2SQL을 특별한 도구 호출로 변환
                    tool_calls.append({
                        'name': 'text2sql',
                        'args': json.dumps(text2sql_call)
                    })
            except json.JSONDecodeError:
                continue
        
        # 중복 제거
        unique_tool_calls = []
        seen = set()
        for call in tool_calls:
            identifier = (call.get('name'), call.get('args'))
            if identifier not in seen:
                seen.add(identifier)
                unique_tool_calls.append(call)

        tool_calls = unique_tool_calls
        
        return tool_calls
    
    def search(self, query: str, return_detailed_info: bool = False) -> str | Dict[str, Any]:
        """주식 검색 실행"""
        try:
            print(f"[START] 쿼리 분석 시작: {query}")
            logging.info(f"쿼리 처리 시작: {query}")
            
            initial_state = StockSearchState(
                messages=[], 
                query=query, 
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
            
            print(f"[WORKFLOW] LangGraph 워크플로우 실행 중...")
            result = self.graph.invoke(initial_state)
            final_result = result.get("result", "답변을 생성할 수 없습니다.")
            
            print(f"[SUCCESS] 응답 생성 완료: {len(final_result)}자")
            logging.info(f"쿼리 처리 완료: {len(final_result)}자 응답 생성")
            
            # 상세 정보 반환 옵션
            if return_detailed_info and self.enable_detailed_logging:
                detailed_info = {
                    "final_result": final_result,
                    "execution_log": result.get("execution_log", []),
                    "tool_results": result.get("tool_results", []),
                    "node_traces": result.get("node_traces", []),
                    "state_history": result.get("state_history", []),
                    "final_state": {
                        "iterations": result.get("iterations", 0),
                        "validation_status": result.get("validation_status", "unknown"),
                        "clarification_needed": result.get("clarification_needed", False),
                        "retry_count": result.get("retry_count", 0),
                        "tool_calls_count": len(result.get("tool_calls", []))
                    }
                }
                return detailed_info
            
            return final_result
            
        except Exception as e:
            print(f"[ERROR] 검색 중 오류: {str(e)}")
            logging.error(f"검색 중 오류 발생: {str(e)}")
            
            error_msg = f"검색 중 오류 발생: {str(e)}"
            
            if return_detailed_info and self.enable_detailed_logging:
                return {
                    "final_result": error_msg,
                    "error": str(e),
                    "execution_log": [],
                    "tool_results": [],
                    "node_traces": [],
                    "state_history": [],
                    "final_state": {"error": True}
                }
            
            return error_msg


if __name__ == "__main__":
    print("현재 위치", os.getcwd())
    print("스크립트 파일 위치:", __file__)
    print("프로젝트 루트:", project_root)
    
    # 파일 존재 확인
    csv_path = "../company_info.csv"
    db_path = "../stock_info.db"
    print(f"CSV 파일 존재 확인: {csv_path} -> {os.path.exists(csv_path)}")
    print(f"DB 파일 존재 확인: {db_path} -> {os.path.exists(db_path)}")
    print(f"절대 경로로 확인: {os.path.abspath(csv_path)} -> {os.path.exists(os.path.abspath(csv_path))}")
    
    # 데이터베이스 매니저 초기화
    db_manager = DatabaseManager(
        company_csv_path=os.path.join(project_root, "company_info.csv"),
        stock_db_path=os.path.join(project_root, "stock_info.db"), 
        market_db_path=os.path.join(project_root, "market_index.db"),
        technical_db_path=os.path.join(project_root, "technical_indicators.db")
    )
    
    # 주식 검색 에이전트 초기화
    agent = StockSearchAgent(db_manager)
    
    # 테스트 질문들
    test_queries = [
        "삼성전자의 2024-11-06 종가는?",
        "2024-11-06 상승률 1위는?",
        "SK하이닉스 찾아줘",
        "2024-11-06 시장 통계 알려줘"
    ]
    
    print("=== LLM 향상 주식 검색 에이전트 ===\n")
    
    for i, query in enumerate(test_queries, 1):
        print(f"[테스트 {i}]")
        print(f"질문: {query}")
        print("답변:", end=" ")
        
        try:
            result = agent.search(query)
            print(result)
        except Exception as e:
            print(f"오류 발생: {e}")
        
        print("-" * 60)