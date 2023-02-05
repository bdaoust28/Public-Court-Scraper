import scrapy.core.downloader.handlers.http11
import sqlite3, requests, time, redis, json2
from proxyChecker import validateProxies
from fake_useragent import UserAgent
from proxyGenerator import getProxies
from court.crawler_script import SpiderScript

def crawlsite_status(url, headers, proxy=None):
    # return site status code (200, 503, 404, ...) with or without proxy
    if proxy:
        return requests.get(url, headers=headers, proxies={'http': proxy, 'https': proxy}, timeout=10).status_code
    return requests.get(url, headers=headers).status_code

def run_spider(db, proxy, letter):
    s = SpiderScript(db, proxy, letter)
    s.run()

def start_db(dbName):
    # create and connect to database
    cnx = sqlite3.connect(dbName)
    cursor = cnx.cursor()
    cursor.execute('PRAGMA foreign_keys = on')      # enable foreign keys
    return create_tables(cnx)

def create_tables(cnx):
    # create case description table
    cursor = cnx.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS cases'
                   '(id TEXT PRIMARY KEY NOT NULL,'
                   'title TEXT NOT NULL,'
                   'date_filed TEXT NOT NULL,'
                   'type TEXT,'
                   'type_description TEXT,'
                   'status TEXT,'
                   'status_description TEXT,'
                   'trial TEXT,'
                   'related_cases TEXT);')          # set related as foreign key for cases(id)?
    # print('Created table: cases')

    # create case parties table
    cursor.execute('CREATE TABLE IF NOT EXISTS parties'
                   '(id TEXT PRIMARY KEY NOT NULL,'
                   'name TEXT NOT NULL,'
                   'type TEXT,'
                   'address TEXT,'
                   'aliases TEXT,'                  # set aliases as foreign key for parties(name)?
                   'case_ids TEXT NOT NULL);')
    #                'FOREIGN KEY (case_id) REFERENCES cases(id));')
    # print('Created table: parties')

    # create case dockets table
    cursor.execute('CREATE TABLE IF NOT EXISTS dockets'
                   '(id TEXT PRIMARY KEY NOT NULL,'
                   'entry_date TEXT NOT NULL,'
                   'description TEXT NOT NULL,'
                   'entry TEXT,'
                   'party_name TEXT,'
                   'monetary TEXT,'
                   'case_id TEXT NOT NULL,'
                   'FOREIGN KEY (case_id) REFERENCES cases(id));')
    #               'FOREIGN KEY (party_name) REFERENCES parties(name);')
    # print('Created table: dockets')
    return cnx

def main():
    # start project timer
    startTime = time.time()

    # declare vars
    inDocker = False
    try:
        red = redis.Redis()                 # establish connection with redis server at localhost
        red.ping()
    except redis.exceptions.ConnectionError:
        red = redis.Redis('redis-host')     # establish connection with redis server at redis-host (in docker)
        inDocker = True

    red.flushdb()                           # wipe redis server before starting
    alpha = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    dbName = 'public_court.db'
    urls = json2.load_file('target.json')       # get urls from json

    # set up headers with random user agent
    headers = {
        'Host': urls['host'],
        'User-Agent': f'{UserAgent().random}',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Cookie': 'disclaimer=Y',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-GPC': '1'
    }

    # check if site is up
    print('Checking site to crawl...')
    status = crawlsite_status(urls['landing'], headers=headers)     # try a proxy if failed?
    # 200 = OK
    if status == 200:
        print('Site is responsive.')
    # any other code is unacceptable
    elif status == 503:
        print('Site is down. Try again later.')
        return
    else:
        print('Site refuses service. Try again later.')
        return

    # start database
    cnx = start_db(dbName)
    print(f'Connected to SQLite database: {dbName}')

    # compile list of proxies and fill redis server
    print('Getting new proxies...')
    getProxies()                        # add proxies to proxyList.txt
    print('Validating proxies... (~25s)')
    validateProxies()                   # fill redis server with new + good proxies

    # find good proxy
    print('Finding proxy to use... (<30s)')
    proxies = red.smembers('proxies')
    for proxy in proxies:
        # check if crawlsite accepts proxy
        proxy = proxy.decode('utf-8')       # decode from binary to str
        #print(f'[DEBUG] Checking {proxy}')
        try:
            status = crawlsite_status(urls['landing'], headers, proxy)
            if status == 200:   # crawlsite accepted proxy
                proxy = f'http://{proxy}'
                print(f'Proxy found.')

                # start spider
                letter = alpha[0]   # A
                print(f'[{letter}] Spider started.')
                run_spider(cnx, proxy, letter)
                break
            #print(f'[DEBUG] {status} from crawlsite with {proxy}')
            red.srem('proxies', proxy)

        # connection tried too many times
        except requests.exceptions.ProxyError:
            #print(f'[DEBUG] Connection refused by crawlsite.')
            red.srem('proxies', proxy)
            continue

        # connection timed out
        except requests.exceptions.ReadTimeout:
            red.srem('proxies', proxy)
            continue

        # connection refused by host
        except requests.exceptions.SSLError:
            #print(f'[DEBUG] Connection refused by crawlsite.')
            red.srem('proxies', proxy)
            continue

        # proxy broke mid-request
        except scrapy.core.downloader.handlers.http11.TunnelError:
            #print('[DEBUG] Proxy no longer working.')
            red.srem('proxies', proxy)
            continue

        except requests.exceptions.ConnectTimeout:
            red.srem('proxies', proxy)
            continue

    # loop never broke, which means no valid proxy was found OR there are no more proxies available
    else:
        print('No valid proxies available. Run the program again to generate more.')
        return

    # LOOK INTO SCRAPYD
    print(f'[{letter}] Spider finished.')

    # query db to see if fields are populated
    cursor = cnx.cursor()
    print(f'\n\nQuerying 1 record from each table in {dbName}:')
    print(f"cases: {cursor.execute('select * from cases;').fetchone()}")
    print(f"\nparties: {cursor.execute('select * from parties;').fetchone()}")
    print(f"\ndockets: {cursor.execute('select * from dockets;').fetchone()}")
    cnx.close()

    # print runtime of project
    print(f'\n\nSuccess!\nProject finished in {time.strftime("%H hours %M minutes %S seconds.", time.gmtime(time.time() - startTime))}')

    # inform user of functionalities
    print('If all 25 pages did not finish, run the program again.\n')
    if inDocker:
        print('To open the database for querying: run container again, open command line (CLI), and run "sqlite3 public_court.db".\n\n')
    else:
        print("To open the database for querying: open PowerShell/CMD, type 'sqlite3' and press Tab. "
              "Then press space and type 'public_court.db' and press Enter.\nThe final command should read: '.\\sqlite3.exe .\\public_court.db'\n")

if __name__ == "__main__":
    main()
