#!/usr/bin/env python3
"""
테스트 결과를 Gemini 2.0 Flash로 평가하는 스크립트
"""

import json
import os
import sys
from datetime import datetime
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate

# 프로젝트 루트 경로 설정
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# LLM 설정
from langchain_google_genai import ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    api_key="AIzaSyCRUhHFdJVX7GXrYi1KOos1WotZIAqRjS4",
    thinking_budget=0,
)
from langchain_naver import ChatClovaX
llm = ChatClovaX(
    model = "HCX-007",
    api_key ="nv-3a8c07b7cc5e4006b0f7080d9c502ecbI051",
    thinking={
        "effort": "none"  # 'none' (disabling), 'low' (default), 'medium', or 'high'
    },
)    

# pip install -qU langchain-core langchain-upstage

from langchain_upstage import ChatUpstage

chat = ChatUpstage(
    api_key="up_IXsWAc6FwOaARBA6iRAr5Nhe63f68", 
    model="solar-pro2",
    reasoning_effort="high"
)

json_parser = JsonOutputParser()

# 프롬프트 템플릿
prompt = """
당신은 모델 응답을 평가하는 AI 평가자입니다.
당신이 학습된 지식은 과거이지만 오늘은 2025년 9월 19일 입니다.
문제에서 제시된 정답이 모델 답변에 포함되어 있다면 "정답"으로 간주합니다.

다음은 사용자의 질문, 모델의 응답, 기대 답변입니다.
각 항목에 대해 다음 기준으로 평가하세요:

- 의미상 동일하거나 적절하면 "정답"
- 의미가 다르거나 틀리면 "오답"
- 간단한 이유도 작성해주세요

**오답인 경우 추가로 오류 유형을 분류하세요:**
- "종목명_오류": 종목명이나 회사명이 틀린 경우
- "사소한_숫자_오류": 숫자가 약간 다르지만 크게 의미에 영향을 주지 않는 경우 (예: 반올림 차이, 소수점 차이)
- "심각한_오류": 완전히 틀렸거나 의미가 크게 다른 경우

출력 형식 예시:
- JSON 파싱에 걸리지 않도록 따옴표 등의 처리를 하세요
{{
  "Q": "질문 텍스트",
  "A": "기대하는 정답 텍스트",
  "모델 답변": "모델이 한 답변 텍스트",
  "정답 여부": "정답",
  "오류 유형": "종목명_오류",
  "코멘트": "간단한 이유"
}}

---

아래 실제 데이터에 대해 평가하세요:
질문: {question}
모델 답변: {llm_answer}
정답: {actual_answer}
"""

evaluation_template = PromptTemplate(
    template=prompt,
    input_variables=['question', 'llm_answer', 'actual_answer']
)

# LangChain chain 구성
chain = evaluation_template | llm

def load_test_data(file_path=None):
    """테스트 결과 로드"""
    if file_path is None:
        # 가장 최근 테스트 결과 자동 선택
        test_results_dir = os.path.join(project_root, "test_results")
        detailed_files = [f for f in os.listdir(test_results_dir) if f.startswith("test_detailed_")]
        if not detailed_files:
            raise FileNotFoundError("테스트 결과 파일을 찾을 수 없습니다.")
        
        latest_file = sorted(detailed_files)[-1]
        file_path = os.path.join(test_results_dir, latest_file)
    
    print(f"로딩 중: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data, file_path

def evaluate_responses(file_path=None):
    """응답 평가 실행"""
    print("테스트 결과를 로딩합니다...")
    data, actual_file_path = load_test_data(file_path)
    
    # 새로운 JSON 구조: data는 직접 배열
    logs = data if isinstance(data, list) else data.get("detailed_logs", [])
    
    correct_count = 0
    total = len(logs)
    detailed_results = []
    
    # 오류 유형별 카운터
    error_counts = {
        "종목명_오류": 0,
        "사소한_숫자_오류": 0,
        "심각한_오류": 0,
        "기타_오류": 0
    }
    
    print(f"\n총 {total}개의 응답을 평가합니다.\n")
    
    for idx, log in enumerate(logs):
        print(f"{'='*50}")
        print(f"[{idx+1}] 평가 중: '{log['question'][:50]}...'")
        
        # 빈 답변 처리 (새로운 필드명 사용)
        actual_result = log.get("actual_result", "")
        if not actual_result or actual_result.strip() == "":
            result = {
                "Q": log["question"],
                "A": log["expected_answer"],
                "모델 답변": "(빈 답변)",
                "정답 여부": "오답",
                "오류 유형": "심각한_오류",
                "코멘트": "모델이 답변을 제공하지 않음"
            }
            detailed_results.append(result)
            error_counts["심각한_오류"] += 1
            print("X 빈 답변 - 오답")
            continue
        
        try:
            response = chain.invoke({
                "question": log["question"],
                "llm_answer": actual_result,
                "actual_answer": log["expected_answer"]
            })
            
            print(f"토큰 사용: {response.usage_metadata['input_tokens']} input, {response.usage_metadata['output_tokens']} output")
            print(f"모델 답변: {repr(actual_result)}")
            print(f"정답: {log['expected_answer']}...")
            
            # JSON 파싱 시도
            try:
                result = json_parser.parse(response.content)
                
            except Exception as parse_error:
                print(f"JSON 파싱 실패: {parse_error}")
                try:
                    # 간단한 문자열 처리로 대체
                    result = json.loads(response.content)
                except:
                    # 파싱 실패 시 기본 결과
                    result = {
                        "Q": log["question"],
                        "A": log["expected_answer"], 
                        "모델 답변": actual_result,
                        "정답 여부": "오답",
                        "오류 유형": "기타_오류",
                        "코멘트": "평가 파싱 오류"
                    }
            
            detailed_results.append(result)
            
            # 정답 여부 확인
            if result.get("정답 여부") == "정답":
                correct_count += 1
                print("O 정답")
            else:
                print("X 오답")
                # 오류 유형 집계
                error_type = result.get("오류 유형", "기타_오류")
                if error_type in error_counts:
                    error_counts[error_type] += 1
                else:
                    error_counts["기타_오류"] += 1
                print(f"오류 유형: {error_type}")
            
            print(f"코멘트: {result.get('코멘트', 'N/A')}")
            
        except Exception as e:
            print(f"평가 중 오류 발생: {e}")
            result = {
                "Q": log["question"],
                "A": log["expected_answer"],
                "모델 답변": log["actual_result"],
                "정답 여부": "오답",
                "오류 유형": "기타_오류", 
                "코멘트": f"평가 오류: {str(e)}"
            }
            detailed_results.append(result)
            error_counts["기타_오류"] += 1
    
    # 최종 결과 출력
    accuracy = correct_count / total * 100
    wrong_count = total - correct_count
    
    print(f"\n{'='*60}")
    print(f"최종 평가 결과")
    print(f"{'='*60}")
    print(f"전체 질문 수: {total}")
    print(f"정답 수: {correct_count}")
    print(f"오답 수: {wrong_count}")
    print(f"정확도: {accuracy:.1f}%")
    
    # 오류 유형별 분석 출력
    print(f"\n{'='*60}")
    print(f"오류 유형별 분석")
    print(f"{'='*60}")
    for error_type, count in error_counts.items():
        if count > 0:
            percentage = count / wrong_count * 100 if wrong_count > 0 else 0
            print(f"{error_type}: {count}건 ({percentage:.1f}%)")
    
    # 총 오류 검증
    total_errors = sum(error_counts.values())
    if total_errors != wrong_count:
        print(f"\n⚠️  오류 집계 불일치: 총 오답({wrong_count}) vs 오류 합계({total_errors})")
    
    # 결과 저장
    results_dir = os.path.join(project_root, "test_results")
    # 테스트 파일의 timestamp 추출
    import re
    timestamp_match = re.search(r'test_detailed_(\d{8}_\d{6})\.json', actual_file_path)
    if timestamp_match:
        test_timestamp = timestamp_match.group(1)
    else:
        test_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    output_file = os.path.join(results_dir, f"evaluation_results_{test_timestamp}.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_timestamp": test_timestamp,
            "evaluation_timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "total_questions": total,
            "correct_answers": correct_count,
            "wrong_answers": wrong_count,
            "accuracy": accuracy,
            "error_analysis": error_counts,
            "detailed_results": detailed_results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n결과가 저장되었습니다: {output_file}")
    
    return detailed_results, accuracy

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="테스트 결과 평가")
    parser.add_argument("--file", type=str, help="평가할 테스트 결과 파일 경로 (미지정시 최신 파일 자동 선택)")
    
    args = parser.parse_args()
    
    try:
        results, accuracy = evaluate_responses(args.file)
        print(f"\n평가 완료! 최종 정확도: {accuracy:.1f}%")
    except Exception as e:
        print(f"평가 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()