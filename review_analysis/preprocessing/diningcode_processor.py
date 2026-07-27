from pathlib import Path

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

    def preprocess(self) -> None:
        """결측치와 이상치를 처리하고 리뷰 텍스트와 날짜를 정제합니다"""

        min_length, max_length = 30, 400

        df = pd.read_csv(self.input_path, encoding="utf-8-sig")

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

    def save_to_database(self) -> None:
        """preprocessing 및 FE 결과를 지정된 CSV 파일로 저장합니다."""

        output_dir = Path(self.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "preprocessed_reviews_diningcode.csv"
        self.df.to_csv(output_path, index=False, encoding="utf-8-sig")


if __name__ == '__main__':
    dcp = DiningCodeProcessor(
        str(
            Path(__file__).resolve().parents[2]
            / "database"
            / "reviews_diningcode.csv"
        ),
        str(Path(__file__).resolve().parents[2] / "database"),
    )
    dcp.preprocess()
    dcp.feature_engineering()
    dcp.save_to_database()
