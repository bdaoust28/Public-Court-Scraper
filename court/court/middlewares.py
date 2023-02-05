# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html
import scrapy.utils.response
from scrapy import signals
import redis, requests, random
import scrapy.core.downloader.handlers.http11
from scrapy.exceptions import IgnoreRequest
from proxyGenerator import getProxies
from proxyChecker import validateProxies

# useful for handling different item types with a single interface
from itemadapter import is_item, ItemAdapter


class CourtSpiderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, or item objects.
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request or item objects.
        pass

    def process_start_requests(self, start_requests, spider):
        # Called with the start requests of the spider, and works
        # similarly to the process_spider_output() method, except
        # that it doesn’t have a response associated.

        # Must return only requests (not items).
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info('Spider opened: %s' % spider.name)


class CourtDownloaderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    def __init__(self):
        self.goodProxies = set()
        self.generations = 0
        self.expireMessage = False

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        return None

    def process_response(self, request, response, spider):
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        if response.status != 200 or 'dataloss' in response.flags:
            if not self.expireMessage:
                print('Proxy has expired. Spider will likely take longer than usual as it rotates proxies.')
                self.expireMessage = True
            badProxy = request.meta["proxy"].split("/")[-1]

            # try validated proxies in self.goodProxies set
            self.goodProxies.discard(request.meta["proxy"])  # removes expired proxy if in set
            if self.goodProxies:
                retryreq = request.copy()
                retryreq.meta['proxy'] = random.choice(list(self.goodProxies))
                return retryreq

            proxy = self.new_proxy(request.url, request.headers, badProxy)
            if proxy:
                retryreq = request.copy()
                retryreq.meta['proxy'] = proxy
                self.goodProxies.add(proxy)
                return retryreq
            else:
                raise IgnoreRequest('No more proxies found. Aborting request.')
        else:
            return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        if not self.expireMessage:
            print('Proxy has expired. Spider will likely take longer than usual as it rotates proxies.')
            self.expireMessage = True

        badProxy = request.meta["proxy"].split("/")[-1]

        # try validated proxies in self.goodProxies set
        self.goodProxies.discard(request.meta["proxy"])  # removes expired proxy if in set
        if self.goodProxies:
            retryreq = request.copy()
            retryreq.meta['proxy'] = random.choice(list(self.goodProxies))
            return retryreq

        proxy = self.new_proxy(request.url, request.headers, badProxy)
        if proxy:
            retryreq = request.copy()
            retryreq.meta['proxy'] = proxy
            self.goodProxies.add(proxy)
            return retryreq
        else:
            raise IgnoreRequest('No more proxies found. Aborting request.')

    def spider_opened(self, spider):
        spider.logger.info('Spider opened: %s' % spider.name)

    def new_proxy(self, url, headers, oldProxy=''):
        try:
            red = redis.Redis()  # establish connection with redis server at localhost
            red.ping()
        except redis.exceptions.ConnectionError:
            red = redis.Redis('redis-host')  # establish connection with redis server at redis-host (in docker)
        red.srem('proxies', oldProxy)   # remove bad proxy

        proxies = list(red.smembers('proxies'))
        for i in range(len(proxies)):
            # check if crawlsite accepts proxy
            proxy = random.choice(proxies).decode('utf-8')  # decode from binary to str
            try:
                status = requests.get(url,
                                      #headers=headers,
                                      proxies={'http': proxy, 'https': proxy},
                                      timeout=10).status_code
                if status == 200:  # crawlsite accepted proxy
                    proxy = f'http://{proxy}'
                    print(f'Proxy found.')
                    return proxy

            # if connection tried too many times
            except requests.exceptions.ProxyError:
                red.srem('proxies', proxy)  # remove bad proxy
                continue

            # if connection refused by host
            except requests.exceptions.SSLError:
                red.srem('proxies', proxy)  # remove bad proxy
                continue

            # if proxy broke mid-request
            except scrapy.core.downloader.handlers.http11.TunnelError:
                red.srem('proxies', proxy)  # remove bad proxy
                continue

            # if request read timed out
            except requests.exceptions.ReadTimeout:
                red.srem('proxies', proxy)  # remove bad proxy
                continue

        # loop never broke, which means no valid proxy was found OR there are no more proxies available
        else:
            if self.generations > 3:
                return None
            print('No more proxies available. Gathering more...')
            getProxies()
            validateProxies()
            self.generations += 1
            self.goodProxies = set()
            return f"http://{random.choice(list(red.smembers('proxies').decode('utf-8')))}"
