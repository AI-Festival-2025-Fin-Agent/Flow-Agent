import requests
import pandas as pd
import json
import time
from datetime import datetime
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API 서버 설정
API_BASE_URL = "http://localhost:8000"  # 또는 실제 서버 주소
SEARCH_ENDPOINT = f"{API_BASE_URL}/search"

def test_api_performance():
    """
    CSV 파일의 질문들을 API에 요청하고 결과와 시간을 측정
    """
    # CSV 파일 읽기
    csv_path = "/home/sese/Clova-FinAgent/test_folder/query/conditional_queries.csv"

    try:
        # 다양한 인코딩 시도
        encodings = ['utf-8-sig', 'utf-8', 'euc-kr', 'cp949']
        df = None

        for encoding in encodings:
            try:
                df = pd.read_csv(csv_path, encoding=encoding)
                logger.info(f"CSV 파일 로드 완료 ({encoding}): {len(df)} 개의 질문")
                break
            except UnicodeDecodeError:
                continue

        if df is None:
            raise Exception("모든 인코딩 시도 실패")

    except Exception as e:
        logger.error(f"CSV 파일 읽기 실패: {e}")
        return

    results = []

    for index, row in df.iterrows():
        time.sleep(5)
        question = row['question']
        expected_answer = row['expected_answer']

        logger.info(f"테스트 {index + 1}/{len(df)}: {question[:50]}...")

        # API 요청 시작 시간 기록
        start_time = time.time()

        try:
            # API 요청
            response = requests.post(
                SEARCH_ENDPOINT,
                json={"question": question},
                headers={"Content-Type": "application/json"},
                timeout=60  # 60초 타임아웃
            )

            # 응답 시간 계산
            end_time = time.time()
            elapsed_time = end_time - start_time

            if response.status_code == 200:
                actual_answer = response.json().get('answer', '')
                logger.info(repr(actual_answer))
                status = "SUCCESS"
            else:
                actual_answer = f"HTTP Error: {response.status_code}"
                status = "ERROR"

        except requests.exceptions.Timeout:
            end_time = time.time()
            elapsed_time = end_time - start_time
            actual_answer = "Request timeout"
            status = "TIMEOUT"

        except Exception as e:
            end_time = time.time()
            elapsed_time = end_time - start_time
            actual_answer = f"Exception: {str(e)}"
            status = "ERROR"

        # 결과 저장
        test_result = {
            "test_id": index + 1,
            "question": question,
            "expected_answer": expected_answer,
            "actual_answer": actual_answer,
            "elapsed_time_seconds": round(elapsed_time, 3),
            "status": status,
            "timestamp": datetime.now().isoformat()
        }

        results.append(test_result)

        # 중간 결과 출력
        logger.info(f"결과: {status}, 시간: {elapsed_time:.3f}초")

        # 서버 부하 방지를 위한 짧은 대기
        time.sleep(0.5)

    # 결과를 JSON 파일로 저장
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"/home/sese/Clova-FinAgent/test_folder/test03_time/test_results_{timestamp}.json"

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"결과 저장 완료: {output_file}")

        # 요약 통계 계산
        total_tests = len(results)
        successful_tests = len([r for r in results if r['status'] == 'SUCCESS'])
        total_time = sum(r['elapsed_time_seconds'] for r in results)
        avg_time = total_time / total_tests if total_tests > 0 else 0

        summary = {
            "test_summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": total_tests - successful_tests,
                "success_rate": round((successful_tests / total_tests) * 100, 2) if total_tests > 0 else 0,
                "total_time_seconds": round(total_time, 3),
                "average_time_seconds": round(avg_time, 3),
                "test_completed_at": datetime.now().isoformat()
            },
            "detailed_results": results
        }

        # 요약이 포함된 최종 결과 저장
        final_output_file = f"/home/sese/Clova-FinAgent/test_folder/test03_time/final_test_results_{timestamp}.json"
        with open(final_output_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        logger.info(f"최종 결과 저장 완료: {final_output_file}")

        # 콘솔에 요약 출력
        print("\n" + "="*50)
        print("테스트 완료 요약")
        print("="*50)
        print(f"전체 테스트: {total_tests}")
        print(f"성공: {successful_tests}")
        print(f"실패: {total_tests - successful_tests}")
        print(f"성공률: {summary['test_summary']['success_rate']}%")
        print(f"총 소요시간: {total_time:.3f}초")
        print(f"평균 응답시간: {avg_time:.3f}초")
        print(f"결과 파일: {final_output_file}")
        print("="*50)

    except Exception as e:
        logger.error(f"결과 저장 실패: {e}")

def check_api_health():
    """API 서버 상태 확인"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            logger.info("API 서버 상태: 정상")
            return True
        else:
            logger.error(f"API 서버 상태 이상: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"API 서버 연결 실패: {e}")
        return False

if __name__ == "__main__":
    print("API 성능 테스트 시작")
    print(f"API 서버: {API_BASE_URL}")

    # API 서버 상태 확인
    if not check_api_health():
        print("API 서버가 실행되지 않았거나 응답하지 않습니다.")
        print("서버를 시작한 후 다시 시도해주세요.")
        exit(1)

    # 테스트 실행
    test_api_performance()