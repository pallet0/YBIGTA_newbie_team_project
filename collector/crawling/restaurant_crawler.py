import time
from typing import List, Dict, Set, Tuple, Optional
from datetime import datetime, date  # [수정] date, datetime import 누락되어 있어서 추가 (버그 2)
import logging

from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# [수정] 원본은 review_analysis.crawling.base_crawler.BaseCrawler를 상속했지만
#        이번 프로젝트엔 그 base 모듈이 없어서 상속 없이 독립 클래스로 변경.
#        utils.logger.setup_logger도 같은 이유로 표준 logging 모듈로 교체.
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class RestaurantCrawler:
    """성심당 본점(카카오맵) 리뷰 크롤러.

    별점, 날짜, 리뷰 내용을 레이지 로딩 무한 스크롤로 수집해 CSV로 저장한다.
    """
    # [수정] 위 docstring 마지막 문장(CSV로 저장한다)은 원본 그대로 남겨뒀지만
    #        실제로는 이제 CSV 저장 없이 self.reviews를 main.py에 바로 넘겨줌.

    # [추가] 크롤링 대상이 카카오맵 페이지 하나(성심당 본점)뿐이라, 리뷰마다 페이지에서
    #        긁지 않고 상수로 고정. DB의 restaurant_name(NOT NULL) 컬럼을 채우는 데 사용.
    RESTAURANT_NAME = "성심당 본점"

    def __init__(
        self,
        target_count: int = 1000,
        headless: bool = True,  # [수정] 콤마 누락되어 SyntaxError 나던 부분 (버그 1)
        stop_before_date: Optional[date] = None,  # [추가] DB의 최신 리뷰 날짜를 전달받음
    ) -> None:
        # [수정] super().__init__(output_dir) 제거
        self.base_url: str = "https://place.map.kakao.com/17733090#review"
        self.driver: Optional[WebDriver] = None
        self.reviews: List[Dict[str, str]] = []
        self.seen: Set[Tuple[str, str]] = set()  # (날짜, 내용) 중복 방지
        self.target_count: int = target_count
        self.headless: bool = headless
        self.restaurant_name = self.RESTAURANT_NAME
        self.logger = logging.getLogger(__name__)

        # [추가] 이 날짜보다 오래된 리뷰가 연속으로 나오면 "이미 다 아는 구간"으로 보고 중단
        self.stop_before_date = stop_before_date
        self._older_streak = 0
        self._older_streak_limit = 5
        self.reached_known_area = False

    def start_browser(self) -> None:
        """크롬 드라이버를 실행하고 대상 페이지로 진입한다."""
        options = webdriver.ChromeOptions()
        options.add_argument("--window-size=1200,900")
        if self.headless:
            # [수정] 원본은 주석 처리(수동으로 필요할 때만 켜는 방식)였지만
            #        EC2(서버, 화면 없음)에서 항상 동작해야 하므로 기본 활성화로 변경.
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--blink-settings=imagesEnabled=false")
        self.driver = webdriver.Remote(command_executor='http://localhost:4444/wd/hub', options=options)
        self.driver.get(self.base_url)
        self.logger.info(f"페이지 진입: {self.base_url}")
        time.sleep(2)

    def scrape_reviews(self) -> None:
        """후기 탭 진입 후 레이지 로딩 무한 스크롤로 목표 개수만큼 수집한다."""
        if self.driver is None:
            self.start_browser()
        assert self.driver is not None

        self._go_to_review_tab()
        self._sort_by_recent()  # [추가] 최신순 정렬 호출이 빠져있어서 추가 (안 하면 계속 유용한순으로 긁힘)

        empty_tries = 0          # 스크롤해도 안 늘어난 횟수
        max_empty_tries = 8      # 이만큼 연속 안 늘면 진짜 끝으로 판단
        while len(self.reviews) < self.target_count and not self.reached_known_area:
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

        if self.reached_known_area:
            self.logger.info("이미 저장된 리뷰 구간에 도달. 신규 리뷰 수집 종료")

        # [수정] 원본은 save_to_database()에서 driver.quit()을 했지만,
        #        이제 저장은 db.py가 담당하므로 크롤링이 끝나는 시점인 여기서 바로 종료.
        if self.driver is not None:
            self.driver.quit()

    def _sort_by_recent(self) -> None:
        """[추가] 정렬 기준을 '최신순'으로 변경.

        스크린샷으로 구조 확인 결과 드롭다운 방식임: button.btn_sort를 눌러야
        div.layer_sort가 열리고, 그 안에서 '최신' 옵션을 한 번 더 클릭해야 함.
        기본 정렬은 '유용한순'이라 이 과정을 안 거치면 최신 리뷰가 아니라
        인기 리뷰 위주로 수집되어 stop_before_date 로직이 무의미해짐.
        """
        assert self.driver is not None
        try:
            # 1단계: 정렬 드롭다운 버튼 열기
            sort_btn = self.driver.find_element(By.CSS_SELECTOR, "div.group_sort > button.btn_sort")
            self.driver.execute_script("arguments[0].click();", sort_btn)

            # 드롭다운이 실제로 열릴 때까지 대기
            WebDriverWait(self.driver, 5).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.layer_sort"))
            )

            # 2단계: 드롭다운 안에서 '최신'이 포함된 옵션 클릭
            recent_option = self.driver.find_element(
                By.XPATH, "//div[contains(@class,'layer_sort')]//*[contains(text(),'최신')]"
            )
            self.driver.execute_script("arguments[0].click();", recent_option)
            time.sleep(1.5)
            self.logger.info("정렬 기준: 최신순으로 변경 완료")
        except (NoSuchElementException, TimeoutException):
            self.logger.warning(
                "최신순 정렬 옵션을 찾지 못함. 기본 정렬(유용한순)로 진행 "
                "(브라우저에서 직접 열어 layer_sort 내부 구조 확인 필요)"
            )

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
            date_str = self._extract_text(item, "span.txt_date")  # [수정] 변수명 date -> date_str (버그 3: 아래에서 date_str을 참조하는데 정의가 date였음, 게다가 date는 import한 타입명과 겹침)
            content = self._extract_content(item)

            key = (date_str, content)
            if not content or key in self.seen:
                continue
            self.seen.add(key)

            # [추가] DB에 이미 있는 최신 날짜보다 오래된 리뷰가 연속으로 나오면 조기 종료
            if self.stop_before_date is not None:
                parsed_date = self._parse_date(date_str)
                if parsed_date is not None and parsed_date < self.stop_before_date:
                    self._older_streak += 1
                    if self._older_streak >= self._older_streak_limit:
                        self.reached_known_area = True
                        return
                else:
                    self._older_streak = 0

            # [수정] 원래 if 블록 안에 들여쓰기 되어 있던 걸 밖으로 뺌 (버그 4)
            #        stop_before_date가 None인 최초 실행 때도 리뷰가 저장되어야 하는데,
            #        if 블록 안에 있으면 그 경우 append가 아예 실행되지 않았음.
            self.reviews.append(
                {
                    "restaurant_name": self.restaurant_name,
                    "rating": rating,
                    "date": date_str,
                    "content": content,
                }
            )

    @staticmethod
    def _parse_date(date_str: str) -> Optional[date]:
        """[추가] '2024.01.01.' 형식 문자열을 date 객체로 변환. 실패하면 None."""
        try:
            cleaned = date_str.strip().rstrip(".")
            return datetime.strptime(cleaned, "%Y.%m.%d").date()
        except ValueError:
            return None

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

    # [삭제] 원본의 save_to_database()는 사실 CSV 저장 함수였음(이름이 오해 소지가 있었음).
    #        이제 저장은 main.py + db.py가 실제 RDS에 저장하는 방식으로 담당하므로 제거.
    #        디버깅용 CSV 백업이 필요해지면 이 자리에 to_csv 메서드를 다시 추가하면 됨.