import os
import time
from typing import List, Dict, Set, Tuple, Optional

import pandas as pd
from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from review_analysis.crawling.base_crawler import BaseCrawler
from utils.logger import setup_logger


class KakaoMapCrawler(BaseCrawler):
    """성심당 본점(카카오맵) 리뷰 크롤러.

    별점, 날짜, 리뷰 내용을 레이지 로딩 무한 스크롤로 수집해 CSV로 저장한다.
    """

    def __init__(self, output_dir: str) -> None:
        super().__init__(output_dir)
        self.base_url: str = "https://place.map.kakao.com/17733090#review"
        self.driver: Optional[WebDriver] = None
        self.reviews: List[Dict[str, str]] = []
        self.seen: Set[Tuple[str, str]] = set()  # (날짜, 내용) 중복 방지
        self.target_count: int = 500
        self.logger = setup_logger()

    def start_browser(self) -> None:
        """크롬 드라이버를 실행하고 대상 페이지로 진입한다."""
        options = webdriver.ChromeOptions()
        options.add_argument("--window-size=1200,900")
        # options.add_argument("--headless=new")  # 창 없이 돌릴 때만 주석 해제
        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.base_url)
        self.logger.info(f"페이지 진입: {self.base_url}")
        time.sleep(2)

    def scrape_reviews(self) -> None:
        """후기 탭 진입 후 레이지 로딩 무한 스크롤로 목표 개수만큼 수집한다."""
        if self.driver is None:
            self.start_browser()
        assert self.driver is not None

        self._go_to_review_tab()

        empty_tries = 0          # 스크롤해도 안 늘어난 횟수
        max_empty_tries = 8      # 이만큼 연속 안 늘면 진짜 끝으로 판단
        while len(self.reviews) < self.target_count:
            before = len(self.reviews)
            self._scroll_step()
            self._parse_current_page()
            self.logger.info(f"수집: {len(self.reviews)}개")

            if len(self.reviews) == before:
                empty_tries += 1
                if empty_tries >= max_empty_tries:
                    self.logger.info(f"{max_empty_tries}회 연속 미증가. 실제 끝으로 판단, 종료")
                    break
                # 끝인 척하고 다시 나오는 케이스 → 조금 더 기다렸다 재시도
                time.sleep(2.0)
            else:
                empty_tries = 0  # 늘었으면 카운터 리셋

    def _scroll_step(self) -> None:
        """페이지를 한 단계 스크롤하고 새 리뷰가 로딩될 시간을 준다."""
        assert self.driver is not None
        lis = self.driver.find_elements(By.CSS_SELECTOR, "ul.list_review > li")
        if lis:
            # 마지막 리뷰로 이동 → 레이지 로딩 트리거
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'end'});", lis[-1]
            )
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2.2)  # 서버 응답 대기 (레이지 로딩 핵심)

    def _go_to_review_tab(self) -> None:
        """후기 탭이 아니면 클릭해서 이동한다."""
        assert self.driver is not None
        if self.driver.find_elements(By.CSS_SELECTOR, "ul.list_review"):
            return  # 이미 후기 화면
        try:
            tab = self.driver.find_element(By.XPATH, "//a[normalize-space()='후기']")
            self.driver.execute_script("arguments[0].click();", tab)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ul.list_review"))
            )
        except (NoSuchElementException, TimeoutException):
            self.logger.warning("후기 탭을 찾지 못함 (선택자 확인 필요)")

    def _parse_current_page(self) -> None:
        """현재 DOM을 파싱해 새 리뷰를 self.reviews에 추가한다."""
        assert self.driver is not None
        soup = BeautifulSoup(self.driver.page_source, "html.parser")

        for item in soup.select("ul.list_review > li"):
            rating = self._extract_rating(item)
            date = self._extract_text(item, "span.txt_date")
            content = self._extract_content(item)

            key = (date, content)
            if content and key not in self.seen:
                self.seen.add(key)
                self.reviews.append(
                    {"rating": rating, "date": date, "content": content}
                )

    def _extract_rating(self, item: Tag) -> str:
        """별점 추출. starred_grade 안 screen_out 중 숫자인 값을 반환한다."""
        grade = item.select_one("span.starred_grade")
        if grade is None:
            return ""
        for span in grade.select("span.screen_out"):
            txt = span.get_text(strip=True)
            try:
                float(txt)  # "별점"은 걸러지고 "2.0"만 통과
                return txt
            except ValueError:
                continue
        return ""

    def _extract_content(self, item: Tag) -> str:
        """리뷰 본문 추출. btn_more(접기/더보기) span은 제거한다."""
        p = item.select_one("p.desc_review")
        if p is None:
            return ""
        more = p.select_one("span.btn_more")
        if more is not None:
            more.extract()
        return p.get_text(strip=True)

    def _extract_text(self, item: Tag, selector: str) -> str:
        el = item.select_one(selector)
        return el.get_text(strip=True) if el else ""

    def save_to_database(self) -> None:
        """수집한 리뷰를 output_dir/reviews_kakaomap.csv 로 저장한다."""
        os.makedirs(self.output_dir, exist_ok=True)
        df = pd.DataFrame(self.reviews)
        path = os.path.join(self.output_dir, "reviews_kakaomap.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
        self.logger.info(f"{len(df)}개 리뷰 저장 완료 → {path}")
        if self.driver is not None:
            self.driver.quit()
