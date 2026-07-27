"""카카오맵(성심당 본점) 리뷰 데이터 전처리 / Feature Engineering.

입력 : database/reviews_kakaomap.csv (컬럼: rating, date, content)
출력 : {output_dir}/preprocessed_reviews_kakaomap.csv
"""

import os
import re
from typing import List

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from review_analysis.preprocessing.base_processor import BaseDataProcessor


# 별점 유효 범위 (카카오맵은 1~5점)
MIN_RATING, MAX_RATING = 1.0, 5.0

# 리뷰 길이 하한. 이보다 짧으면 정보량이 없는 리뷰로 판단 ("ㅎㅎ", "애용" 등)
MIN_TEXT_LEN = 5

# 날짜 하한. 성심당 본점 카카오맵 리뷰가 존재할 수 없는 과거 시점
MIN_DATE = pd.Timestamp("2010-01-01")

# 한글/영문/숫자/공백만 남기기 위한 패턴 (이모지, 특수문자, 자음·모음 단독 제거)
NON_TEXT_PATTERN = re.compile(r"[^가-힣a-zA-Z0-9\s]")
MULTI_SPACE_PATTERN = re.compile(r"\s+")
EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F0FF⬀-⯿]"
)

# 조사/어미만 남은 토큰과 의미 없는 고빈도어
STOPWORDS = {
    "그리고", "그래서", "하지만", "그런데", "정말", "진짜", "너무", "아주", "매우", "조금",
    "그냥", "역시", "다시", "항상", "언제", "이런", "저런", "그런", "여기", "거기", "저기",
    "이거", "그거", "저거", "우리", "제가", "저는", "근데", "약간", "완전", "엄청", "많이",
    "좀더", "라서", "인데", "해서", "하고", "이고", "에서", "으로", "이라", "니까", "까지",
    "부터", "보다", "처럼", "같이", "같은", "있는", "없는", "하는", "되는", "된다", "한다",
    "합니다", "했어요", "해요", "이에요", "예요", "에요", "네요", "더라", "더라구요", "같아요",
    "있어요", "없어요", "같습니다", "입니다", "것이", "것은", "것을", "때문", "정도", "느낌",
}

# 조사처럼 끝나지만 떼면 안 되는 고유명사 (예: '튀김소보로'의 '로')
PROTECTED_WORDS = {
    "튀김소보로", "망고시루", "딸기시루", "판타지아", "부추빵", "명란바게트",
    "보문산메아리", "메아리", "성심당", "대전역", "케익부띠끄",
}

# 길이 3 이상 토큰 뒤에 붙은 조사를 떼기 위한 패턴
JOSA_PATTERN = re.compile(
    r"(은|는|이|가|을|를|에|의|도|만|과|와|께|로|으로|에서|에게|한테|처럼|보다|까지|부터|"
    r"이나|라도|이라도|이며|하고|랑|이랑)$"
)


def tokenize(text: str) -> List[str]:
    """공백 기준 토큰화 후 조사 제거 + 불용어 제거.

    konlpy 등 형태소 분석기를 쓰지 않고도 재현 가능하도록 규칙 기반으로 처리한다.
    """
    tokens = []
    for raw in str(text).split():
        token = raw
        # '평일에도'처럼 조사가 겹친 경우가 있어 최대 2회까지 제거.
        # 단, 고유명사는 조사처럼 끝나도 원형을 유지한다.
        for _ in range(2):
            if len(token) < 3 or token in PROTECTED_WORDS:
                break
            token = JOSA_PATTERN.sub("", token)
        if len(token) < 2 or token in STOPWORDS:
            continue
        tokens.append(token)
    return tokens


class KakaomapProcessor(BaseDataProcessor):
    """카카오맵 리뷰 전처리기."""

    SITE_NAME = "kakaomap"

    def __init__(self, input_path: str, output_dir: str):
        super().__init__(input_path, output_dir)
        self.df = pd.read_csv(input_path, encoding="utf-8-sig")
        self.raw_count = len(self.df)
        self.report: List[str] = []
        self.tfidf_matrix = None
        self.tfidf_terms: List[str] = []

    # ------------------------------------------------------------------ #
    # 1. 전처리
    # ------------------------------------------------------------------ #
    def preprocess(self):
        # 팀 공통 스키마(rating, date, content) 중 본문 컬럼만 review로 통일
        df = self.df.rename(columns={"content": "review"})
        df = df[["rating", "date", "review"]].copy()

        # (1) 결측치 처리 -------------------------------------------------
        # 공백만 있는 리뷰도 결측으로 간주한 뒤, 핵심 3개 컬럼 중 하나라도 비면 제거
        df["review"] = df["review"].astype(str).str.strip().replace({"": None, "nan": None})
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
        before = len(df)
        df = df.dropna(subset=["rating", "date", "review"])
        self._log("결측치 제거", before - len(df))

        # (2) 중복 제거 ---------------------------------------------------
        before = len(df)
        df = df.drop_duplicates(subset=["date", "review"], keep="first")
        self._log("중복 리뷰 제거", before - len(df))

        # (3) 별점 이상치 처리 --------------------------------------------
        before = len(df)
        df = df[df["rating"].between(MIN_RATING, MAX_RATING)]
        self._log(f"별점 범위({MIN_RATING}~{MAX_RATING}) 이탈 제거", before - len(df))

        # (4) 날짜 이상치 처리 --------------------------------------------
        # 'YYYY.MM.DD.' 형식을 datetime으로 변환, 파싱 실패/미래/과거 이상치 제거
        df["date"] = pd.to_datetime(
            df["date"].astype(str).str.strip().str.rstrip("."),
            format="%Y.%m.%d",
            errors="coerce",
        )
        before = len(df)
        df = df.dropna(subset=["date"])
        self._log("날짜 파싱 실패 제거", before - len(df))

        before = len(df)
        crawled_at = df["date"].max()  # 크롤링 시점 이후 날짜는 존재할 수 없음
        df = df[(df["date"] >= MIN_DATE) & (df["date"] <= crawled_at)]
        self._log(f"날짜 범위({MIN_DATE.date()}~{crawled_at.date()}) 이탈 제거", before - len(df))

        # (5) 텍스트 전처리 -----------------------------------------------
        # 이모지 개수는 제거 전에 미리 세어 파생변수로 활용
        df["emoji_count"] = df["review"].apply(lambda t: len(EMOJI_PATTERN.findall(t)))
        df["review_len"] = df["review"].str.len()  # 원문 길이 (이상치 판단용)

        df["review_clean"] = (
            df["review"]
            .str.replace(r"\n+", " ", regex=True)          # 줄바꿈 -> 공백
            .apply(lambda t: NON_TEXT_PATTERN.sub(" ", t))  # 특수문자/이모지 제거
            .apply(lambda t: MULTI_SPACE_PATTERN.sub(" ", t).strip())
        )
        df["tokens"] = df["review_clean"].apply(tokenize)

        # (6) 리뷰 길이 이상치 처리 ---------------------------------------
        # 하한: 절대 기준(5자 미만) / 상한: IQR 1.5 fence
        q1, q3 = df["review_len"].quantile([0.25, 0.75])
        upper = q3 + 1.5 * (q3 - q1)

        before = len(df)
        df = df[df["review_len"] >= MIN_TEXT_LEN]
        self._log(f"너무 짧은 리뷰 제거(<{MIN_TEXT_LEN}자)", before - len(df))

        before = len(df)
        df = df[df["review_len"] <= upper]
        self._log(f"너무 긴 리뷰 제거(>{upper:.0f}자, IQR 1.5 fence)", before - len(df))

        # 불용어 제거 후 남은 토큰이 없는 리뷰 제거
        before = len(df)
        df = df[df["tokens"].apply(len) > 0]
        self._log("불용어 제거 후 빈 리뷰 제거", before - len(df))

        self.df = df.sort_values("date").reset_index(drop=True)
        return self.df

    # ------------------------------------------------------------------ #
    # 2. Feature Engineering
    # ------------------------------------------------------------------ #
    def feature_engineering(self):
        df = self.df
        weekday_kr = ["월", "화", "수", "목", "금", "토", "일"]

        # (1) 날짜 파생변수 -----------------------------------------------
        df["year"] = df["date"].dt.year
        df["month"] = df["date"].dt.month
        df["year_month"] = df["date"].dt.to_period("M").astype(str)
        df["quarter"] = df["date"].dt.quarter
        df["weekday"] = df["date"].dt.weekday
        df["weekday_name"] = df["weekday"].map(lambda i: weekday_kr[i])
        df["is_weekend"] = (df["weekday"] >= 5).astype(int)

        # (2) 텍스트 파생변수 ---------------------------------------------
        df["clean_len"] = df["review_clean"].str.len()
        df["word_count"] = df["tokens"].apply(len)

        # (3) 별점 파생변수 -----------------------------------------------
        df["rating_group"] = pd.cut(
            df["rating"], bins=[0, 2, 3, 5], labels=["부정", "중립", "긍정"]
        ).astype(str)

        # (4) 도메인 파생변수: 성심당 리뷰의 핵심 화두인 '웨이팅' 언급 여부
        df["mentions_wait"] = (
            df["review_clean"].str.contains("웨이팅|대기|줄서|줄 서|기다", regex=True).astype(int)
        )

        # (5) 텍스트 벡터화 (TF-IDF) ---------------------------------------
        corpus = df["tokens"].apply(lambda ts: " ".join(ts))
        vectorizer = TfidfVectorizer(
            max_features=100,
            min_df=2,
            token_pattern=r"(?u)\S+",  # 이미 토큰화된 문자열이므로 공백 기준 분리
        )
        matrix = vectorizer.fit_transform(corpus)
        self.tfidf_matrix = matrix
        self.tfidf_terms = list(vectorizer.get_feature_names_out())

        tfidf_df = pd.DataFrame(
            matrix.toarray(),
            columns=[f"tfidf_{t}" for t in self.tfidf_terms],
            index=df.index,
        )
        self.df = pd.concat([df, tfidf_df], axis=1)
        self.report.append(f"TF-IDF 벡터화: {matrix.shape[0]}개 리뷰 x {matrix.shape[1]}개 term")
        return self.df

    # ------------------------------------------------------------------ #
    # 3. 저장
    # ------------------------------------------------------------------ #
    def save_to_database(self):
        os.makedirs(self.output_dir, exist_ok=True)
        out = self.df.copy()
        out["date"] = out["date"].dt.strftime("%Y-%m-%d")
        out["tokens"] = out["tokens"].apply(lambda ts: " ".join(ts))

        output_path = os.path.join(
            self.output_dir, f"preprocessed_reviews_{self.SITE_NAME}.csv"
        )
        out.to_csv(output_path, index=False, encoding="utf-8-sig")

        print(f"[KakaomapProcessor] {self.raw_count}행 -> {len(out)}행")
        for line in self.report:
            print(f"  - {line}")
        print(f"  저장 완료: {output_path} (컬럼 {out.shape[1]}개)")
        return output_path

    # ------------------------------------------------------------------ #
    def _log(self, name: str, removed: int):
        self.report.append(f"{name}: {removed}행")
