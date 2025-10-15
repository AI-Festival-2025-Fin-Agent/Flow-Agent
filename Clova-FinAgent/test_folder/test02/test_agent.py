# -*- coding: utf-8 -*-
import os
import sys
from datetime import datetime

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from parsing_agent import ParsingAgent, StockSearchState
from core.database_manager import DatabaseManager

class StockAgentTester:
    """주식 검색 에이전트 테스터 클래스"""

    def __init__(self):
        # 데이터베이스 매니저 초기화
        self.db_manager = DatabaseManager(
            company_csv_path=os.path.join(project_root, "company_info.csv"),
            stock_db_path=os.path.join(project_root, "stock_info.db"),
            market_db_path=os.path.join(project_root, "market_index.db"),
            technical_db_path=os.path.join(project_root, "technical_indicators.db")
        )

        # 파싱 에이전트 초기화
        self.agent = ParsingAgent(self.db_manager, enable_detailed_logging=True)

    def test_tool_parsing(self, question: str, verbose: bool = True) -> dict:
        """도구 파싱 테스트"""

        if verbose:
            print(f"\n=== 도구 파싱 테스트 ===")
            print(f"질문: {question}")
            print("-" * 50)

        try:
            # 초기 상태 설정
            initial_state = StockSearchState(
                messages=[],
                query=question,
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

            ai_response = None
            parsed_tools = []

            # 파싱 에이전트 실행 (agent → parse → END)
            final_state = None
            for step in self.agent.graph.stream(initial_state):
                for node_name, state in step.items():
                    if node_name == "agent" and verbose:
                        if state.get('messages'):
                            ai_message = state['messages'][-1]
                            ai_response = ai_message.content
                            print(f"✓ AI 응답: {ai_response[:100]}...")

                    elif node_name == "parse":
                        final_state = state
                        parsed_tools = state.get('tool_calls', [])
                        if verbose:
                            print(f"✓ {len(parsed_tools)}개 도구 호출 파싱됨")
                            for i, tool in enumerate(parsed_tools):
                                print(f"  [{i+1}] {tool.get('name', 'Unknown')}: {tool.get('args', 'None')}")
                        break

            # 결과 분석
            if parsed_tools:
                status = "parsing_success"
                if verbose:
                    print(f"\n✓ 파싱 성공: {len(parsed_tools)}개 도구 호출")
            else:
                status = "parsing_failed"
                if verbose:
                    print(f"\n✗ 파싱 실패: 도구 호출이 파싱되지 않음")

            return {
                'question': question,
                'ai_response': ai_response,
                'parsed_tools': parsed_tools,
                'tool_count': len(parsed_tools),
                'status': status,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            if verbose:
                print(f"\n✗ 오류 발생: {e}")
                import traceback
                traceback.print_exc()

            return {
                'question': question,
                'ai_response': None,
                'parsed_tools': [],
                'tool_count': 0,
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

def test_single_query_main(question: str):
    """메인 함수로 호출 가능한 도구 파싱 테스트"""
    tester = StockAgentTester()
    return tester.test_tool_parsing(question, verbose=True)

if __name__ == "__main__":
    # 직접 실행 시 테스트 쿼리 실행
    test_query = "삼성전자 2024-11-06 주가는?"

    tester = StockAgentTester()
    result = tester.test_tool_parsing(test_query)

    print(f"\n=== 테스트 완료 ===")
    print(f"상태: {result['status']}")
    print(f"파싱된 도구: {result['tool_count']}개")