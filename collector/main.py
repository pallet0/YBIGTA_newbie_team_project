"""collector 실행 진입점.

흐름:
  1) DB에서 이 식당의 가장 최신 리뷰 날짜를 확인
  2) 카카오맵을 최신순으로 정렬해 크롤링 -> 그 날짜보다 오래된 리뷰가 연속으로 나오면 중단
     (최초 실행은 DB가 비어있으니 자연스럽게 끝까지 다 긁음)
  3) 전처리
  4) 저장 직전 (review_date, review_text) 기준으로 최종 중복 제거 후 DB 저장
"""

import os

from crawling.restaurant_crawler import RestaurantCrawler
from preprocessing.restaurant_preprocessor import RestaurantPreprocessor
import db


def main():
    restaurant_name = "성심당 본점"

    # [수정] 이제 target_count는 무한 스크롤 방지용 안전장치일 뿐, 실제 종료는
    #        대부분 stop_before_date 로직에서 더 일찍 일어남
    target_count = int(os.getenv("CRAWL_TARGET_COUNT", 1000))

    latest_date = db.get_latest_review_date(restaurant_name)
    print(f"DB에 저장된 가장 최근 리뷰 날짜: {latest_date}")

    crawler = RestaurantCrawler(
        target_count=target_count,
        stop_before_date=latest_date,  # None이면 (최초 실행) 끝까지 수집
    )
    crawler.scrape_reviews()
    raw_reviews = crawler.reviews
    print(f"크롤링 완료: {len(raw_reviews)}개 (이번 실행에서 새로 훑은 리뷰)")

    preprocessor = RestaurantPreprocessor(raw_reviews)
    cleaned_reviews = preprocessor.preprocess()
    print(f"전처리 완료: {len(cleaned_reviews)}개")

    # 같은 날짜 경계에서 애매하게 겹칠 수 있어 저장 직전 한 번 더 최종 대조
    existing_keys = db.fetch_existing_keys(restaurant_name=restaurant_name)
    new_reviews = [
        r for r in cleaned_reviews
        if (r["review_date"], r["review_text"]) not in existing_keys
    ]
    print(f"신규 리뷰: {len(new_reviews)}개 (기존 DB와 중복 제외)")

    saved = db.save_reviews(new_reviews)
    print(f"DB 저장 완료: {saved}개")


if __name__ == "__main__":
    main()