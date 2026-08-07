from fastapi import APIRouter, HTTPException

from database.mongodb_connection import mongo_db
from review_analysis.preprocessing.diningcode_processor import DiningCodeProcessor
from review_analysis.preprocessing.navermap_processor import NavermapProcessor
from review_analysis.preprocessing.kakaomap_processor import KakaomapProcessor

review = APIRouter(prefix="/review")

# site_name에 따라 어떤 프로세서를 쓸지 매핑
PROCESSOR_MAP = {
    "diningcode": DiningCodeProcessor,
    "navermap": NavermapProcessor,
    "kakaomap": KakaomapProcessor,
}

@review.post("/preprocess/{site_name}")
async def preprocess_reviews(site_name: str):
    processor_class = PROCESSOR_MAP.get(site_name)
    if processor_class is None:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 site_name입니다: {site_name}"
        )

    # 1. MongoDB에서 원본 크롤링 데이터 조회
    raw_collection = mongo_db["raw_reviews"]
    raw_docs = list(raw_collection.find({"site_name": site_name}))

    if not raw_docs:
        raise HTTPException(
            status_code=404,
            detail=f"{site_name}에 해당하는 데이터가 없습니다."
        )

    # 2. 전처리 클래스로 전처리 + FE 수행
    processor = processor_class("", "")
    processor.load_from_mongo(raw_docs)
    processor.preprocess()
    processor.feature_engineering()

    # 3. 전처리 결과를 MongoDB processed_reviews 컬렉션에 저장
    processed_collection = mongo_db["processed_reviews"]
    processor.save_to_database(processed_collection)

    return {
        "status": "success",
        "site_name": site_name,
        "processed_count": len(processor.df),
    }