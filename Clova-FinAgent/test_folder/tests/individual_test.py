#!/usr/bin/env python3
"""
개별 쿼리 테스트 도구
단일 쿼리나 소수의 쿼리를 대화형으로 테스트하는 도구
"""

import os
import sys
from datetime import datetime
from typing import List, Optional

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from agents.stock_search_agent import StockSearchAgent
from core.database_manager import DatabaseManager


class IndividualTester:
    """개별 쿼리 테스터 클래스"""
    
    def __init__(self):
        # 데이터베이스 매니저 초기화
        self.db_manager = DatabaseManager(
            company_csv_path=os.path.join(project_root, "company_info.csv"),
            stock_db_path=os.path.join(project_root, "stock_info.db"), 
            market_db_path=os.path.join(project_root, "market_index.db"),
            technical_db_path=os.path.join(project_root, "technical_indicators.db")
        )
        
        # 주식 검색 에이전트 초기화
        self.agent = StockSearchAgent(self.db_manager)
        
        print("✅ 개별 테스터 초기화 완료")
    
    def test_predefined_queries(self):
        """미리 정의된 테스트 쿼리들 실행"""
        test_queries = [
            "삼성전자의 2024-11-06 주가는?",
            "2024-11-06 상승률 1위는?", 
            "SK하이닉스 찾아줘",
            "2024-11-06 시장 통계 알려줘",
            "2024-11-06에 RSI가 70 이상인 과매수 종목은?",
            "2024-11-06에 거래량이 20일 평균 대비 500% 이상 급증한 종목은?",
            "2024-01-01부터 2024-12-31까지 골든크로스가 발생한 종목은?",
            "KOSPI 시장에서 가격이 1만원 이상 5만원 이하인 종목은?"
        ]
        
        print("\n" + "=" * 60)
        print("미리 정의된 테스트 쿼리 실행")
        print("=" * 60)
        
        for i, query in enumerate(test_queries, 1):
            self._execute_single_test(i, query, len(test_queries))
    
    def test_custom_queries(self):
        """사용자 정의 쿼리들 대화형 테스트"""
        print("\n" + "=" * 60)
        print("사용자 정의 쿼리 테스트 (종료하려면 'quit' 입력)")
        print("=" * 60)
        
        query_count = 0
        while True:
            query = input(f"\n[쿼리 {query_count + 1}] 질문을 입력하세요: ").strip()
            
            if query.lower() in ['quit', 'exit', '종료']:
                print("테스트를 종료합니다.")
                break
                
            if not query:
                print("빈 질문입니다. 다시 입력해주세요.")
                continue
            
            query_count += 1
            self._execute_single_test(query_count, query)
    
    def test_single_query(self, query: str):
        """단일 쿼리 테스트"""
        print("\n" + "=" * 60)
        print("단일 쿼리 테스트")
        print("=" * 60)
        
        self._execute_single_test(1, query)
    
    def _execute_single_test(self, index: int, query: str, total: Optional[int] = None):
        """실제 쿼리 실행 및 결과 출력"""
        progress = f"[{index}/{total}]" if total else f"[{index}]"
        
        print(f"\n{progress} 질문: {query}")
        print("-" * 60)
        
        start_time = datetime.now()
        
        try:
            result = self.agent.search(query)
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds()
            
            print("✅ 답변:")
            print(result)
            print(f"\n⏱️  응답 시간: {response_time:.2f}초")
            
        except Exception as e:
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds()
            
            print("❌ 오류 발생:")
            print(f"   {str(e)}")
            print(f"\n⏱️  실행 시간: {response_time:.2f}초")
        
        if total and index < total:
            input("\n⏸️  계속하려면 Enter를 누르세요...")


def main():
    """메인 실행 함수"""
    print("개별 쿼리 테스터")
    print("=" * 50)
    
    try:
        tester = IndividualTester() 
        
        print("\n테스트 모드를 선택하세요:")
        print("1. 미리 정의된 테스트 쿼리 실행")
        print("2. 사용자 정의 쿼리 대화형 테스트")  
        print("3. 단일 쿼리 테스트")
        
        choice = input("\n선택 (1-3): ").strip()
        
        if choice == "1":
            tester.test_predefined_queries()
            
        elif choice == "2":
            tester.test_custom_queries()
            
        elif choice == "3":
            query = input("\n테스트할 쿼리를 입력하세요: ").strip()
            if query:
                tester.test_single_query(query)
            else:
                print("빈 쿼리입니다.")
                
        else:
            print("잘못된 선택입니다.")
            
    except Exception as e:
        print(f"\n❌ 테스터 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()