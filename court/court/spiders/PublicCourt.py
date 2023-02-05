import scrapy, redis, csv, re, sqlite3, json2
from datetime import datetime
from html_text import extract_text
from pathlib import Path
from collections import defaultdict

class PublicCourtSpider(scrapy.Spider):
    def __init__(self, db=None, proxy=None, letter='A'):
        if db:
            self.cnx = db
        else:
            self.cnx = sqlite3.connect(Path.cwd().parent / 'public_court.db')
        self.cursor = self.cnx.cursor()
        self.proxy = proxy
        self.letter = letter
        self.finished_cases = defaultdict(int)
        self.finished_pages = 0
        self.total_pages = 0
        self.requestNum = defaultdict(int)

    saveFolder = Path.cwd()
    urls = json2.load_file(saveFolder / 'target.json')

    name = 'PublicCourt'
    allowed_domains = [urls['host']]
    try:
        r = redis.Redis()  # establish connection with redis server at localhost
        r.ping()
    except redis.exceptions.ConnectionError:
        r = redis.Redis('redis-host')  # establish connection with redis server at redis-host (in docker)
    searchFormHeaders = {
        'Host': urls['host'],
        # 'User-Agent': taken over by fake-useragent
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': urls['searchReferer'],
        'DNT': '1',
        'Connection': 'keep-alive',
        'Cookie': 'disclaimer=Y',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'frame',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-GPC': '1'
    }
    docketHeaders = {
        'Host': urls['host'],
        # 'User-Agent': taken over by fake-useragent
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': '',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Cookie': 'disclaimer=Y',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'frame',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-GPC': '1',
    }

    def start_requests(self):
        url = f'{self.urls["search"]}' \
              f'?backto=P' \
              f'&soundex_ind=' \
              f'&partial_ind=checked' \
              f'&last_name={self.letter}' \
              f'&first_name=' \
              f'&middle_name=' \
              f'&begin_date=' \
              f'&end_date=' \
              f'&case_type=ALL' \
              f'&id_code=&PageNo='

        # begin crawl
        for counter in range(1, 26):
            # remove meta when using rotated proxies
            yield scrapy.Request(f'{url + str(counter)}', method='GET', headers=self.searchFormHeaders, callback=self.parseSearch,
                                 meta={'proxy': self.proxy, 'download_timeout': 60})
        self.total_pages = counter
        print(f'[{self.letter}] {self.total_pages} pages requested. Each page requests up to 20 cases.')

    def parseSearch(self, response):
        idSet = 'case_ids'
        titleSet = 'case_titles'
        caseId = ''
        caseTitle = ''
        docketUrl = ''

        page = response.url.split("=")[-1]
        rows = len(response.xpath('/html/body/font[1]/table[2]/tr'))
        for i in range(rows):
            # skip first row
            if i < 1:
                continue
            # row XPATH changes if address is unavailable, changing occurence of 'i' element
            ifAddress = len(response.xpath(f'/html/body/font[1]/table[2]/tr[{i + 1}]/td[3]/i'))
            if ifAddress == 1:
                caseId = clean(response.xpath(f'/html/body/font[1]/table[2]/tr[{i + 1}]/td[3]/i/a/text()').get())
                caseTitle = clean(response.xpath(f'/html/body/font[1]/table[2]/tr[{i + 1}]/td[3]/i/text()').get())

                docketUrl = self.urls['docket'].format(caseId)
            elif ifAddress == 2:
                caseId = clean(response.xpath(f'/html/body/font[1]/table[2]/tr[{i + 1}]/td[3]/i[2]/a/text()').get())
                caseTitle = clean(response.xpath(f'/html/body/font[1]/table[2]/tr[{i + 1}]/td[3]/i[2]/text()').get())
                docketUrl = self.urls['docket'].format(caseId)

            # skip case scrape if already done
            if not self.r.sismember(idSet, caseId):
                self.docketHeaders['Referer'] = self.urls['docketReferer'].format(caseId)
                yield scrapy.Request(docketUrl, method='GET', headers=self.docketHeaders, callback=self.parseDocket,
                                     meta={'proxy': self.proxy, 'download_timeout': 45, 'page': page})
                self.r.sadd(idSet, caseId)
                self.requestNum[page] += 1

    def parseDocket(self, response):
        tableNum = len(response.xpath('/html/body/font/table'))     # should be 4 unless case events
        aNum = len(response.xpath('/html/body/font/a'))             # should be 6 unless related cases
        docketEntries = not response.xpath('/html/body/font/a[6]/i').get()

        # parse case description ---------------------------------------------------------------------------------------
        descCSV = self.saveFolder / 'case_description.csv'     # place csv in parent dir
        descTable = '/html/body/font/table[2]'

        caseId = clean(response.xpath(f'{descTable}/tr[1]/td[3]/text()').get().split('\n')[0])
        caseTitle = response.xpath(f'{descTable}/tr[1]/td[3]/text()').get().split('\n')[1][2:]
        caseFileDate = response.xpath(f'{descTable}/tr[2]/td[3]/text()').get()
        caseTrial = response.xpath(f'{descTable}/tr[1]/td[3]/i/text()').get()
        caseType = response.xpath(f'{descTable}/tr[3]/td[3]/text()').get()
        caseStatus = response.xpath(f'{descTable}/tr[4]/td[3]/text()').get()

        # should be no related cases unless num of 'a's exceed 6
        relatedCases = None
        if aNum > 6:
            bound = aNum - 6    # if aNum == 8, bound = 2
            cases = []
            for i in range(bound):  # if bound == 2, loop only runs twice
                cases.append(response.xpath(f'/html/body/font/a[{4 + i}]/text()').get())
            relatedCases = ';'.join(cases)      # seperate related cases with comma

        # convert date from 'Monday January 23rd, 2022' to '2022-01-23'
        caseFileDate = clean(caseFileDate).replace(' ', '').split(',')      # clean str, get rid of any space and split by commas
        caseFileDate[1] = caseFileDate[1][0:-2]                             # truncate last 2 chars of day (ex: 'st', 'rd', 'th)
        caseFileDate = ','.join(caseFileDate)                               # rejoin with comma as delimiter
        dateFormatted = datetime.strptime(caseFileDate, '%A,%B%d,%Y').strftime('%Y-%m-%d')    # convert date to yyyy/mm/dd

        # remove redundant 'CLOSED' from case title
        if 'CLOSED' in caseTitle.split(' ')[0]:
            caseTitle = ' '.join(caseTitle.split(' ')[1:])

        # if a case trial is given, truncate front '-'
        if caseTrial:
            caseTrial = caseTrial[1:]

        # if no case type is given
        if response.xpath(f'{descTable}/tr[3]/td[3]/i').get():
            typeShort, typeLong = None, None
        else:
            # split case type into two parts
            # abbreviated and full
            typeShort, typeLong = caseType.split(' - ')

        # if no case status is given
        if response.xpath(f'{descTable}/tr[4]/td[3]/i').get():
            statusShort, statusLong = None, None
        else:
            # split case status into two parts
            # short and expanded (if applicable, otherwise same as short)
            statusShort, statusLong = caseStatus.split(' - ')

        caseDesc = {
            'id': caseId,
            'title': clean(caseTitle),
            'date_filed': dateFormatted,
            'type': clean(typeShort),
            'type_description': clean(typeLong),
            'status': clean(statusShort),
            'status_description': clean(statusLong),
            'trial': clean(caseTrial),
            'related': clean(relatedCases)
        }

        # write to csv file for debugging
        try:
            with open(descCSV, 'a+') as file:
                write = csv.writer(file, delimiter=',')
                write.writerow(list(caseDesc.values()))
        except PermissionError:
            pass

        # write to sqlite database if case not already written
        if not self.cursor.execute('SELECT * FROM cases WHERE id=?;', (caseDesc['id'],)).fetchone():
            self.cursor.execute('INSERT INTO cases VALUES(?,?,?,?,?,?,?,?,?);', tuple(caseDesc.values()))
            self.cnx.commit()

        # parse case parties--------------------------------------------------------------------------------------------
        caseParties = []
        partiesCSV = self.saveFolder / 'case_parties.csv'  # place csv in parent dir
        party = {}
        if docketEntries:
            partyTable = f'/html/body/font/table[{tableNum - 1}]'  # second to last table
        else:
            partyTable = f'/html/body/font/table[{tableNum}]'  # last table
        partyId = None
        partyName = None
        partyType = None
        partyAddress = None
        partyAliases = None
        for i, row in enumerate(response.xpath(f'{partyTable}/tr')):
            # skip first row and blank rows
            if not response.xpath(f'{partyTable}/tr[{i + 1}]/td[2]').get():
                continue
            address = response.xpath(f'{partyTable}/tr[{i + 1}]/td[1]/b').get()
            if address:
                partyAddress = response.xpath(f'{partyTable}/tr[{i + 1}]/td[2]').get()
                plainAddress = extract_text(partyAddress)   # use html-text module to extract multi-line text from html
                if 'unavailable' in plainAddress:
                    plainAddress = None
                else:
                    plainAddress = clean(plainAddress).replace('\n', ', ')      # turn newlines into commas
                if response.xpath(f'{partyTable}/tr[{i + 1}]/td[4]/i').get():
                    partyAliases = None
                else:
                    getAliases = extract_text(response.xpath(f'{partyTable}/tr[{i + 1}]/td[4]').get())
                    partyAliases = clean(getAliases).replace('\n', ';')    # split aliases by semicolon
                party = {
                    'id': clean(partyId),
                    'party_name': clean(partyName),
                    'party_type': clean(partyType),
                    'party_address': clean(plainAddress),
                    'party_aliases': clean(partyAliases),
                    'case_id': caseId
                }
                caseParties.append(party)
            else:
                partyId = response.xpath(f'{partyTable}/tr[{i + 1}]/td[5]/a/text()').get()
                partyName = response.xpath(f'{partyTable}/tr[{i + 1}]/td[6]/b/text()').get()
                partyType = response.xpath(f'{partyTable}/tr[{i + 1}]/td[4]/text()').get()

        # write to csv file for debugging
        try:
            with open(partiesCSV, 'a+') as file:
                write = csv.writer(file, delimiter=',')
                for partyDict in caseParties:
                    write.writerow(list(partyDict.values()))
        except PermissionError:
            pass

        # write to sqlite database
        for party in caseParties:
            # check if party already exists in table AND if case already exists in party's row
            if self.cursor.execute('SELECT * FROM parties WHERE id=?;', (party['id'],)).fetchone():
                if not self.cursor.execute(f'SELECT * FROM parties WHERE case_ids like "%{party["case_id"]}%" and id="{party["id"]}";').fetchone():
                    self.cursor.execute(f'UPDATE parties SET case_ids=case_ids || ";{party["case_id"]}" WHERE id="{party["id"]}";')
                    self.cnx.commit()
            # else new entry
            else:
                self.cursor.execute('INSERT INTO parties VALUES(?,?,?,?,?,?);', tuple(party.values()))
                self.cnx.commit()

        # parse docket entries------------------------------------------------------------------------------------------
        docketCSV = self.saveFolder / 'case_docket.csv'

        # only run loop if there are docket entries
        if docketEntries:
            docketTable = f'/html/body/font/table[{tableNum}]'  # last table
            docketName = None
            docketDate = None
            docketTitle = None
            docketDescr = None
            docketMoney = None
            caseDocket = []
            docketEntry = {}

            for i, row in enumerate(response.xpath(f'{docketTable}/tr')):
                # skip first row and blank rows
                if not response.xpath(f'{docketTable}/tr[{i + 1}]/td[2]').get():
                    continue

                if response.xpath(f'{docketTable}/tr[{i + 1}]/td[1]/b/text()').get():
                    # account for if no entry
                    if response.xpath(f'{docketTable}/tr[{i + 1}]/td[2]/i/text()').get():
                        docketDescr = None
                    else:
                        description = response.xpath(f'{docketTable}/tr[{i + 1}]/td[2]/text()').get()   # get description
                        docketDescr = clean(description).replace('\n', ' ')   # replace newlines with spaces

                    docketEntry = {
                        'id': f'{caseId}:{str(len(caseDocket))}',      # N11C-09-068:0, N11C-09-068:1, ...
                        'date_filed': docketDate,
                        'description': clean(docketTitle),
                        'entry': clean(docketDescr),
                        'name': clean(docketName),
                        'monetary': clean(docketMoney),
                        'case_id': caseId
                    }
                    caseDocket.append(docketEntry)
                else:
                    # extract plaintext from element via http_text module
                    date = extract_text(response.xpath(f'{docketTable}/tr[{i + 1}]/td[1]').get())
                    # convert date from '23-JAN-2022\n03:53 PM' to '2022-01-23 15:53'
                    try:
                        docketDate = datetime.strptime(date, '%d-%b-%Y\n%I:%M %p').strftime('%Y-%m-%d %H:%M')
                    except ValueError as error:
                        print(f'{error}\n{response.body}')

                    docketTitle = response.xpath(f'{docketTable}/tr[{i + 1}]/td[2]/text()').get()
                    docketName = response.xpath(f'{docketTable}/tr[{i + 1}]/td[3]/text()').get()
                    docketMoney = response.xpath(f'{docketTable}/tr[{i + 1}]/td[4]/text()').get()

            # write to csv file for debugging
            try:
                with open(docketCSV, 'a+') as file:
                    write = csv.writer(file, delimiter=',')
                    for docketDict in caseDocket:
                        write.writerow(list(docketDict.values()))
            except PermissionError:
                pass

            # write to sqlite database
            for docket in caseDocket:
                # check if docket id exists in db
                if not self.cursor.execute('SELECT * FROM dockets where id=?;', (docket['id'],)).fetchone():
                    self.cursor.execute('INSERT INTO dockets VALUES(?,?,?,?,?,?,?);', tuple(docket.values()))
                    self.cnx.commit()

        self.finished_cases[response.meta["page"]] += 1

        # if number of rows finished == total rows requested
        if self.finished_cases[response.meta["page"]] == self.requestNum[response.meta["page"]]:
            self.finished_pages += 1
            print(f'[{self.letter}] Page finished. ({self.finished_pages}/{self.total_pages})')
        pass

def clean(string):
    # remove anything which is...
    # not alphanumeric, space, newline, forward slash, semicolon, period, dash, comma, apostrophe, quotation
    # excessive newlines and spaces in middle of string
    # hex unicode formatting data, spaces, and newlines in start and end of string
    # note: single newlines needed in middle of string for replacement purposes
    stripStr = ' \n\x8d\xa0'
    if string:
        return str(re.sub(r'[^ \nA-Za-z\d/:;.,\'\"-]+', '', re.sub(' +', ' ', re.sub('\n+', '\n', string))).strip(stripStr))
    else:
        return None
