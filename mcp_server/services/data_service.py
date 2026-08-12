"""
data_service.py

MCP Tool이 직접 호출하는 레이어.
- 입력값 검증(validation)을 여기서 수행한다
- Repository를 호출해서 결과를 받아오되, 비즈니스 로직(범위 제한 등)은 여기서 처리
- MCP Tool 함수(server.py에서 @mcp.tool()로 등록될 함수)는 이 함수들만 부르면 됨
"""

from datetime import datetime

from repositories.data_repository import ReviewRepository

_repo = ReviewRepository()


def get_latest_data(limit: int = 10) -> list[dict]:
    """
    가장 최근에 수집된 리뷰 데이터를 조회한다.

    Args:
        limit: 가져올 개수 (기본 10, 최대 100으로 자동 제한됨)
    """
    return _repo.get_latest(limit=limit)


def search_data(
    keyword: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    키워드 및 기간으로 리뷰를 검색한다.

    Args:
        keyword: 리뷰 본문 또는 식당명에 포함된 검색어 (선택)
        start_date: 조회 시작일, 'YYYY-MM-DD' 형식 (선택)
        end_date: 조회 종료일, 'YYYY-MM-DD' 형식 (선택)
        limit: 가져올 개수 (기본 10, 최대 100)
    """
    _validate_date_format(start_date)
    _validate_date_format(end_date)

    return _repo.search(
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


def get_statistics(column: str = "rating") -> dict:
    """
    지정한 컬럼의 평균/최소/최대/개수 통계를 반환한다.

    Args:
        column: 통계를 낼 컬럼명. 현재 'rating'만 허용됨.
    """
    return _repo.get_statistics(column=column)


def _validate_date_format(date_str: str | None) -> None:
    """'YYYY-MM-DD' 형식인지 검증. 아니면 명확한 에러를 던진다."""
    if date_str is None:
        return
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"날짜 형식이 올바르지 않습니다 (YYYY-MM-DD): {date_str}")