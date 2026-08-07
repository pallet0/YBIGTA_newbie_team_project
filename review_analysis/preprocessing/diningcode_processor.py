import pandas as pd
from review_analysis.preprocessing.base_processor import BaseDataProcessor
from sklearn.feature_extraction.text import TfidfVectorizer


class DiningCodeProcessor(BaseDataProcessor):
    """DiningCode 리뷰 데이터의 전처리와 특성 공학을 수행합니다."""

    def __init__(self, input_path: str, output_dir: str) -> None:
        """입력 CSV 경로와 결과 저장 디렉터리를 설정합니다.

        Args:
            input_path: DiningCode 원본 리뷰 CSV 경로
            output_dir: 전처리 결과 CSV를 저장할 곳
        """
        super().__init__(input_path, output_dir)
        self.df: pd.DataFrame = pd.DataFrame()
        self.raw_documents: list[dict] = []  # [수정] Mongo 원본 문서를 담을 변수 추가

    def load_from_mongo(self, documents: list[dict]) -> None:  # [수정] 신규 메서드 추가
        """MongoDB find() 결과(dict 리스트)를 주입받습니다.

        Args:
            documents: raw_reviews 컬렉션에서 site_name="diningcode"로 조회한 문서 리스트
        """
        self.raw_documents = documents

    def preprocess(self) -> None:
        """결측치와 이상치를 처리하고 리뷰 텍스트와 날짜를 정제합니다"""

        min_length, max_length = 30, 400

        # [수정] pd.read_csv(self.input_path) → 주입받은 documents로 DataFrame 생성
        df = pd.DataFrame(self.raw_documents)

        if "_id" in df.columns:  # [수정] Mongo _id는 재삽입 시 충돌 방지를 위해 제거
            df = df.drop(columns=["_id"])

        df.columns = df.columns.str.replace("\ufeff", "", regex=False)  # [수정] BOM 제거


        df["rating"] = pd.to_numeric(df["rating"], errors="coerce") # 평점을 숫자 자료형으로 변환
        df = df.dropna(subset=["rating"])
        df = df[df["rating"].between(1, 5)]

        df["content"] = df["content"].astype("string").str.strip() # 문자열 처음과 끝의 공백제거
        df["content"] = df["content"].replace("", pd.NA) # 공백 -> 결측치로 전환
        df = df.dropna(subset=["content"]) # NA삭제

        # 리뷰 가 너무 길거나 짧으면 제거
        df["content_length"] = df["content"].str.len()
        df = df[df["content_length"].between(min_length, max_length)]

        # 특수문자 제거
        df["cleaned"] = (
            df["content"]
            .str.replace(r"[^가-힣A-Za-z0-9\s]", " ", regex=True)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

        # 날짜 형식 수정; 연도가 누락되는 등 문제를 해결하고, datetime 자료형으로 전환
        date_text = df["date"].astype("string").str.strip()
        date_text = date_text.str.replace(
            r"^(\d{1,2}월\s*\d{1,2}일)$",
            r"2026년 \1",
            regex=True,
        )
        df["date"] = pd.to_datetime(
            date_text,
            format="%Y년 %m월 %d일",
            errors="coerce",
        )
        df = df.dropna(subset=["date"]) # 변환실패시(NaT) 제거

        today = pd.Timestamp.today().normalize()
        df = df[df["date"] <= today]

        # 클래스 변수에 결과 저장
        self.df = df.reset_index(drop=True)

    def feature_engineering(self) -> None:
        """리뷰들을 TF-IDF를 통해 변환하여 데이터에 추가합니다"""

        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(self.df["cleaned"])
        tfidf_df = pd.DataFrame(
            tfidf_matrix.toarray(),
            columns=[
                f"tfidf_{term}"
                for term in vectorizer.get_feature_names_out()
            ],
            index=self.df.index,
        )
        self.df = pd.concat([self.df, tfidf_df], axis=1)


    def save_to_database(self, collection) -> None:  # [수정] output_dir → mongo collection 인자로 변경
        """전처리 및 FE 결과를 MongoDB 컬렉션에 저장합니다.

        Args:
            collection: 저장 대상 MongoDB 컬렉션 (pymongo Collection 객체)
        """
        # [수정] Path/mkdir/to_csv 제거 → insert_many로 변경
        records = self.df.to_dict("records")
        if records:
            collection.delete_many({"site_name": "diningcode"})  # 재실행시 기존 데이터 먼저 삭제
            collection.insert_many(records)
        print(f"Saved to MongoDB: {len(records)} rows")  # [수정] 저장 결과 로그 추가

# [수정] from pathlib import Path 삭제
# [수정] __main__ 블록 전체 삭제 
