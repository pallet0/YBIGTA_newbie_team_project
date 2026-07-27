"""시각화 공통 설정 / 데이터 로더.

- 두 사이트 원본 CSV를 하나의 스키마(rating, date, review)로 읽어온다.
- matplotlib 한글 폰트, 색상 팔레트, 스타일을 한 곳에서 관리한다.
"""

import os
import re
import sys

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

DATABASE_DIR = os.path.join(ROOT_DIR, "database")
PLOTS_DIR = os.path.join(ROOT_DIR, "review_analysis", "plots")

# 크롤링 시점. 연도가 없는 다이닝코드 날짜의 연도를 추정하는 기준점으로 사용
CRAWLED_AT = pd.Timestamp("2026-07-27")

# ---------------------------------------------------------------- 색상/스타일
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

# 카테고리 색상 (사이트 = 엔티티). 순서 고정, 순환하지 않음
SERIES = {"카카오맵": "#2a78d6", "다이닝코드": "#eb6834"}

# 순서가 있는 별점(1~5)에 쓰는 단일 색상 ordinal 램프
BLUE_ORDINAL = ["#86b6ef", "#5598e7", "#2a78d6", "#256abf", "#184f95"]

# 극성(부정 ↔ 긍정)을 나타내는 diverging 3색: 중간값은 중립 회색
DIVERGING = {"부정": "#d03b3b", "중립": "#c3c2b7", "긍정": "#2a78d6"}


def setup_style():
    """한글 폰트 + 절제된 차트 크롬 설정."""
    plt.rcParams.update({
        "font.family": "AppleGothic",
        "axes.unicode_minus": False,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "axes.labelcolor": INK_SECONDARY,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "grid.linestyle": "-",       # 점선 그리드는 노이즈가 되므로 실선 hairline
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.frameon": False,
        "legend.fontsize": 10,
        "figure.dpi": 130,
    })


def strip_chrome(ax, keep_x=True):
    """위/오른쪽 축을 지우고 그리드를 y축만 남긴다."""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(AXIS)
    ax.spines["bottom"].set_color(AXIS)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.grid(axis="x", visible=False)
    if not keep_x:
        ax.spines["bottom"].set_visible(False)


def save(fig, filename):
    os.makedirs(PLOTS_DIR, exist_ok=True)
    path = os.path.join(PLOTS_DIR, filename)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  저장: review_analysis/plots/{filename}")
    return path


# ---------------------------------------------------------------- 데이터 로더
_DINING_DATE = re.compile(r"^(?:(\d{4})년\s*)?(\d{1,2})월\s*(\d{1,2})일$")


def _parse_diningcode_date(value):
    """'2025년 11월 9일' / '7월 2일' / '4시간 전' 형식을 datetime으로 변환.

    연도가 없으면 크롤링 시점의 연도로 보고, 그 결과가 미래가 되면 1년을 뺀다.
    """
    text = str(value).strip()
    m = _DINING_DATE.match(text)
    if m:
        year = int(m.group(1)) if m.group(1) else CRAWLED_AT.year
        try:
            date = pd.Timestamp(year, int(m.group(2)), int(m.group(3)))
        except ValueError:
            return pd.NaT
        if m.group(1) is None and date > CRAWLED_AT:
            date = pd.Timestamp(year - 1, int(m.group(2)), int(m.group(3)))
        return date
    if re.search(r"(분|시간|일|주|개월|년)\s*전$", text):  # '4시간 전' 등 상대 표기
        return CRAWLED_AT.normalize()
    return pd.NaT


def load_raw(site):
    """원본 크롤링 CSV를 (rating, date, review) 스키마로 로드. EDA 전용."""
    if site == "카카오맵":
        df = pd.read_csv(os.path.join(DATABASE_DIR, "reviews_kakaomap.csv"), encoding="utf-8-sig")
        df = df.rename(columns={"content": "review"})
        df["date"] = pd.to_datetime(
            df["date"].astype(str).str.strip().str.rstrip("."), format="%Y.%m.%d", errors="coerce"
        )
    elif site == "다이닝코드":
        df = pd.read_csv(os.path.join(DATABASE_DIR, "reviews_diningcode.csv"), encoding="utf-8-sig")
        df = df.rename(columns={"content": "review"})
        df["date"] = df["date"].apply(_parse_diningcode_date)
    else:
        raise ValueError(site)

    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df["review"] = df["review"].astype(str).replace({"nan": None})
    df["text_len"] = df["review"].str.len()
    df.loc[df["review"].isna(), "text_len"] = None
    return df[["rating", "date", "review", "text_len"]]
