from review_analysis.crawling.base_crawler import BaseCrawler
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium import webdriver
from typing import TypedDict
from pathlib import Path
import pandas as pd
import time

class Review(TypedDict):
    """잘 구운 리뷰 하나
    
    rating (float): 평점
    date (str): 날짜
    content(str): 리뷰 내용
    """
    rating: float
    date: str
    content: str

class DiningCodeCrawler(BaseCrawler):
    """다이닝코드에서 리뷰를 수집하는 크롤러
    """
    
    def __init__(self, output_dir: str) -> None:
        """URL 설정, 결과 목록 초기화

        Args:
            output_dir (str): 출력위치
        """
        super().__init__(output_dir)
        
        # 성심당
        self.base_url = 'https://www.diningcode.com/profile.php?rid=LtMjLaf0kZJC'
        self.review_count = 500
        self.reviews: list[Review] = []
        self.visited: set[str] = set()
        
    def start_browser(self) -> WebDriver:
        """크롬 브라우저를 실행합니다.

        Returns:
            WebDriver: 크롬 웹 드라이버
        """
        return webdriver.Chrome()
    
    def scrape_reviews(self) -> None:
        """브라우저를 열고, 리뷰를 실질적으로 수집합니다.
        """
        driver = self.start_browser()
        
        try:
            driver.get(self.base_url)
            time.sleep(2)
            
            for _ in range(1000): # 1000은 failsafe
                more_review_div = driver.find_element(
                    By.ID,
                    "div_more_review"
                )
                
                # 더 불러올 리뷰가 없으면 버튼 div가 display: none이 됨
                if not more_review_div.is_displayed():
                    break
                
                more_button = more_review_div.find_element(
                    By.CSS_SELECTOR,
                    ".More__Review__Button"                    
                )
                
                more_button.click()
                time.sleep(1)
            
            # 리뷰 전개 종료, 리뷰 모으기
            scraped_reviews = driver.find_elements(
                By.CSS_SELECTOR,
                ".latter-graph"
            )
            
            for review in scraped_reviews:
                # 평점, 날짜, 내용 파싱
                scraped_rating = review.find_element(
                    By.CSS_SELECTOR,
                    ".total_score",
                )
                scraped_date = review.find_element(
                    By.CSS_SELECTOR,
                    ".date",
                )
                scraped_content = review.find_elements(
                    By.CSS_SELECTOR,
                    ".review_contents",
                )
                
                self.reviews.append(Review(
                    rating=float(scraped_rating.text.strip().removesuffix("점")),
                    date=scraped_date.text.strip(),
                    content=scraped_content[0].text.strip() if scraped_content else ""
                ))
        finally:
            driver.quit()
    
    def save_to_database(self) -> None:
        """수집된 리뷰들을 .csv 형태로 지정 위치(output_dir)에 저장합니다.
        """
        output_dir = Path(self.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        dataframe = pd.DataFrame(
            self.reviews,
            columns=["rating", "date", "content"]
        )
        
        csv_path = output_dir / "reviews_diningcode.csv"
        dataframe.to_csv(
            csv_path,
            index=False,
            encoding="utf-8-sig"
        )
