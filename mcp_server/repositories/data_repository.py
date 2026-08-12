"""
data_repository.py

DB와 직접 대화하는 최하위 레이어.
- SQL 쿼리를 여기서만 작성한다 (다른 파일에서는 SQL을 직접 다루지 않음)
- parameterized query만 사용 (SQL Injection 방지)
- mcp_user (read-only 계정)로만 연결한다
"""

import os
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DATABASE_URL")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("MCP_DB_USER")
DB_PASSWORD = os.getenv("MCP_DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "ybigta_agent")

# search_data()에서 사용을 허용할 컬럼 화이트리스트
# (이 목록에 없는 컬럼으로는 필터링/정렬 불가)
ALLOWED_FILTER_COLUMNS = {"restaurant_name", "review_date", "rating"}
ALLOWED_STAT_COLUMNS = {"rating"}

MAX_LIMIT = 100  # 한 번에 조회 가능한 최대 row 수


@contextmanager
def get_connection():
    """
    with get_connection() as conn: 형태로 사용.
    함수가 끝나면(에러가 나도) 커넥션을 확실히 닫아준다.
    """
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        cursorclass=DictCursor,
        connect_timeout=5,   # query timeout 대응: 연결 자체도 5초 이상 안 기다림
        read_timeout=5,
    )
    try:
        yield conn
    finally:
        conn.close()


class ReviewRepository:
    """reviews 테이블 전용 Repository"""

    def get_latest(self, limit: int = 10):
        """
        최신 수집순으로 리뷰를 limit개 가져온다.
        get_latest_data MCP Tool에서 사용.
        """
        limit = self._clamp_limit(limit)

        query = """
            SELECT id, restaurant_name, review_text, rating,
                   review_date, created_at, updated_at, collected_at
            FROM reviews
            ORDER BY collected_at DESC
            LIMIT %s
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (limit,))
                return cur.fetchall()

    def search(
        self,
        keyword: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 10,
    ):
        """
        키워드/기간으로 리뷰를 검색한다.
        search_data MCP Tool에서 사용 (B 담당 Tool이지만, Repository는 공용으로 둠).
        """
        limit = self._clamp_limit(limit)

        conditions = []
        params = []

        if keyword:
            conditions.append("(review_text LIKE %s OR restaurant_name LIKE %s)")
            like_pattern = f"%{keyword}%"
            params.extend([like_pattern, like_pattern])

        if start_date:
            conditions.append("review_date >= %s")
            params.append(start_date)

        if end_date:
            conditions.append("review_date <= %s")
            params.append(end_date)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT id, restaurant_name, review_text, rating,
                   review_date, created_at, updated_at, collected_at
            FROM reviews
            {where_clause}
            ORDER BY review_date DESC
            LIMIT %s
        """
        params.append(limit)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                return cur.fetchall()

    def get_statistics(self, column: str = "rating"):
        """
        지정한 컬럼의 평균/최소/최대/개수를 반환한다.
        get_statistics MCP Tool에서 사용.
        column은 허용된 목록(ALLOWED_STAT_COLUMNS)에 있는 것만 통과시킨다.
        (f-string으로 컬럼명을 넣긴 하지만, 화이트리스트 검증을 반드시 먼저 거치므로
         사용자 입력이 그대로 SQL에 삽입되는 것은 아님)
        """
        if column not in ALLOWED_STAT_COLUMNS:
            raise ValueError(f"허용되지 않은 column입니다: {column}")

        query = f"""
            SELECT
                AVG({column}) AS avg_value,
                MIN({column}) AS min_value,
                MAX({column}) AS max_value,
                COUNT(*) AS count
            FROM reviews
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                return cur.fetchone()

    @staticmethod
    def _clamp_limit(limit: int) -> int:
        """대량 조회 방지: limit이 범위를 벗어나면 안전한 값으로 보정"""
        if limit is None or limit < 1:
            return 10
        if limit > MAX_LIMIT:
            return MAX_LIMIT
        return limit