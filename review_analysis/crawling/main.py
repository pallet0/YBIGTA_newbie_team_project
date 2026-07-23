from argparse import ArgumentParser
from typing import Dict, Type

from review_analysis.crawling.base_crawler import BaseCrawler
from review_analysis.crawling.diningcode_crawler import DiningCodeCrawler
from review_analysis.crawling.kakaomap_crawler import KakaoMapCrawler
from review_analysis.crawling.navermap_crawler import NaverMapCrawler


CRAWLER_CLASSES: Dict[str, Type[BaseCrawler]] = {
    "diningcode": DiningCodeCrawler,
    "kakaomap": KakaoMapCrawler,
    "navermap": NaverMapCrawler,
}


def create_parser() -> ArgumentParser:
    """크롤러 실행에 사용할 명령행 인자를 정의합니다."""
    parser = ArgumentParser()
    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        required=True,
        help="Output file directory. Example: ../../database",
    )
    parser.add_argument(
        "-c",
        "--crawler",
        type=str,
        required=False,
        choices=CRAWLER_CLASSES.keys(),
        help=f"Which crawler to use. Choices: {', '.join(CRAWLER_CLASSES.keys())}",
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Run all crawlers. Default to False.",
    )
    return parser


if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()

    if args.all:
        for crawler_class in CRAWLER_CLASSES.values():
            crawler = crawler_class(args.output_dir)
            crawler.scrape_reviews()
            crawler.save_to_database()
    elif args.crawler:
        crawler_class = CRAWLER_CLASSES[args.crawler]
        crawler = crawler_class(args.output_dir)
        crawler.scrape_reviews()
        crawler.save_to_database()
    else:
        raise ValueError("No crawlers.")
