"""카카오맵·다이닝코드·네이버맵 통합 비교분석.

각 사이트의 ``preprocessed_reviews_*.csv``를 공통 스키마로 읽은 뒤,
같은 텍스트 정규화 규칙을 적용하여 별점·텍스트·시계열을 비교한다.

실행:
    python -m review_analysis.visualization.comparison_all_sites
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.use("Agg")

ROOT_DIR = Path(__file__).resolve().parents[2]
DATABASE_DIR = ROOT_DIR / "database"
PLOTS_DIR = ROOT_DIR / "review_analysis" / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

SITES = ("카카오맵", "다이닝코드", "네이버맵")
FILES = {
    "카카오맵": "preprocessed_reviews_kakaomap.csv",
    "다이닝코드": "preprocessed_reviews_diningcode.csv",
    "네이버맵": "preprocessed_reviews_navermap.csv",
}
COLORS = {
    "카카오맵": "#2A78D6",
    "다이닝코드": "#EB6834",
    "네이버맵": "#18A57A",
}

TOPICS = {
    "맛·메뉴": r"맛있|맛없|맛은|맛이|맛도|빵|소보로|시루|메아리|부추|크림|딸기|망고|바게트|케이[크|ㅋ]|달콤|고소",
    "가격·가성비": r"가격|가성비|저렴|싸다|싼|비싸|혜자",
    "웨이팅·혼잡": r"웨이팅|대기|줄서|줄 서|줄이|기다리|사람 많|붐비|북적|혼잡|복잡",
    "서비스·직원": r"친절|불친절|직원|서비스|응대|사장",
    "접근성·시설": r"주차|위치|매장|자리|화장실|역에서|가까|찾아가",
}
WAIT_PATTERN = TOPICS["웨이팅·혼잡"]
STOPWORDS = {
    "성심당", "대전", "본점", "정말", "너무", "그냥", "여기", "이번", "진짜",
    "그리고", "하지만", "그래서", "있는", "없는", "같아요", "있어요", "입니다",
    "합니다", "했어요", "먹었어요", "좋아요", "같은", "많이", "역시",
}
PARTICLES = (
    "에서는", "으로는", "에게서", "이라고", "라는", "까지", "부터", "보다",
    "에서", "으로", "에게", "하고", "처럼", "만큼", "이나", "라도", "에는",
    "은", "는", "이", "가", "을", "를", "에", "의", "도", "로", "와", "과",
)
TOKEN_PATTERN = re.compile(r"[가-힣]{2,}|[A-Za-z]{2,}")


def setup_style() -> None:
    font = "Malgun Gothic" if sys.platform.startswith("win") else "AppleGothic"
    plt.rcParams.update(
        {
            "font.family": font,
            "axes.unicode_minus": False,
            "figure.facecolor": "#FCFCFB",
            "axes.facecolor": "#FCFCFB",
            "savefig.facecolor": "#FCFCFB",
            "axes.edgecolor": "#C3C2B7",
            "axes.titleweight": "bold",
            "axes.titlecolor": "#111111",
            "axes.labelcolor": "#52514E",
            "xtick.color": "#686762",
            "ytick.color": "#686762",
            "grid.color": "#E1E0D9",
            "grid.linewidth": 0.8,
            "legend.frameon": False,
            "figure.dpi": 130,
        }
    )


def strip_chrome(ax: plt.Axes, grid_axis: str = "y") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis=grid_axis)
    ax.set_axisbelow(True)


def save(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / name, bbox_inches="tight")
    plt.close(fig)
    print(f"저장: review_analysis/plots/{name}")


def normalize_token(token: str) -> str:
    for suffix in PARTICLES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 2:
            token = token[: -len(suffix)]
            break
    return token


def tokenize(text: str) -> list[str]:
    tokens = (normalize_token(token.lower()) for token in TOKEN_PATTERN.findall(text))
    return [token for token in tokens if len(token) >= 2 and token not in STOPWORDS]


def load_site(site: str) -> pd.DataFrame:
    df = pd.read_csv(DATABASE_DIR / FILES[site], encoding="utf-8-sig")
    text_column = next(
        column
        for column in ("review_clean", "cleaned", "content", "review")
        if column in df.columns
    )
    result = pd.DataFrame(
        {
            "rating": pd.to_numeric(df["rating"], errors="coerce"),
            "date": pd.to_datetime(df["date"], errors="coerce"),
            "text": df[text_column].fillna("").astype(str),
        }
    ).dropna(subset=["rating", "date"])
    result = result[result["text"].str.strip().ne("")].copy()
    result["length"] = result["text"].str.len()
    result["tokens"] = result["text"].apply(tokenize)
    result["mentions_wait"] = result["text"].str.contains(WAIT_PATTERN, regex=True)
    return result.reset_index(drop=True)


def plot_rating_groups(data: dict[str, pd.DataFrame]) -> dict[str, dict[str, float]]:
    groups = ("부정(<3)", "중립(3~3.5)", "긍정(≥4)")
    rates: dict[str, dict[str, float]] = {}
    for site, df in data.items():
        labels = np.select(
            [df["rating"] < 3, df["rating"] < 4],
            [groups[0], groups[1]],
            default=groups[2],
        )
        rates[site] = {
            group: round(float((labels == group).mean() * 100), 1)
            for group in groups
        }

    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    x = np.arange(len(groups))
    width = 0.24
    for index, site in enumerate(SITES):
        values = [rates[site][group] for group in groups]
        bars = ax.bar(x + (index - 1) * width, values, width, color=COLORS[site], label=site)
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 1.2,
                f"{value:.1f}%",
                ha="center",
                fontsize=9,
            )
    ax.set_xticks(x, groups)
    ax.set_ylim(0, max(rates[site][groups[2]] for site in SITES) + 12)
    ax.set_ylabel("리뷰 비율 (%)")
    ax.set_title("사이트별 별점 그룹 비교")
    ax.legend(loc="upper left")
    strip_chrome(ax)
    save(fig, "compare_all_rating_groups.png")
    return rates


def keyword_rates(
    data: dict[str, pd.DataFrame], per_site: int = 5, limit: int = 14
) -> tuple[list[str], dict[str, list[float]]]:
    counters: dict[str, Counter[str]] = {}
    for site, df in data.items():
        counter: Counter[str] = Counter()
        for tokens in df["tokens"]:
            counter.update(set(tokens))
        counters[site] = counter

    candidates: list[str] = []
    for site in SITES:
        candidates.extend(word for word, _ in counters[site].most_common(per_site))
    candidates = list(dict.fromkeys(candidates))
    candidates.sort(
        key=lambda word: max(counters[site][word] / len(data[site]) for site in SITES),
        reverse=True,
    )
    keywords = candidates[:limit]
    rates = {
        site: [round(counters[site][word] / len(data[site]) * 100, 1) for word in keywords]
        for site in SITES
    }
    return keywords, rates


def plot_keywords(
    data: dict[str, pd.DataFrame],
) -> tuple[list[str], dict[str, list[float]]]:
    keywords, rates = keyword_rates(data)
    fig, ax = plt.subplots(figsize=(10.5, max(5.2, len(keywords) * 0.43)))
    y = np.arange(len(keywords))
    height = 0.23
    for index, site in enumerate(SITES):
        ax.barh(
            y + (index - 1) * height,
            rates[site],
            height,
            color=COLORS[site],
            label=site,
        )
    ax.set_yticks(y, keywords)
    ax.invert_yaxis()
    ax.set_xlabel("해당 단어를 포함한 리뷰 비율 (%)")
    ax.set_title("사이트별 주요 키워드 언급률")
    ax.legend(loc="lower right")
    strip_chrome(ax, "x")
    save(fig, "compare_all_keywords.png")
    return keywords, rates


def plot_topics(data: dict[str, pd.DataFrame]) -> dict[str, dict[str, float]]:
    rates: dict[str, dict[str, float]] = {}
    for site, df in data.items():
        rates[site] = {
            topic: round(float(df["text"].str.contains(pattern, regex=True).mean() * 100), 1)
            for topic, pattern in TOPICS.items()
        }

    topics = list(TOPICS)
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(topics))
    width = 0.24
    for index, site in enumerate(SITES):
        ax.bar(
            x + (index - 1) * width,
            [rates[site][topic] for topic in topics],
            width,
            color=COLORS[site],
            label=site,
        )
    ax.set_xticks(x, topics)
    ax.set_ylabel("토픽 언급 리뷰 비율 (%)")
    ax.set_title("사이트별 토픽 언급률 (한 리뷰의 복수 토픽 허용)")
    ax.legend()
    strip_chrome(ax)
    save(fig, "compare_all_topics.png")
    return rates


def plot_weekly_trend(
    data: dict[str, pd.DataFrame],
) -> tuple[str, str, dict[str, list[int]]]:
    common_start = max(df["date"].min() for df in data.values())
    common_end = min(df["date"].max() for df in data.values())

    first_monday = common_start.normalize() + pd.Timedelta(
        days=(7 - common_start.weekday()) % 7
    )
    last_sunday = common_end.normalize() - pd.Timedelta(
        days=(common_end.weekday() - 6) % 7
    )
    week_starts = pd.date_range(first_monday, last_sunday, freq="W-MON")

    counts: dict[str, list[int]] = {}
    fig, ax = plt.subplots(figsize=(11, 4.8))
    for site in SITES:
        dates = data[site]["date"]
        values = [
            int(((dates >= start) & (dates < start + pd.Timedelta(days=7))).sum())
            for start in week_starts
        ]
        counts[site] = values
        ax.plot(
            week_starts,
            values,
            marker="o",
            linewidth=2,
            markersize=4,
            color=COLORS[site],
            label=site,
        )
    ax.set_title(
        f"공통 수집기간 주간 리뷰 수 ({first_monday:%Y-%m-%d} ~ {last_sunday:%Y-%m-%d})"
    )
    ax.set_ylabel("리뷰 수")
    ax.legend()
    strip_chrome(ax)
    save(fig, "compare_all_weekly_trend.png")
    return str(first_monday.date()), str(last_sunday.date()), counts


def plot_lengths(data: dict[str, pd.DataFrame]) -> dict[str, dict[str, float]]:
    stats = {
        site: {
            "mean": round(float(df["length"].mean()), 1),
            "median": round(float(df["length"].median()), 1),
            "q1": round(float(df["length"].quantile(0.25)), 1),
            "q3": round(float(df["length"].quantile(0.75)), 1),
        }
        for site, df in data.items()
    }
    fig, ax = plt.subplots(figsize=(9.5, 4.5))
    values = [data[site]["length"] for site in SITES]
    box = ax.boxplot(
        values,
        vert=False,
        patch_artist=True,
        tick_labels=SITES,
        showfliers=False,
        widths=0.5,
        medianprops={"color": "#FFFFFF", "linewidth": 2},
    )
    for patch, site in zip(box["boxes"], SITES):
        patch.set_facecolor(COLORS[site])
    for y, site in enumerate(SITES, start=1):
        stat = stats[site]
        ax.text(
            max(site_df["length"].quantile(0.9) for site_df in data.values()),
            y,
            f"중앙값 {stat['median']:.0f}자 · 평균 {stat['mean']:.1f}자",
            va="center",
            ha="right",
            fontsize=9,
        )
    ax.set_xlabel("전처리 후 리뷰 길이 (자)")
    ax.set_title("사이트별 리뷰 길이 분포 (이상치 표시는 생략)")
    strip_chrome(ax, "x")
    save(fig, "compare_all_review_length.png")
    return stats


def plot_waiting_effect(data: dict[str, pd.DataFrame]) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    for site, df in data.items():
        mentioned = df[df["mentions_wait"]]
        not_mentioned = df[~df["mentions_wait"]]
        stats[site] = {
            "mention_rate": round(float(df["mentions_wait"].mean() * 100), 1),
            "rating_wait": round(float(mentioned["rating"].mean()), 2),
            "rating_no_wait": round(float(not_mentioned["rating"].mean()), 2),
            "n_wait": int(len(mentioned)),
        }

    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    x = np.arange(len(SITES))
    width = 0.32
    wait_values = [stats[site]["rating_wait"] for site in SITES]
    no_wait_values = [stats[site]["rating_no_wait"] for site in SITES]
    ax.bar(x - width / 2, no_wait_values, width, color="#B8B7B0", label="웨이팅 미언급")
    ax.bar(
        x + width / 2,
        wait_values,
        width,
        color=[COLORS[site] for site in SITES],
        label="웨이팅 언급",
    )
    for index, site in enumerate(SITES):
        ax.text(
            index + width / 2,
            wait_values[index] + 0.04,
            f"{wait_values[index]:.2f}\n(n={stats[site]['n_wait']})",
            ha="center",
            fontsize=9,
        )
    ax.set_xticks(x, SITES)
    ax.set_ylim(0, 5.35)
    ax.set_ylabel("평균 별점")
    ax.set_title("웨이팅·혼잡 언급 여부에 따른 평균 별점")
    ax.legend(loc="lower left")
    strip_chrome(ax)
    save(fig, "compare_all_waiting_rating.png")
    return stats


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    setup_style()
    data = {site: load_site(site) for site in SITES}
    summary: dict[str, object] = {
        "sample_size": {site: len(df) for site, df in data.items()},
        "date_range": {
            site: [str(df["date"].min().date()), str(df["date"].max().date())]
            for site, df in data.items()
        },
        "rating_mean": {
            site: round(float(df["rating"].mean()), 2) for site, df in data.items()
        },
    }
    summary["rating_groups"] = plot_rating_groups(data)
    keywords, keyword_rate = plot_keywords(data)
    summary["keywords"] = {
        site: dict(zip(keywords, keyword_rate[site])) for site in SITES
    }
    summary["topics"] = plot_topics(data)
    common_start, common_end, weekly = plot_weekly_trend(data)
    summary["common_weekly_period"] = [common_start, common_end]
    summary["weekly_counts"] = weekly
    summary["length"] = plot_lengths(data)
    summary["waiting"] = plot_waiting_effect(data)

    summary_path = PLOTS_DIR / "compare_all_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
