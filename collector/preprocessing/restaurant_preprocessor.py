"""카카오맵(성심당 본점) 리뷰 데이터 전처리.

원본 kakaomap_processor.py를 이번 과제 목적에 맞게 축소해서 재사용.
[수정] 이번 과제는 MCP Tool이 원본 리뷰 텍스트를 조회해서 LLM에게 넘기고
   LLM이 직접 분석하는 구조라, TF-IDF/형태소 분석 기반 Feature Engineering은 제거
[수정] DB INSERT에 바로 쓸 수 있는 dict 리스트를 반환하도록 변경

입력 : crawler가 만든 리뷰 dict 리스트 (restaurant_name, rating, date, content)
출력 : DB reviews 테이블 컬럼에 맞춘 dict 리스트
       (restaurant_name, review_text, rating, review_date, collected_at)
"""

import re
from datetime import datetime
from typing import List, Dict

import pandas as pd


# 별점 유효 범위 (카카오맵은 1~5점)
MIN_RATING, MAX_RATING = 1.0, 5.0

# 리뷰 길이 하한. 이보다 짧으면 정보량이 없는 리뷰로 판단 ("ㅎㅎ", "애용" 등)
MIN_TEXT_LEN = 5

# 날짜 하한. 성심당 본점 카카오맵 리뷰가 존재할 수 없는 과거 시점
MIN_DATE = pd.Timestamp("2010-01-01")

# 한글/영문/숫자/공백만 남기기 위한 패턴 (이모지, 특수문자 제거)
NON_TEXT_PATTERN = re.compile(r"[^가-힣a-zA-Z0-9\s]")
MULTI_SPACE_PATTERN = re.compile(r"\s+")


class RestaurantPreprocessor:
    """크롤러가 수집한 원본 리뷰 리스트를 DB 저장 가능한 형태로 정제한다."""

    def __init__(self, raw_reviews: List[Dict]):
        # [수정] 원본은 CSV/Mongo에서 읽어왔지만, 이번엔 크롤러 결과(dict 리스트)를 바로 받음
        self.raw_reviews = raw_reviews
        self.report: List[str] = []

    def preprocess(self) -> List[Dict]:
        df = pd.DataFrame(self.raw_reviews)
        if df.empty:
            self._log("입력 리뷰 없음", 0)
            return []

        # [수정] 팀 공통 스키마: content -> review_text로 통일 (DB 컬럼명과 맞춤)
        df = df.rename(columns={"content": "review_text", "date": "review_date_raw"})

        # (1) 결측치 처리 -------------------------------------------------
        df["review_text"] = df["review_text"].astype(str).str.strip().replace({"": None, "nan": None})
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
        before = len(df)
        df = df.dropna(subset=["rating", "review_date_raw", "review_text"])
        self._log("결측치 제거", before - len(df))

        # (2) 중복 제거 (이번 크롤링 배치 내에서) --------------------------
        before = len(df)
        df = df.drop_duplicates(subset=["review_date_raw", "review_text"], keep="first")
        self._log("중복 리뷰 제거", before - len(df))

        # (3) 별점 이상치 처리 --------------------------------------------
        before = len(df)
        df = df[df["rating"].between(MIN_RATING, MAX_RATING)]
        self._log(f"별점 범위({MIN_RATING}~{MAX_RATING}) 이탈 제거", before - len(df))

        # (4) 날짜 파싱 -----------------------------------------------------
        # 'YYYY.MM.DD.' 형식을 datetime으로 변환, 파싱 실패/미래/과거 이상치 제거
        df["review_date"] = pd.to_datetime(
            df["review_date_raw"].astype(str).str.strip().str.rstrip("."),
            format="%Y.%m.%d",
            errors="coerce",
        )
        before = len(df)
        df = df.dropna(subset=["review_date"])
        self._log("날짜 파싱 실패 제거", before - len(df))

        before = len(df)
        crawled_at = df["review_date"].max()  # 크롤링 시점 이후 날짜는 존재할 수 없음
        df = df[(df["review_date"] >= MIN_DATE) & (df["review_date"] <= crawled_at)]
        self._log("날짜 범위 이탈 제거", before - len(df))

        # (5) 텍스트 정제 ---------------------------------------------------
        df["review_text"] = (
            df["review_text"]
            .str.replace(r"\n+", " ", regex=True)          # 줄바꿈 -> 공백
            .apply(lambda t: NON_TEXT_PATTERN.sub(" ", t))  # 특수문자/이모지 제거
            .apply(lambda t: MULTI_SPACE_PATTERN.sub(" ", t).strip())
        )

        before = len(df)
        df = df[df["review_text"].str.len() >= MIN_TEXT_LEN]
        self._log(f"너무 짧은 리뷰 제거(<{MIN_TEXT_LEN}자)", before - len(df))

        # (6) DB 저장용 컬럼만 최종 정리 -------------------------------------
        df["review_date"] = df["review_date"].dt.strftime("%Y-%m-%d")  # DB DATE 타입에 맞춤

        result = df[["restaurant_name", "review_text", "rating", "review_date"]].to_dict("records")
        # [수정] collected_at을 df 컬럼으로 넣으면 pandas Timestamp가 되어 pymysql이 못 읽을 수 있어서,
        #        dict로 변환한 뒤 순수 Python datetime으로 각 행에 직접 넣어줌
        now = datetime.now()
        for r in result:
            r["collected_at"] = now
        return result

    # [삭제] 원본의 feature_engineering(), TF-IDF 벡터화 부분은 제거

    def _log(self, name: str, removed: int):
        self.report.append(f"{name}: {removed}행")
        print(f"  - {name}: {removed}행")