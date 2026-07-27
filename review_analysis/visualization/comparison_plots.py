"""사이트간 비교분석 시각화 (카카오맵 vs 다이닝코드).

- 카카오맵은 preprocessed_reviews_seongsimdang.csv를 그대로 사용한다.
- 다이닝코드는 아직 전처리기가 없어, KakaomapProcessor와 동일한 규칙
  (결측/별점범위/길이 IQR fence/텍스트 정제/토큰화)을 같은 코드로 적용해 맞춘다.
결과: review_analysis/plots/compare_*.png
"""

import os
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from review_analysis.preprocessing.kakaomap_processor import (
    MIN_TEXT_LEN, MULTI_SPACE_PATTERN, NON_TEXT_PATTERN, tokenize,
)
from review_analysis.visualization.viz_common import (
    AXIS, CRAWLED_AT, DATABASE_DIR, GRID, INK, INK_MUTED, INK_SECONDARY, SERIES, SURFACE,
    load_raw, save, setup_style, strip_chrome,
)

SITES = list(SERIES.keys())  # ["카카오맵", "다이닝코드"]

# 토픽 사전: 리뷰가 어떤 화두를 다루는지 규칙 기반으로 분류
TOPICS = {
    "맛·제품": r"맛있|맛은|맛도|맛이|빵|소보로|시루|메아리|부추|크림|딸기|망고|바게트|케익|케이크|달콤|고소",
    "웨이팅·혼잡": r"웨이팅|대기|줄서|줄 서|줄이|기다리|기다려|사람 많|붐비|북적|인산인해|복잡",
    "가격·가성비": r"가성비|가격|저렴|싸[다고요]|비싸|착한|혜자",
    "서비스·직원": r"친절|불친절|직원|서비스|응대|사장",
    "접근성·시설": r"주차|위치|매장|자리|화장실|역에서|가까|찾아가",
}
TOPIC_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#c3c2b7"]

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]


def load_for_compare(site):
    """비교분석용 데이터프레임 (rating, date, review_clean, tokens)."""
    if site == "카카오맵":
        path = os.path.join(DATABASE_DIR, "preprocessed_reviews_kakaomap.csv")
        df = pd.read_csv(path, encoding="utf-8-sig", usecols=["rating", "date", "review_clean", "tokens"])
        df["date"] = pd.to_datetime(df["date"])
        df["tokens"] = df["tokens"].fillna("").str.split()
        return df

    # 다이닝코드: 카카오맵과 동일한 규칙을 적용해 비교 가능한 상태로 맞춘다
    df = load_raw(site).dropna(subset=["rating", "date", "review"])
    df = df[df["rating"].between(1, 5)]
    df = df.drop_duplicates(subset=["date", "review"])
    q1, q3 = df["text_len"].quantile([0.25, 0.75])
    upper = q3 + 1.5 * (q3 - q1)
    df = df[(df["text_len"] >= MIN_TEXT_LEN) & (df["text_len"] <= upper)]
    df["review_clean"] = (
        df["review"].str.replace(r"\n+", " ", regex=True)
        .apply(lambda t: NON_TEXT_PATTERN.sub(" ", t))
        .apply(lambda t: MULTI_SPACE_PATTERN.sub(" ", t).strip())
    )
    df["tokens"] = df["review_clean"].apply(tokenize)
    return df[["rating", "date", "review_clean", "tokens"]].reset_index(drop=True)


def _round_half_up(series):
    """numpy 기본 반올림은 4.5를 4로 내리므로 0.5는 올림으로 명시 처리."""
    return np.floor(series + 0.5).astype(int)


# ---------------------------------------------------------------- 별점 비교
def plot_rating(data):
    fig, ax = plt.subplots(figsize=(9, 4.4))
    scores = [1, 2, 3, 4, 5]
    width = 0.38

    for i, site in enumerate(SITES):
        rounded = _round_half_up(data[site]["rating"])
        share = [(rounded == s).mean() * 100 for s in scores]
        offset = (i - 0.5) * (width + 0.02)  # 막대 사이 surface 간격 확보
        bars = ax.bar(np.arange(len(scores)) + offset, share, width=width,
                      color=SERIES[site], label=f"{site} (평균 {data[site]['rating'].mean():.2f}점)")
        for rect, value in zip(bars, share):
            if value >= 3:  # 작은 막대에 라벨을 욱여넣지 않는다
                ax.text(rect.get_x() + rect.get_width() / 2, value + 1.5, f"{value:.1f}%",
                        ha="center", fontsize=9, color=INK_SECONDARY)

    ax.set_xticks(np.arange(len(scores)))
    ax.set_xticklabels([f"{s}점" for s in scores])
    ax.set_title("사이트별 별점 분포 비교 (다이닝코드 0.5점 단위는 반올림)")
    ax.set_ylabel("전체 리뷰 대비 비율 (%)")
    ax.set_ylim(0, 85)
    ax.legend(loc="upper left", labelcolor=INK_SECONDARY)
    strip_chrome(ax)
    fig.tight_layout()
    return save(fig, "compare_rating.png")


# ---------------------------------------------------------------- 시계열 비교
def plot_monthly_trend(data):
    """월별 리뷰 수를 사이트별 라인으로 겹쳐 비교."""
    fig, ax = plt.subplots(figsize=(11, 4.6))

    # 두 사이트가 모두 리뷰를 가진 공통 구간으로 잘라 비교 (수집 기간이 달라서)
    start = max(data[s]["date"].min() for s in SITES).to_period("M")
    end = min(data[s]["date"].max() for s in SITES).to_period("M")
    if end == CRAWLED_AT.to_period("M"):
        end -= 1  # 크롤링 중 잘린 마지막 달은 급감처럼 보이므로 제외
    full_range = pd.period_range(start, end, freq="M")

    for site in SITES:
        periods = data[site]["date"].dt.to_period("M")
        monthly = periods.value_counts().reindex(full_range, fill_value=0).sort_index()
        x = monthly.index.to_timestamp()
        ax.plot(x, monthly.values, color=SERIES[site], linewidth=2, label=site)
        ax.plot([x[-1]], [monthly.values[-1]], marker="o", markersize=8, color=SERIES[site],
                markeredgecolor=SURFACE, markeredgewidth=2)
        ax.annotate(f"{site} {monthly.values[-1]}건", (x[-1], monthly.values[-1]),
                    textcoords="offset points", xytext=(8, 0), va="center",
                    fontsize=10, color=SERIES[site])

    ax.set_title(f"월별 리뷰 수 추이 비교 ({start} ~ {end})")
    ax.set_ylabel("리뷰 수")
    ax.legend(loc="upper left", labelcolor=INK_SECONDARY)
    ax.margins(x=0.08)
    strip_chrome(ax)
    fig.tight_layout()
    return save(fig, "compare_monthly_trend.png")


def plot_weekday(data):
    fig, ax = plt.subplots(figsize=(9, 4.2))
    width = 0.38
    peak = 0
    for i, site in enumerate(SITES):
        counts = data[site]["date"].dt.weekday.value_counts().reindex(range(7), fill_value=0)
        share = counts / counts.sum() * 100
        peak = max(peak, share.max())
        offset = (i - 0.5) * (width + 0.02)
        ax.bar(np.arange(7) + offset, share.values, width=width, color=SERIES[site], label=site)
    ax.set_ylim(0, peak * 1.35)  # 범례가 막대를 가리지 않도록 여백 확보
    ax.axhline(100 / 7, color=INK_MUTED, linewidth=1)
    ax.text(6.5, 100 / 7, " 균등선 14.3%", fontsize=9, color=INK_SECONDARY, va="bottom", ha="right")
    ax.set_xticks(np.arange(7))
    ax.set_xticklabels(WEEKDAY_KR)
    ax.set_title("요일별 리뷰 작성 비율 비교")
    ax.set_ylabel("비율 (%)")
    ax.legend(loc="upper left", labelcolor=INK_SECONDARY)
    strip_chrome(ax)
    fig.tight_layout()
    return save(fig, "compare_weekday.png")


# ---------------------------------------------------------------- 텍스트 비교
def _top_keywords(tokens_series, k):
    counter = Counter(t for tokens in tokens_series for t in tokens)
    return counter.most_common(k)


def plot_keyword_top(data):
    """사이트별 상위 키워드 빈도 (각 사이트 색으로 분리 패널)."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, site in zip(axes, SITES):
        top = _top_keywords(data[site]["tokens"], 12)[::-1]
        labels = [w for w, _ in top]
        values = [c for _, c in top]
        bars = ax.barh(labels, values, height=0.62, color=SERIES[site])
        for rect, value in zip(bars, values):
            ax.text(rect.get_width() + max(values) * 0.02, rect.get_y() + rect.get_height() / 2,
                    str(value), va="center", fontsize=9, color=INK_SECONDARY)
        ax.set_title(f"{site} · 상위 키워드 12개 (n={len(data[site])})")
        ax.set_xlabel("등장 횟수")
        ax.set_xlim(0, max(values) * 1.15)
        strip_chrome(ax)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return save(fig, "compare_keyword_top.png")


def plot_keyword_gap(data):
    """양쪽 상위 키워드를 합쳐 '해당 단어를 언급한 리뷰 비율'로 직접 비교."""
    pool = []
    for site in SITES:
        pool += [w for w, _ in _top_keywords(data[site]["tokens"], 12)]
    keywords = list(dict.fromkeys(pool))

    rates = {}
    for site in SITES:
        sets = data[site]["tokens"].apply(set)
        rates[site] = [sets.apply(lambda s, w=w: w in s).mean() * 100 for w in keywords]

    # 두 사이트 언급률 차이가 큰 순으로 정렬해 대비를 드러낸다
    order = np.argsort([rates[SITES[0]][i] + rates[SITES[1]][i] for i in range(len(keywords))])
    keywords = [keywords[i] for i in order]
    for site in SITES:
        rates[site] = [rates[site][i] for i in order]

    fig, ax = plt.subplots(figsize=(9, max(5, len(keywords) * 0.34)))
    height = 0.38
    y = np.arange(len(keywords))
    for i, site in enumerate(SITES):
        offset = (i - 0.5) * (height + 0.02)
        ax.barh(y + offset, rates[site], height=height, color=SERIES[site], label=site)
    ax.set_yticks(y)
    ax.set_yticklabels(keywords)
    ax.set_title("키워드별 언급 리뷰 비율 비교")
    ax.set_xlabel("해당 키워드를 포함한 리뷰 비율 (%)")
    ax.legend(loc="lower right", labelcolor=INK_SECONDARY)
    strip_chrome(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return save(fig, "compare_keyword_gap.png")


def plot_topic(data):
    """규칙 기반 토픽 분류 결과를 사이트별 파이차트로 비교."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    names = list(TOPICS.keys()) + ["기타"]

    for ax, site in zip(axes, SITES):
        text = data[site]["review_clean"].fillna("")
        hits = pd.DataFrame({name: text.str.count(pattern) for name, pattern in TOPICS.items()})
        primary = hits.apply(lambda row: row.idxmax() if row.max() > 0 else "기타", axis=1)
        sizes = [(primary == n).sum() for n in names]

        present = [(n, s) for n, s in zip(names, sizes) if s > 0]
        colors = [TOPIC_COLORS[names.index(n)] for n, _ in present]
        wedges, _ = ax.pie([s for _, s in present], colors=colors, startangle=90,
                           counterclock=False, wedgeprops={"edgecolor": SURFACE, "linewidth": 2})
        total = sum(s for _, s in present)
        ax.legend(wedges, [f"{n}  {s / total * 100:.1f}%" for n, s in present],
                  loc="center left", bbox_to_anchor=(0.96, 0.5), labelcolor=INK_SECONDARY)
        ax.set_title(f"{site} · 리뷰 주제 분포")

    fig.tight_layout()
    return save(fig, "compare_topic.png")


def plot_length(data):
    """리뷰 길이 분포 비교 (박스플롯 + 요약값)."""
    fig, ax = plt.subplots(figsize=(9, 4.2))
    lengths = [data[site]["review_clean"].str.len() for site in SITES]
    box = ax.boxplot(lengths, vert=False, widths=0.45, patch_artist=True,
                     tick_labels=SITES,
                     medianprops={"color": SURFACE, "linewidth": 2},
                     whiskerprops={"color": AXIS}, capprops={"color": AXIS},
                     flierprops={"marker": "o", "markersize": 4, "markeredgecolor": SURFACE,
                                 "alpha": 0.6})
    for patch, site in zip(box["boxes"], SITES):
        patch.set_facecolor(SERIES[site])
        patch.set_edgecolor(AXIS)
    for flier, site in zip(box["fliers"], SITES):
        flier.set_markerfacecolor(SERIES[site])

    for i, (site, values) in enumerate(zip(SITES, lengths), start=1):
        ax.text(values.max(), i + 0.32, f"중앙값 {values.median():.0f}자 · 평균 {values.mean():.0f}자",
                ha="right", fontsize=10, color=INK_SECONDARY)
    ax.set_title("전처리 후 리뷰 길이 분포 비교")
    ax.set_xlabel("글자 수")
    strip_chrome(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    return save(fig, "compare_length.png")


if __name__ == "__main__":
    setup_style()
    data = {site: load_for_compare(site) for site in SITES}
    for site in SITES:
        print(f"[비교분석] {site}: {len(data[site])}건")
    plot_rating(data)
    plot_monthly_trend(data)
    plot_weekday(data)
    plot_keyword_top(data)
    plot_keyword_gap(data)
    plot_topic(data)
    plot_length(data)
