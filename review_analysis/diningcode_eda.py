from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# 경로 사전지정
review_analysis_dir = Path(__file__).resolve().parent
project_dir = review_analysis_dir.parent

input_path = project_dir / "database" / "reviews_diningcode.csv"
plots_dir = review_analysis_dir / "plots"

# 대상 폴더가 없으면 만들기
plots_dir.mkdir(parents=True, exist_ok=True)

# 깡데이터 불러오기
df = pd.read_csv(input_path, encoding="utf-8-sig")

df["rating"] = pd.to_numeric(df["rating"], errors="coerce")

df["content"] = df["content"].astype("string").str.strip()
df["content_length"] = df["content"].str.len()

# 가벼운 전처리 (diningcode_processor와 유사)
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


# 1. 별점 분포 그래프
rating_counts = df["rating"].value_counts().sort_index()

plt.figure(figsize=(8, 5))
rating_counts.plot(kind="bar")

plt.title("DiningCode Rating Distribution")
plt.xlabel("Rating")
plt.ylabel("Review Count")
plt.tight_layout()

plt.savefig(plots_dir / "diningcode_rating_distribution.png")
plt.close()

# 1.1. 별점 이상치
invalid_ratings = df[
    df["rating"].notna()
    & ~df["rating"].between(1, 5)
]
print("Invalid rating count:", len(invalid_ratings))


# 2. 리뷰 길이 분포
plt.figure(figsize=(8, 5))
df["content_length"].plot(kind="hist", bins=30)

plt.title("DiningCode Review Length Distribution")
plt.xlabel("Review Length")
plt.ylabel("Review Count")
plt.tight_layout()

plt.savefig(
    plots_dir / "diningcode_content_length_distribution.png"
)
plt.close()


# 3. 리뷰 길이 이상치 그래프
plt.figure(figsize=(8, 4))
df["content_length"].plot(kind="box", vert=False)

plt.title("DiningCode Review Length Boxplot")
plt.xlabel("Review Length")
plt.tight_layout()

plt.savefig(
    plots_dir / "diningcode_content_length_boxplot.png"
)
plt.close()

# 3.1. 이상치 일부
print(
    df[["content", "content_length"]]
    .sort_values("content_length")
    .head(10)
)

print(
    df[["content", "content_length"]]
    .sort_values("content_length", ascending=False)
    .head(10)
)


# 4. 날짜 분포
monthly_counts = (
    df.dropna(subset=["date"])
    .set_index("date")
    .resample("ME")
    .size()
)

plt.figure(figsize=(10, 5))
monthly_counts.plot(kind="line")

plt.title("DiningCode Monthly Review Count")
plt.xlabel("Date")
plt.ylabel("Review Count")
plt.tight_layout()

plt.savefig(plots_dir / "diningcode_date_distribution.png")
plt.close()


# 4.1. 날자 이상치
today = pd.Timestamp.today().normalize()

future_dates = df[df["date"] > today]

print("Earliest date:", df["date"].min())
print("Latest date:", df["date"].max())
print("Future review count:", len(future_dates))
