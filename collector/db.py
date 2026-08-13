"""collector에서 사용하는 DB 연결 및 저장/조회 함수 모음.

 DB 관련 로직만 따로 분리해두면
- crawling/preprocessing 코드는 DB를 몰라도 되고 (책임 분리)
- 나중에 DB 연결 정보나 쿼리를 수정할 때 이 파일만 고치면 되기 때문에 추가함.
"""

import os
from typing import List, Dict, Set, Tuple

import pymysql
from dotenv import load_dotenv

load_dotenv()  # 프로젝트 최상위 .env 로드


def get_connection():
    """RDS(MySQL) 커넥션을 생성한다."""
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4",
    )


def fetch_existing_keys(restaurant_name: str) -> Set[Tuple[str, str]]:
    """이미 저장된 (review_date, review_text) 조합을 가져온다.

    cron이 주기적으로 재실행될 때, 이미 DB에 있는 리뷰를 다시 저장하지 않도록
    저장 전에 걸러내는 용도로 사용한다.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT review_date, review_text FROM reviews WHERE restaurant_name = %s",
                (restaurant_name,),
            )
            rows = cursor.fetchall()
        return {(str(r[0]), r[1]) for r in rows}
    finally:
        conn.close()


def save_reviews(reviews: List[Dict]) -> int:
    """전처리 완료된 리뷰 리스트를 reviews 테이블에 저장한다.

    Returns:
        실제로 저장된 행 수
    """
    if not reviews:
        return 0

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO reviews
                    (restaurant_name, review_text, rating, review_date, collected_at)
                VALUES (%s, %s, %s, %s, %s)
            """
            for r in reviews:
                cursor.execute(
                    sql,
                    (
                        r["restaurant_name"],
                        r["review_text"],
                        r["rating"],
                        r["review_date"],
                        r["collected_at"],
                    ),
                )
        conn.commit()
        return len(reviews)
    finally:
        conn.close()
        

def get_latest_review_date(restaurant_name: str):
    """[추가] 해당 식당의 DB에 저장된 가장 최신 review_date를 반환. 없으면 None."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT MAX(review_date) FROM reviews WHERE restaurant_name = %s",
                (restaurant_name,),
            )
            row = cursor.fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()