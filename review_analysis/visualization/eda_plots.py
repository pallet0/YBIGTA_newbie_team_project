"""개별 사이트 EDA 시각화.

원본 크롤링 CSV(reviews_*.csv)의 분포와 이상치를 그래프로 저장한다.
결과: review_analysis/plots/eda_*.png
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from review_analysis.visualization.viz_common import (
    AXIS, BLUE_ORDINAL, CRAWLED_AT, DIVERGING, GRID, INK, INK_MUTED, INK_SECONDARY,
    SERIES, SURFACE, load_raw, save, setup_style, strip_chrome,
)

SITES = {"카카오맵": "kakaomap", "다이닝코드": "diningcode"}
MIN_TEXT_LEN = 5


def plot_rating(site, slug, df):
    """별점 분포(막대) + 감성 그룹 비율(파이)."""
    color = SERIES[site]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1.6, 1]})

    counts = df["rating"].value_counts().sort_index()
    ax = axes[0]
    bars = ax.bar([str(v) for v in counts.index], counts.values, width=0.62, color=color)
    for rect, value in zip(bars, counts.values):
        ax.text(rect.get_x() + rect.get_width() / 2, value + max(counts) * 0.02,
                f"{value}\n({value / counts.sum() * 100:.1f}%)",
                ha="center", va="bottom", fontsize=9, color=INK_SECONDARY, linespacing=1.3)
    ax.set_title(f"{site} · 별점 분포 (n={int(counts.sum())})")
    ax.set_xlabel("별점")
    ax.set_ylabel("리뷰 수")
    ax.set_ylim(0, max(counts) * 1.25)
    strip_chrome(ax)
    ax.text(0.01, 0.95, f"평균 {df['rating'].mean():.2f}점", transform=ax.transAxes,
            ha="left", va="top", fontsize=11, color=INK, fontweight="bold")

    # 감성 그룹(파이): 극성이므로 diverging 3색, 중립은 무채색.
    # 작은 조각끼리 라벨이 겹치므로 값은 파이 안이 아니라 범례로 읽힌다.
    group = df["rating"].apply(lambda r: "긍정" if r >= 4 else ("중립" if r >= 3 else "부정"))
    order = [g for g in ["긍정", "중립", "부정"] if g in group.values]
    sizes = [(group == g).sum() for g in order]
    total = sum(sizes)
    ax = axes[1]
    wedges, _ = ax.pie(sizes, colors=[DIVERGING[g] for g in order],
                       startangle=90, counterclock=False,
                       wedgeprops={"edgecolor": SURFACE, "linewidth": 2})
    ax.legend(wedges, [f"{g}  {n / total * 100:.1f}%  ({n}건)" for g, n in zip(order, sizes)],
              loc="center left", bbox_to_anchor=(0.98, 0.5), labelcolor=INK_SECONDARY)
    ax.set_title(f"{site} · 감성 그룹 비율")

    fig.tight_layout()
    return save(fig, f"eda_{slug}_rating.png")


def plot_length(site, slug, df):
    """텍스트 길이 히스토그램 + 박스플롯."""
    color = SERIES[site]
    lengths = df["text_len"].dropna()
    fig, axes = plt.subplots(2, 1, figsize=(9, 5.4), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1]})

    ax = axes[0]
    ax.hist(lengths, bins=40, color=color, alpha=0.85)
    ax.axvline(lengths.median(), color=INK, linewidth=1.5)
    ax.text(lengths.median(), ax.get_ylim()[1] * 0.92, f"  중앙값 {lengths.median():.0f}자",
            fontsize=10, color=INK, va="top")
    ax.set_title(f"{site} · 리뷰 텍스트 길이 분포 (평균 {lengths.mean():.0f}자, 최대 {lengths.max():.0f}자)")
    ax.set_ylabel("리뷰 수")
    strip_chrome(ax)

    ax = axes[1]
    ax.boxplot(lengths, vert=False, widths=0.5, patch_artist=True,
               boxprops={"facecolor": color, "edgecolor": AXIS, "linewidth": 1},
               medianprops={"color": SURFACE, "linewidth": 2},
               whiskerprops={"color": AXIS}, capprops={"color": AXIS},
               flierprops={"marker": "o", "markersize": 4, "markerfacecolor": color,
                           "markeredgecolor": SURFACE, "alpha": 0.6})
    ax.set_yticks([])
    ax.set_xlabel("글자 수")
    strip_chrome(ax)
    ax.grid(axis="y", visible=False)

    fig.tight_layout()
    return save(fig, f"eda_{slug}_length.png")


def plot_date(site, slug, df):
    """월별 리뷰 추이(선) + 연도별 리뷰 수(막대)."""
    color = SERIES[site]
    dates = df["date"].dropna()
    # 리뷰가 없는 달도 0으로 채워야 추이가 왜곡되지 않는다
    periods = dates.dt.to_period("M")
    full_range = pd.period_range(periods.min(), periods.max(), freq="M")
    monthly = periods.value_counts().reindex(full_range, fill_value=0).sort_index()
    yearly = dates.dt.year.value_counts().sort_index()

    fig, axes = plt.subplots(2, 1, figsize=(10, 6))

    ax = axes[0]
    x = monthly.index.to_timestamp()
    ax.plot(x, monthly.values, color=color, linewidth=2)
    peak = monthly.idxmax()
    ax.plot([peak.to_timestamp()], [monthly.max()], marker="o", markersize=8,
            color=color, markeredgecolor=SURFACE, markeredgewidth=2)
    ax.annotate(f"최다 {peak} · {monthly.max()}건", (peak.to_timestamp(), monthly.max()),
                textcoords="offset points", xytext=(0, 10), ha="center",
                fontsize=10, color=INK)
    ax.set_title(f"{site} · 월별 리뷰 수 추이 ({dates.min():%Y-%m} ~ {dates.max():%Y-%m})")
    ax.set_ylabel("리뷰 수")
    ax.set_ylim(0, monthly.max() * 1.25)
    strip_chrome(ax)

    ax = axes[1]
    bars = ax.bar([str(y) for y in yearly.index], yearly.values, width=0.6, color=color)
    for rect, value in zip(bars, yearly.values):
        ax.text(rect.get_x() + rect.get_width() / 2, value + max(yearly) * 0.03, str(value),
                ha="center", va="bottom", fontsize=9, color=INK_SECONDARY)
    ax.set_title(f"{site} · 연도별 리뷰 수")
    ax.set_ylabel("리뷰 수")
    ax.set_ylim(0, max(yearly) * 1.2)
    strip_chrome(ax)

    fig.tight_layout()
    return save(fig, f"eda_{slug}_date.png")


def plot_outlier(site, slug, df):
    """길이 이상치 경계 + 이상치 유형별 건수."""
    color = SERIES[site]
    lengths = df["text_len"].dropna()
    q1, q3 = lengths.quantile([0.25, 0.75])
    upper = q3 + 1.5 * (q3 - q1)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))

    # (좌) 길이 산점 + IQR 상한 / 하한 경계선
    ax = axes[0]
    idx = np.arange(len(lengths))
    normal = (lengths >= MIN_TEXT_LEN) & (lengths <= upper)
    ax.scatter(idx[normal.values], lengths[normal.values], s=9, color=color, alpha=0.5,
               linewidths=0, label="정상 범위")
    ax.scatter(idx[~normal.values], lengths[~normal.values], s=26, color=DIVERGING["부정"],
               edgecolor=SURFACE, linewidth=1.2, label="길이 이상치")
    ax.axhline(upper, color=INK_MUTED, linewidth=1)
    ax.axhline(MIN_TEXT_LEN, color=INK_MUTED, linewidth=1)
    ax.set_title(f"{site} · 리뷰 길이 이상치", pad=52)
    ax.set_xlabel("리뷰 인덱스")
    ax.set_ylabel("글자 수")
    ax.set_ylim(-lengths.max() * 0.05, lengths.max() * 1.12)
    # 경계선 설명은 점 위에 겹치지 않도록 범례로 뺀다
    threshold_handles = [
        Line2D([], [], color=INK_MUTED, linewidth=1, label=f"상한 {upper:.0f}자 (Q3+1.5·IQR)"),
        Line2D([], [], color=INK_MUTED, linewidth=1, label=f"하한 {MIN_TEXT_LEN}자"),
    ]
    ax.legend(handles=ax.get_legend_handles_labels()[0] + threshold_handles,
              loc="lower left", bbox_to_anchor=(0, 1.01), ncol=2, labelcolor=INK_SECONDARY)
    strip_chrome(ax)

    # (우) 이상치/결측 유형별 건수
    checks = {
        "리뷰 결측": int(df["review"].isna().sum()),
        "별점 결측": int(df["rating"].isna().sum()),
        "별점 1~5 이탈": int((~df["rating"].between(1, 5)).sum()),
        "날짜 파싱 실패": int(df["date"].isna().sum()),
        "미래 날짜": int((df["date"] > CRAWLED_AT).sum()),
        f"길이 {MIN_TEXT_LEN}자 미만": int((lengths < MIN_TEXT_LEN).sum()),
        f"길이 {upper:.0f}자 초과": int((lengths > upper).sum()),
        "중복 리뷰": int(df.duplicated(subset=["date", "review"]).sum()),
    }
    ax = axes[1]
    labels = list(checks.keys())[::-1]
    values = [checks[k] for k in labels]
    bars = ax.barh(labels, values, height=0.6,
                   color=[color if v else GRID for v in values])
    for rect, value in zip(bars, values):
        ax.text(rect.get_width() + max(max(values), 1) * 0.02,
                rect.get_y() + rect.get_height() / 2, str(value),
                va="center", fontsize=9, color=INK_SECONDARY)
    ax.set_title(f"{site} · 이상치 · 결측 유형별 건수 (전체 {len(df)}건)")
    ax.set_xlim(0, max(max(values), 1) * 1.18)
    ax.set_xlabel("건수")
    strip_chrome(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)

    fig.tight_layout()
    return save(fig, f"eda_{slug}_outlier.png")


if __name__ == "__main__":
    setup_style()
    for site, slug in SITES.items():
        print(f"[EDA] {site}")
        df = load_raw(site)
        plot_rating(site, slug, df)
        plot_length(site, slug, df)
        plot_date(site, slug, df)
        plot_outlier(site, slug, df)
