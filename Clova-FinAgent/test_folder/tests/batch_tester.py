#!/usr/bin/env python3
"""
통합 배치 테스터
모든 유형의 쿼리(simple, conditional, signal)를 지원하는 통합 배치 테스트 도구
"""

import os
import sys
import json
import csv
import pandas as pd
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
import traceback

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from agents.stock_search_agent import StockSearchAgent
from core.database_manager import DatabaseManager


class BatchTester:
    """통합 배치 테스터 클래스"""
    
    def __init__(self):
        self.db_manager = DatabaseManager(
            company_csv_path=os.path.join(project_root, "company_info.csv"),
            stock_db_path=os.path.join(project_root, "stock_info.db"), 
            market_db_path=os.path.join(project_root, "market_index.db"),
            technical_db_path=os.path.join(project_root, "technical_indicators.db")
        )
        self.agent = StockSearchAgent(self.db_manager)
        
        # 결과 저장 디렉토리 생성
        self.results_dir = os.path.join(project_root, "test_results")
        os.makedirs(self.results_dir, exist_ok=True)
        
        # 테스트 시작 시간
        self.test_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def load_queries(self, query_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        쿼리 파일들에서 질문 목록 로드
        
        Args:
            query_types: 로드할 쿼리 유형 리스트 (None이면 모든 유형)
                        예: ["simple"], ["conditional", "signal"], ["simple", "conditional", "signal", "open"]
        """
        if query_types is None:
            query_types = ["simple", "conditional", "signal", "open"]
            
        all_queries = []
        
        # CSV 파일들 로드
        csv_files = [
            ("simple_queries.csv", "simple"),
            ("conditional_queries.csv", "conditional"), 
            ("signal_queries.csv", "signal"),
            ("open_queries.csv", "open")
        ]
        
        for filename, query_type in csv_files:
            if query_type not in query_types:
                continue
                
            filepath = os.path.join(project_root, "query", filename)
            if os.path.exists(filepath):
                try:
                    df = pd.read_csv(filepath)
                    for _, row in df.iterrows():
                        all_queries.append({
                            "type": query_type,
                            "subtype": row.get("type", ""),
                            "evaluation_type": row.get("evaluation_type", "PASS_OR_FAIL"),
                            "question": row["question"],
                            "expected_answer": row["expected_answer"],
                            "source_file": filename
                        })
                    print(f"✓ {filename}에서 {len(df)}개 쿼리 로드")
                except Exception as e:
                    print(f"✗ CSV 파일 로드 오류 {filename}: {e}")
        
        # JSON 파일들 로드
        json_files = [
            ("simple_queries_2.json", "simple"),
            ("conditional_queries_2.json", "conditional"),
            ("signal_queries_2.json", "signal"),
            ("open_queries.json", "open")
        ]
        
        for filename, query_type in json_files:
            if query_type not in query_types:
                continue
                
            filepath = os.path.join(project_root, "query", filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    for item in data:
                        all_queries.append({
                            "type": query_type,
                            "subtype": "",
                            "evaluation_type": item.get("evaluation_type", "PASS_OR_FAIL"),
                            "question": item["input_data"]["message"],
                            "expected_answer": item["expected_output"],
                            "source_file": filename
                        })
                    print(f"✓ {filename}에서 {len(data)}개 쿼리 로드")
                except Exception as e:
                    print(f"✗ JSON 파일 로드 오류 {filename}: {e}")
        
        print(f"\n총 {len(all_queries)}개 쿼리 로드 완료")
        return all_queries
    
    def test_single_query(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """단일 쿼리 테스트 실행"""
        question = query_data["question"]
        expected = query_data["expected_answer"]
        
        print(f"\n테스트 중: {question[:50]}...")
        
        start_time = datetime.now()
        
        try:
            # 에이전트 실행 (상세 정보 포함)
            detailed_result = self.agent.search(question, return_detailed_info=True)
            
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds()
            
            # 상세 정보가 Dict인지 확인
            if isinstance(detailed_result, dict):
                actual_result = detailed_result.get("final_result", "")
                agent_detailed_info = {
                    "execution_log": detailed_result.get("execution_log", []),
                    "tool_results": detailed_result.get("tool_results", []),
                    "node_traces": detailed_result.get("node_traces", []),
                    "state_history": detailed_result.get("state_history", []),
                    "final_state": detailed_result.get("final_state", {})
                }
            else:
                # fallback: 단순 문자열 결과
                actual_result = str(detailed_result)
                agent_detailed_info = {
                    "execution_log": [],
                    "tool_results": [],
                    "node_traces": [],
                    "state_history": [],
                    "final_state": {}
                }
            
            # 결과 저장
            result = {
                "timestamp": start_time.isoformat(),
                "query_type": query_data["type"],
                "subtype": query_data.get("subtype", ""),
                "evaluation_type": query_data.get("evaluation_type", "PASS_OR_FAIL"),
                "question": question,
                "expected_answer": expected,
                "actual_result": actual_result,
                "response_time": response_time,
                "status": "SUCCESS",
                "error_message": None,
                "source_file": query_data.get("source_file", ""),
                # 새로운 상세 정보 필드들
                "agent_detailed_info": agent_detailed_info,
                "execution_summary": {
                    "total_execution_logs": len(agent_detailed_info["execution_log"]),
                    "total_tool_calls": len(agent_detailed_info["tool_results"]),
                    "total_node_traces": len(agent_detailed_info["node_traces"]),
                    "total_state_changes": len(agent_detailed_info["state_history"]),
                    "final_iterations": agent_detailed_info["final_state"].get("iterations", 0),
                    "final_validation_status": agent_detailed_info["final_state"].get("validation_status", "unknown")
                }
            }
            
            print(f"✓ 완료 ({response_time:.2f}초)")
            print(f"  - 실행 로그: {len(agent_detailed_info['execution_log'])}개")
            print(f"  - 도구 호출: {len(agent_detailed_info['tool_results'])}개")
            print(f"  - 노드 추적: {len(agent_detailed_info['node_traces'])}개")
            
            return result
            
        except Exception as e:
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds()
            
            error_msg = str(e)
            print(f"✗ 오류: {error_msg}")
            
            result = {
                "timestamp": start_time.isoformat(),
                "query_type": query_data["type"],
                "subtype": query_data.get("subtype", ""),
                "evaluation_type": query_data.get("evaluation_type", "PASS_OR_FAIL"),
                "question": question,
                "expected_answer": expected,
                "actual_result": f"ERROR: {error_msg}",
                "response_time": response_time,
                "status": "ERROR",
                "error_message": error_msg,
                "source_file": query_data.get("source_file", ""),
                # 오류 시에도 빈 상세 정보 구조 제공
                "agent_detailed_info": {
                    "execution_log": [],
                    "tool_results": [],
                    "node_traces": [],
                    "state_history": [],
                    "final_state": {"error": True}
                },
                "execution_summary": {
                    "total_execution_logs": 0,
                    "total_tool_calls": 0,
                    "total_node_traces": 0,
                    "total_state_changes": 0,
                    "final_iterations": 0,
                    "final_validation_status": "error"
                }
            }
            
            return result
    
    def run_batch_test(self, query_types: Optional[List[str]] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        배치 테스트 실행
        
        Args:
            query_types: 테스트할 쿼리 유형 (None이면 모든 유형)
            limit: 테스트할 최대 쿼리 수 (None이면 모든 쿼리)
        """
        print("=" * 60)
        print("통합 배치 테스트 시작")
        print("=" * 60)
        
        # 쿼리 로드
        queries = self.load_queries(query_types)
        
        if limit:
            queries = queries[:limit]
            print(f"테스트 제한: {limit}개 쿼리만 실행")
        
        # 테스트 실행
        results = []
        successful_tests = 0
        failed_tests = 0
        
        for i, query_data in enumerate(queries, 1):
            print(f"\n[{i}/{len(queries)}]", end=" ")
            
            result = self.test_single_query(query_data)
            results.append(result)
            
            if result["status"] == "SUCCESS":
                successful_tests += 1
            else:  
                failed_tests += 1
        
        # 결과 저장 (상세 분석 포함)
        self._save_results(results, query_types, limit)
        
        # 상세 분석 리포트 생성
        self._generate_detailed_analysis(results)
        
        # 요약 통계
        summary = {
            "total_queries": len(queries),
            "successful_tests": successful_tests,
            "failed_tests": failed_tests,
            "success_rate": successful_tests / len(queries) * 100 if queries else 0,
            "test_timestamp": self.test_timestamp,
            "query_types_tested": query_types or ["simple", "conditional", "signal"],
            "limit_applied": limit
        }
        
        self._print_summary(summary)
        return summary
    
    def _save_results(self, results: List[Dict[str, Any]], query_types: Optional[List[str]], limit: Optional[int]):
        """테스트 결과 저장"""
        
        # 상세 결과 저장 (JSON)
        detail_filename = f"test_detailed_{self.test_timestamp}.json"
        detail_path = os.path.join(self.results_dir, detail_filename)
        
        with open(detail_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # 요약 결과 저장 (CSV)
        summary_filename = f"test_summary_{self.test_timestamp}.csv"
        summary_path = os.path.join(self.results_dir, summary_filename)
        
        df = pd.DataFrame(results)
        df.to_csv(summary_path, index=False, encoding='utf-8-sig')
        
        # 실패한 테스트만 저장
        failed_results = [r for r in results if r["status"] == "ERROR"]
        if failed_results:
            failed_filename = f"failed_queries_{self.test_timestamp}.json"
            failed_path = os.path.join(self.results_dir, failed_filename)
            
            with open(failed_path, 'w', encoding='utf-8') as f:
                json.dump(failed_results, f, ensure_ascii=False, indent=2)
        
        print(f"\n📁 결과 저장 완료:")
        print(f"   - 상세: {detail_filename} (agent 내부 정보 포함)")
        print(f"   - 요약: {summary_filename}")
        if failed_results:
            print(f"   - 실패: {failed_filename}")
        print(f"   ※ JSON 파일에 agent 상태, tool 실행 세부사항, node 추적 정보가 모두 포함됨")
    
    def _print_summary(self, summary: Dict[str, Any]):
        """테스트 결과 요약 출력"""
        print("\n" + "=" * 60)
        print("테스트 결과 요약")
        print("=" * 60)
        print(f"전체 쿼리 수: {summary['total_queries']}")
        print(f"성공: {summary['successful_tests']}")
        print(f"실패: {summary['failed_tests']}")
        print(f"성공률: {summary['success_rate']:.1f}%")
        print(f"테스트 유형: {', '.join(summary['query_types_tested'])}")
        if summary['limit_applied']:
            print(f"제한 적용: {summary['limit_applied']}개")
        print("=" * 60)
    
    def _generate_detailed_analysis(self, results: List[Dict[str, Any]]):
        """상세 분석 리포트 생성"""
        if not results:
            return
            
        print(f"\n📊 상세 실행 분석 리포트 생성 중...")
        
        # 도구 사용 통계
        tool_usage_stats = {}
        tool_performance_stats = {}
        node_execution_stats = {}
        validation_status_stats = {}
        
        for result in results:
            detailed_info = result.get("agent_detailed_info", {})
            
            # 도구 사용 통계 수집
            for tool_result in detailed_info.get("tool_results", []):
                tool_name = tool_result.get("tool_name", "unknown")
                
                if tool_name not in tool_usage_stats:
                    tool_usage_stats[tool_name] = {
                        "count": 0,
                        "success_count": 0,
                        "param_error_count": 0,
                        "error_count": 0,
                        "total_execution_time": 0.0,
                        "avg_execution_time": 0.0
                    }
                
                tool_usage_stats[tool_name]["count"] += 1
                
                status = tool_result.get("status", "unknown")
                if status == "success":
                    tool_usage_stats[tool_name]["success_count"] += 1
                elif status == "param_missing":
                    tool_usage_stats[tool_name]["param_error_count"] += 1
                else:
                    tool_usage_stats[tool_name]["error_count"] += 1
                
                exec_time = tool_result.get("execution_time", 0.0)
                tool_usage_stats[tool_name]["total_execution_time"] += exec_time
            
            # 노드 실행 통계
            for node_trace in detailed_info.get("node_traces", []):
                node_name = node_trace.get("node_name", "unknown")
                if node_name not in node_execution_stats:
                    node_execution_stats[node_name] = 0
                node_execution_stats[node_name] += 1
            
            # 검증 상태 통계
            final_status = detailed_info.get("final_state", {}).get("validation_status", "unknown")
            if final_status not in validation_status_stats:
                validation_status_stats[final_status] = 0
            validation_status_stats[final_status] += 1
        
        # 평균 실행 시간 계산
        for tool_name, stats in tool_usage_stats.items():
            if stats["count"] > 0:
                stats["avg_execution_time"] = stats["total_execution_time"] / stats["count"]
        
        # 분석 리포트 저장
        analysis_report = {
            "generated_at": datetime.now().isoformat(),
            "total_tests": len(results),
            "tool_usage_statistics": tool_usage_stats,
            "node_execution_statistics": node_execution_stats,
            "validation_status_statistics": validation_status_stats,
            "performance_summary": {
                "most_used_tools": sorted(tool_usage_stats.items(), key=lambda x: x[1]["count"], reverse=True)[:5],
                "slowest_tools": sorted(tool_usage_stats.items(), key=lambda x: x[1]["avg_execution_time"], reverse=True)[:5],
                "most_error_prone_tools": sorted(
                    [(name, stats) for name, stats in tool_usage_stats.items() if stats["count"] > 0],
                    key=lambda x: (x[1]["error_count"] + x[1]["param_error_count"]) / x[1]["count"],
                    reverse=True
                )[:5]
            }
        }
        
        # 분석 리포트 파일 저장
        analysis_filename = f"detailed_analysis_{self.test_timestamp}.json"
        analysis_path = os.path.join(self.results_dir, analysis_filename)
        
        with open(analysis_path, 'w', encoding='utf-8') as f:
            json.dump(analysis_report, f, ensure_ascii=False, indent=2)
        
        print(f"📊 상세 분석 리포트 저장: {analysis_filename}")
        
        # 콘솔에 주요 통계 출력
        print(f"\n🔍 주요 통계:")
        print(f"  - 총 도구 호출: {sum(stats['count'] for stats in tool_usage_stats.values())}")
        print(f"  - 가장 많이 사용된 도구: {analysis_report['performance_summary']['most_used_tools'][0][0] if analysis_report['performance_summary']['most_used_tools'] else 'N/A'}")
        print(f"  - 평균 실행 시간이 가장 긴 도구: {analysis_report['performance_summary']['slowest_tools'][0][0] if analysis_report['performance_summary']['slowest_tools'] else 'N/A'}")
        
        if validation_status_stats:
            print(f"  - 검증 상태 분포:")
            for status, count in validation_status_stats.items():
                print(f"    * {status}: {count}개 ({count/len(results)*100:.1f}%)")
        
        print("=" * 60)


def parse_arguments():
    """CLI 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="통합 배치 테스터 - 주식 검색 에이전트 테스트 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python batch_tester.py                                    # 대화형 모드
  python batch_tester.py --limit 10                         # 처음 10개만 테스트
  python batch_tester.py --type simple                      # 기본 쿼리만 테스트
  python batch_tester.py --type conditional --limit 5       # 조건 쿼리 5개만 테스트
  python batch_tester.py --type simple,signal               # 기본+시그널 쿼리 테스트
  python batch_tester.py --all                              # 모든 쿼리 테스트 (대화형 없이)
        """
    )
    
    parser.add_argument(
        "--type", 
        type=str,
        help="테스트할 쿼리 유형 (simple, conditional, signal, open). 쉼표로 구분하여 여러 개 지정 가능"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        help="테스트할 최대 쿼리 수"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="모든 쿼리 테스트 (대화형 모드 건너뛰기)"
    )
    
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="대화형 모드 강제 실행 (다른 옵션 무시)"
    )
    
    return parser.parse_args()

def main():
    """메인 실행 함수"""
    args = parse_arguments()
    
    print("통합 배치 테스터")
    print("=" * 50)
    
    tester = BatchTester()
    
    # 대화형 모드 강제 실행
    if args.interactive:
        run_interactive_mode(tester)
        return
    
    # CLI 인자가 있으면 바로 실행
    if args.type or args.limit or args.all:
        run_cli_mode(tester, args)
        return
    
    # 인자가 없으면 대화형 모드
    run_interactive_mode(tester)

def run_cli_mode(tester: BatchTester, args):
    """CLI 모드 실행"""
    try:
        # 쿼리 유형 파싱
        query_types = None
        if args.type:
            query_types = [t.strip() for t in args.type.split(",")]
            # 유효성 검사
            valid_types = ["simple", "conditional", "signal", "open"]
            for qt in query_types:
                if qt not in valid_types:
                    print(f"❌ 잘못된 쿼리 유형: {qt}")
                    print(f"   사용 가능한 유형: {', '.join(valid_types)}")
                    return
        elif args.all:
            query_types = ["simple", "conditional", "signal", "open"]
        
        # 테스트 정보 출력
        type_str = f" ({', '.join(query_types)})" if query_types else ""
        limit_str = f" (최대 {args.limit}개)" if args.limit else ""
        print(f"\n🚀 배치 테스트 시작{type_str}{limit_str}")
        
        # 테스트 실행
        summary = tester.run_batch_test(query_types=query_types, limit=args.limit)
        
        print(f"\n✅ 테스트 완료! 성공률: {summary['success_rate']:.1f}%")
        
    except Exception as e:
        print(f"\n❌ 테스트 실행 중 오류 발생: {e}")
        traceback.print_exc()

def run_interactive_mode(tester: BatchTester):
    """대화형 모드 실행"""
    print("\n테스트 옵션을 선택하세요:")
    print("1. 전체 테스트 (모든 유형, 모든 쿼리)")
    print("2. 기본 쿼리만 테스트")
    print("3. 조건 쿼리만 테스트") 
    print("4. 시그널 쿼리만 테스트")
    print("5. 오픈 쿼리만 테스트")
    print("6. 제한된 테스트 (처음 50개)")
    print("7. 제한된 테스트 (처음 5개)")
    
    choice = input("\n선택 (1-6): ").strip()
    
    try:
        if choice == "1":
            print("\n전체 배치 테스트를 시작합니다...")
            summary = tester.run_batch_test()
            
        elif choice == "2":
            print("\n기본 쿼리 테스트를 시작합니다...")
            summary = tester.run_batch_test(query_types=["simple"])
            
        elif choice == "3":
            print("\n조건 쿼리 테스트를 시작합니다...")
            summary = tester.run_batch_test(query_types=["conditional"])
            
        elif choice == "4":
            print("\n시그널 쿼리 테스트를 시작합니다...")
            summary = tester.run_batch_test(query_types=["signal"])
            
        elif choice == "5":
            print("\n오픈 쿼리 테스트를 시작합니다...")
            summary = tester.run_batch_test(query_types=["open"])
            
        elif choice == "6":
            print("\n제한된 배치 테스트 (50개)를 시작합니다...")
            summary = tester.run_batch_test(limit=50)
            
        elif choice == "7":
            print("\n제한된 배치 테스트 (5개)를 시작합니다...")
            summary = tester.run_batch_test(limit=5)
            
        else:
            print("잘못된 선택입니다.")
            return
            
        print(f"\n✅ 테스트 완료! 성공률: {summary['success_rate']:.1f}%")
        
    except Exception as e:
        print(f"\n❌ 테스트 실행 중 오류 발생: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()