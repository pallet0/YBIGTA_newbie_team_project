from abc import ABC, abstractmethod

from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver


######## 수정 금지 #########
class BaseCrawler(ABC):
    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    @abstractmethod
    def start_browser(self):
        pass

    @abstractmethod
    def scrape_reviews(self):
        pass

    @abstractmethod
    def save_to_database(self):
        pass
############################
