"""

네이버 지도 방문자 리뷰 크롤러 모듈
 
<성심당 본점>의 네이버 플레이스 방문자 리뷰 페이지에서
별점(rating), 작성일(date), 리뷰 내용(content)을 Selenium으로 크롤링하여
CSV 파일로 저장합니다.

    1. start_browser()
        - 셀레니움 탐지 우회 옵션(자동화 배너 제거, navigator.webdriver 숨김, User-Agent 위장 등)을
        적용한 크롬 드라이버를 실행하고, base_url(리뷰 탭으로 바로 진입하는 URL)에 접속합니다.

    2. scrape_reviews(min_count=570)
        - 리뷰 아이템(ITEM_SEL)이 로드될 때까지 대기한 뒤, 더보기 버튼(MORE_BUTTON_SEL)을
        반복 클릭해 리뷰 개수를 늘려가며 로드된 리뷰 수가 min_count(570) 이상이 될 때까지 반복합니다.
        (텍스트 없는 리뷰 필터링 위함)
        - 각 리뷰 아이템에서 본문(TEXT_SEL), 별점(RATING_SEL), 날짜(DATE_CONTAINER_SEL),
        방문 시간대/예약 여부/대기 시간(VISIT_INFO_SEL)을 파싱해 self.reviews 리스트에 dict로 쌓습니다.

    3. save_to_database()
        - self.reviews를 output_dir/reviews_naver.csv 로 저장하고, 드라이버를 종료합니다.

"""

import os
import re
import csv
import time
import random
import logging
from typing import List, Dict, Optional
import undetected_chromedriver as uc # type: ignore
 

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys 
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)

from review_analysis.crawling.base_crawler import BaseCrawler
from utils.logger import setup_logger

"""
    로거 설정이 한 번도 안되었을 때만 설정을 실행합니다.
    setup_logger가 중복으로 실행되는 것을 방지합니다.
"""

if not logging.getLogger().handlers:  
    setup_logger(log_file="naver_crawler.log")
logger = logging.getLogger(__name__)

class NaverMapCrawler(BaseCrawler):

    """
        네이버 지도 방문자 리뷰를 수집하는 크롤러

        BaseCrawler를 상속받아 start_browser / scrape_reviews / save_to_database
        3개의 추상 메서드를 구현합니다.

        Attributes:
            base_url (str): 크롤링 대상 매장의 리뷰 탭 URL (탭 클릭 없이 바로 리뷰 목록으로)
            driver: Selenium Chrome 드라이버 인스턴스. start_browser() 호출 전에는 None.
            reviews (List[Dict]): 
                파싱된 리뷰들을 담는 리스트. 각 원소는
                {"rating", "date", "review", "visit_time", "reservation", "wait_time"} 
                키를 가진 dict.

        CSS Selector 상수:
            ITEM_SEL (str): 리뷰 한 건을 감싸는 li 태그
            TEXT_SEL (str): 리뷰 본문 텍스트가 담긴 div
            DATE_CONTAINER_SEL (str): 
                방문일 정보를 감싸는 영역 
                이 안의 span.pui__blind 중 연도가 포함된 텍스트를 찾아 날짜로 사용합니다.
            RATING_SEL (str): 별점이 담긴 div (숫자만 추출해서 사용)
            MORE_BUTTON_SEL (str): 리뷰를 추가로 불러오는 더보기 버튼
            VISIT_INFO_SEL (str): 방문 시간대 / 예약 여부 / 대기 시간 태그들이 담긴 영역
                리뷰마다 노출되는 태그 개수가 다르므로 위치가 아니라 각 span/em의 텍스트
                키워드("방문", "예약", "대기")로 어떤 항목인지 분류합니다.
    """

    ITEM_SEL = "li.place_apply_pui.EjjAW"
    TEXT_SEL = "div.pui__vn15t2"
    DATE_CONTAINER_SEL = "div.Vk05k span.pui__gfuUIT" 
    RATING_SEL = "div.pui__6abRMf"
    MORE_BUTTON_SEL = "a.fvwqf"
    VISIT_INFO_SEL = "div.pui__-0Ter1 span.pui__V8F9nN" 


    def __init__(self, output_dir: str):

        """크롤러를 초기화합니다.
 
        Args:
            output_dir (str): 크롤링 결과 csv를 저장할 디렉토리 경로 (예: "database").
        """

        super().__init__(output_dir)
        self.base_url = "https://m.place.naver.com/restaurant/11871325/review/visitor?entry=ple&reviewSort=recent"
        self.driver: Optional[webdriver.Chrome] = None
        self.reviews: List[Dict] = []

    def start_browser(self):
        """undetected-chromedriver를 사용하여 봇 탐지를 우회합니다."""
        options = uc.ChromeOptions()
        
        options.add_argument("--window-size=1200,900")
        
        # 모바일 접속 환경으로 위장
        user_agent = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        )
        options.add_argument(f"--user-agent={user_agent}")

        logger.info("undetected-chromedriver로 브라우저를 시작합니다...")
        
        # uc.Chrome을 사용하면 기존에 사용했던 복잡한 우회 옵션(CDP 등)을 알아서 처리해 줍니다.
        self.driver = uc.Chrome(options=options,version_main=150) #version_main=150 주석처리
        
        self.driver.get(self.base_url)
        self._sleep(3.0, 5.0)
        
    
    def scrape_reviews(self, min_count: int = 570):
        """
        리뷰 탭에 진입한 뒤, 더보기를 반복 클릭하며 리뷰를 수집합니다.
 
        Args:
            min_count (int): 목표로 하는 최소 리뷰 수집 개수 (570개)
        """

        if self.driver is None:
            logger.info("driver가 없어 start_browser()를 자동으로 호출합니다.")
            self.start_browser()

        assert self.driver is not None 
        wait = WebDriverWait(self.driver, 10)
 
        # 1. 리뷰 아이템이 최소 1개 로드될 때까지 대기
        try:
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.ITEM_SEL))
            )
            logger.info("리뷰 목록 로드 확인")
        except TimeoutException:
            logger.warning("리뷰 아이템을 찾지 못했습니다. 페이지 구조 또는 인증 모달을 확인하세요.")
 
        # 2. 더보기 버튼을 반복 클릭하며 리뷰를 계속 로드
        no_progress_count = 0
        while True:
            items = self.driver.find_elements(By.CSS_SELECTOR, self.ITEM_SEL)
            current_count = len(items)
            logger.info(f"현재 로드된 리뷰 수: {current_count}")
 
            if current_count >= min_count:
                break
            
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self._sleep(1.0, 1.5)

            try:
                # 텍스트 기반 XPATH 사용
                more_buttons = self.driver.find_elements(
                    By.XPATH, "//a[contains(., '더보기')]"
                )
                
                # 화면에 실제로 보이는 버튼만 필터링
                visible_buttons = [b for b in more_buttons if b.is_displayed()]

                if not visible_buttons:
                    raise NoSuchElementException("보이는 더보기 버튼 없음")

                # 화면에 보이는 더보기버튼 중 가장 마지막(-1) 버튼을 클릭
                more_button = visible_buttons[-1]
                
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", more_button)
                self._sleep(0.5, 1.2)

                try:
                    more_button.click()
                except ElementClickInterceptedException:
                    more_button.send_keys(Keys.ENTER)

                self._sleep(1.0, 2.5)
                no_progress_count = 0

            except NoSuchElementException:
                no_progress_count += 1
                logger.info(f"더보기 버튼을 찾을 수 없습니다. (시도 {no_progress_count}/3)")
                # DOM 렌더링이 안 된 경우 스크롤을 살짝 올려서 다시 트리거 유도
                self.driver.execute_script("window.scrollBy(0, -300);")
                self._sleep(1.5, 3.0)
                
                if no_progress_count >= 3:
                    logger.info("더 이상 불러올 리뷰가 없는 것으로 판단하여 종료합니다.")
                    break

 
        # 3. 로드된 리뷰 파싱
        items = self.driver.find_elements(By.CSS_SELECTOR, self.ITEM_SEL)
        for item in items:
            # ----- 리뷰 본문 -----
            try:
                raw_text = item.find_element(By.CSS_SELECTOR, self.TEXT_SEL).get_attribute(
                    "textContent"
                ) or ""

                # 잘린 리뷰 끝에 붙는 더보기 버튼 텍스트는 제거
                text = raw_text.replace("더보기", "").strip()
            except NoSuchElementException:
                text = ""

            # ----- 별점(숫자만 추출) -----
            try:
                raw_rating = item.find_element(By.CSS_SELECTOR, self.RATING_SEL).get_attribute(
                    "textContent"
                ) or ""
                match = re.search(r"(\d+(\.\d+)?)", raw_rating)
                rating = match.group(1) if match else ""
            except (NoSuchElementException, StaleElementReferenceException):
                rating = ""

            # ----- 날짜 -----
            """
                time 태그는 연도가 표기되지 않아 
                연도가 포함된 "pui__blind" class를
                찾아서 사용합니다.
            """
            date = ""
            try:
                date_container = item.find_element(By.CSS_SELECTOR, self.DATE_CONTAINER_SEL)
                blind_spans = date_container.find_elements(By.CSS_SELECTOR, "span.pui__blind")
                for blind in blind_spans:
                    blind_text = (blind.get_attribute("textContent") or "").strip()
                    if "년" in blind_text and "월" in blind_text:
                        date = blind_text
                        break
            except NoSuchElementException:
                date = ""

            # ----- 추가 정보(방문 시간대/예약 여부/대기 시간) -----
            visit_time = ""
            reservation = ""
            wait_time = ""
            try:
                visit_info_spans = item.find_elements(By.CSS_SELECTOR, self.VISIT_INFO_SEL)
                for span in visit_info_spans:
                    span_text = (span.get_attribute("textContent") or "").strip()
                    try:
                        em_text = (span.find_element(By.TAG_NAME, "em").get_attribute(
                            "textContent") or ""
                        ).strip()
                    except NoSuchElementException:
                        em_text = ""
 
                    if "방문" in em_text:
                        visit_time = em_text
                    elif "예약" in em_text:
                        reservation = em_text
                    elif "대기" in span_text:
                        wait_time = em_text
            except NoSuchElementException:
                pass

            if not text:
                continue
 
            if text or date or rating:
                self.reviews.append(
                    {
                        "rating": rating,
                        "date": date,
                        "review": text,
                        "visit_time": visit_time,
                        "reservation": reservation,
                        "wait_time": wait_time,
                    }
                )
 
        logger.info(f"총 {len(self.reviews)}개의 리뷰 파싱 완료")

    def save_to_database(self):
        """
        수집된 리뷰를 output_dir/reviews_navermap.csv 로 저장합니다.
        
        저장 후 logger.info()로 저장된 리뷰 건수와 경로를 기록하고,
        드라이버가 실행 중이면 quit()으로 브라우저를 종료합니다.
        """

        os.makedirs(self.output_dir, exist_ok=True)
        save_path = os.path.join(self.output_dir, "reviews_navermap.csv")
 
        with open(save_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["rating", "date", "review","visit_time","reservation","wait_time"])
            writer.writeheader()
            writer.writerows(self.reviews)
 
        logger.info(f"리뷰 {len(self.reviews)}건을 {save_path} 에 저장했습니다.")
 
        if self.driver:
            self.driver.quit()

    @staticmethod
    def _sleep(min_sec: float, max_sec: float):
        """min_sec ~ max_sec 사이의 랜덤한 시간만큼 대기"""
        time.sleep(random.uniform(min_sec, max_sec))
 
 
if __name__ == "__main__":
    crawler = NaverMapCrawler(output_dir="database")
    crawler.start_browser()
    crawler.scrape_reviews(min_count=570)
    crawler.save_to_database()