# -*- coding: utf-8 -*-
import pandas as pd
import os
from typing import List

def load_queries_from_csv(csv_file_path: str) -> List[str]:
    """CSV 파일에서 질문들만 추출해서 리스트로 반환"""
    try:
        df = pd.read_csv(csv_file_path, encoding='utf-8-sig')
        questions = df['question'].tolist()
        print(f"✓ {len(questions)}개 쿼리 로드됨: {csv_file_path}")
        return questions
    except Exception as e:
        print(f"✗ CSV 로드 실패: {e}")
        return []

def get_simple_queries(query_folder: str, count: int = 5) -> List[str]:
    """simple_queries.csv에서 질문들 가져오기"""
    csv_path = os.path.join(query_folder, "simple_queries.csv")
    questions = load_queries_from_csv(csv_path)
    return questions[:count] if questions else []

def get_conditional_queries(query_folder: str, count: int = 5) -> List[str]:
    """conditional_queries.csv에서 질문들 가져오기"""
    csv_path = os.path.join(query_folder, "conditional_queries.csv")
    questions = load_queries_from_csv(csv_path)
    return questions[:count] if questions else []

def get_signal_queries(query_folder: str, count: int = 5) -> List[str]:
    """signal_queries.csv에서 질문들 가져오기"""
    csv_path = os.path.join(query_folder, "signal_queries.csv")
    questions = load_queries_from_csv(csv_path)
    return questions[:count] if questions else []