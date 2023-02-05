from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
import os

class SpiderScript:
    def __init__(self, db, proxy, letter):
        from court.court.spiders.PublicCourt import PublicCourtSpider
        settings_file_path = 'court.court.script_settings'                      # path from venv (root) to script settings file
        os.environ.setdefault('SCRAPY_SETTINGS_MODULE', settings_file_path)     # manually point to settings
        self.process = CrawlerProcess(get_project_settings())
        self.spider = PublicCourtSpider   # specifies which spider to use
        self.letter = letter    # letter to crawl
        self.db = db            # sqlite connection
        self.proxy = proxy      # proxy to use

    def run(self):
        self.process.crawl(self.spider, self.db, self.proxy, self.letter)     # runs spider w/o terminal input
        self.process.start()

if __name__ == "__main__":
    print('This script can only be run via master.py')
