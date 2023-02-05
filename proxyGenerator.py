import requests
from bs4 import BeautifulSoup

# get list of proxies
def getProxies():
    with open('proxyList.txt', 'a+') as proxies:
        r = requests.get('https://free-proxy-list.net/')
        soup = BeautifulSoup(r.content, 'html.parser')
        table = soup.find('tbody')
        for row in table:
            if row.find_all('td')[4].text == 'elite proxy':
                proxy = ':'.join([row.find_all('td')[0].text, row.find_all('td')[1].text])
                proxies.write(proxy + '\n')
            else:
                pass
        r.close()

if __name__ == "__main__":
    getProxies()
