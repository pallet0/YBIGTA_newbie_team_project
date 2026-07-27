import os
import re
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore

from review_analysis.preprocessing.base_processor import BaseDataProcessor

class NavermapProcessor(BaseDataProcessor):
    def __init__(self, input_path: str, output_path: str):
        super().__init__(input_path, output_path)

    def preprocess(self):
        df = pd.read_csv(self.input_path)
 
        # 1. 결측치 처리: 별점/리뷰/날짜 중 결측치가 있을 경우 행 제거
        df = df.dropna(subset=["rating", "date", "content"])
 
        # 2. 별점 이상치 처리
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
        df = df.dropna(subset=["rating"])
        df = df[(df["rating"] >= 0.5) & (df["rating"] <= 5.0)]
 
        # 3. 날짜 파싱 + 이상치 처리: "2026년 7월 22일 수요일" -> datetime, 요일 제거
        df["date"] = df["date"].str.extract(r"(\d{4}년 \d{1,2}월 \d{1,2}일)")[0]
        df["date"] = pd.to_datetime(df["date"], format="%Y년 %m월 %d일", errors="coerce")
        df = df.dropna(subset=["date"])
        today = pd.Timestamp.today()
        df = df[(df["date"] >= "2015-01-01") & (df["date"] <= today)]
 
        # 4. 텍스트 전처리: 특수문자/이모지 제거, 공백 정리
        def clean_text(text: str) -> str:
            text = re.sub(r"[^\w\s가-힣]", " ", str(text)) 
            text = re.sub(r"\s+", " ", text).strip()
            return text
 
        df["content"] = df["content"].apply(clean_text)

        # 5. 이상치 처리 (텍스트 길이): 너무 짧은 리뷰(3자 미만)제거
        df["review_length"] = df["content"].str.len()
        df = df[(df["review_length"] >= 3) & (df["review_length"] <= 500)]

        # 6. 범주형 컬럼 결측 대체 (별도 정보 없음 -> "정보없음")
        for col in ["visit_time", "reservation", "wait_time"]:
            df[col] = df[col].fillna("정보없음")
 
        self.df = df.reset_index(drop=True)
        return self.df    

    def feature_engineering(self):
        df = self.df

        # 파생변수 1. 요일 (date에서 추출, 시계열 비교분석용)
        df["weekday"] = df["date"].dt.day_name()

        # 파생변수 2. 별점 z점수 
        df["rating_zscore"] = (df["rating"] - df["rating"].mean()) / df["rating"].std()

        # 파생변수 3. 대기 시간 수치화 (wait_time -> wait_time_minutes)
        wait_mapping = {
            "바로 입장": 0, 
            "10분 이내": 5, 
            "30분 이내": 20, 
            "30분 이상": 45, 
            "1시간 이상": 90, 
            "2시간 이상": 120
        }
        df["wait_time_minutes"] = df["wait_time"].map(wait_mapping)

        # 파생변수 4. 예약 여부 이진화 (reservation -> is_reserved)
        df["is_reserved"] = df["reservation"].apply(lambda x: 0 if "없이" in str(x) else 1)

        # 텍스트 벡터화: TF-IDF
        tfidf_vectorizer = TfidfVectorizer(max_features=100)
        tfidf_matrix = tfidf_vectorizer.fit_transform(df["content"])
        tfidf_df = pd.DataFrame(
            tfidf_matrix.toarray(),
            columns=[f"tfidf_{w}" for w in tfidf_vectorizer.get_feature_names_out()],
        )

        self.df = pd.concat([df.reset_index(drop=True), tfidf_df], axis=1)
        return self.df

    def save_to_database(self):
        os.makedirs(self.output_dir, exist_ok=True)
        output_path = os.path.join(self.output_dir, "preprocessed_reviews_navermap.csv")
        self.df.to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"Saved: {output_path} ({len(self.df)} rows)")
