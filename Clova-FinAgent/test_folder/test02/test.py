# -*- coding: utf-8 -*-
import os
import sys
import json
import time
from datetime import datetime

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from utils import get_simple_queries, get_conditional_queries, get_signal_queries
from test_agent import test_single_query_main

def test_csv_queries():
    """CSV 파일에서 쿼리들 가져와서 테스트"""

    print("=== CSV 쿼리 테스트 ===\n")

    query_folder = os.path.join(os.path.dirname(__file__), "..", "query")

    # 각 타입별로 3개씩 테스트
    simple_queries = get_simple_queries(query_folder, -1)
    conditional_queries = get_conditional_queries(query_folder, -1)
    signal_queries = get_signal_queries(query_folder, -1)

    all_queries = [
        ("simple", simple_queries),
        ("conditional", conditional_queries),
        ("signal", signal_queries)
    ]

    total_success = 0
    total_tests = 0
    all_results = []

    # 전체 테스트 시작 시간
    test_start_time = time.time()

    for query_type, queries in all_queries:
        print(f"\n--- {query_type} 쿼리 테스트 ---")

        for i, question in enumerate(queries):
            print(f"\n[{i+1}/{len(queries)}] {question}")

            # 개별 쿼리 실행 시간 측정
            query_start_time = time.time()
            result = test_single_query_main(question)
            query_end_time = time.time()
            execution_time = query_end_time - query_start_time

            total_tests += 1

            # 결과에 추가 정보 포함
            result['query_type'] = query_type
            result['test_index'] = f"{query_type}_{i+1}"
            result['execution_time_seconds'] = round(execution_time, 2)
            all_results.append(result)

            if result['status'] == 'parsing_success':
                total_success += 1
                print(f"✓ 성공 (도구 {result['tool_count']}개, {execution_time:.2f}초)")
            else:
                print(f"✗ 실패: {result['status']} ({execution_time:.2f}초)")
            
            time.sleep(5)

    # 전체 테스트 종료 시간
    test_end_time = time.time()
    total_execution_time = test_end_time - test_start_time

    print(f"\n=== 전체 결과 ===")
    print(f"총 {total_tests}개 테스트")
    print(f"성공: {total_success}개")
    print(f"실패: {total_tests - total_success}개")
    print(f"전체 실행 시간: {total_execution_time:.2f}초")

    # 결과를 JSON 파일로 저장
    result_file = os.path.join(os.path.dirname(__file__), "test_results.json")
    summary = {
        "test_summary": {
            "total_tests": total_tests,
            "successful": total_success,
            "failed": total_tests - total_success,
            "success_rate": round(total_success / total_tests * 100, 2) if total_tests > 0 else 0,
            "total_execution_time_seconds": round(total_execution_time, 2),
            "average_time_per_query": round(total_execution_time / total_tests, 2) if total_tests > 0 else 0,
            "test_timestamp": datetime.now().isoformat()
        },
        "detailed_results": all_results
    }

    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"결과 저장됨: {result_file}")

if __name__ == "__main__":
    test_csv_queries()