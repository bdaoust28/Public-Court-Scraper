import time
import requests, threading, redis

badProxies = []
try:
    red = redis.Redis()  # establish connection with redis server at localhost
    red.ping()
except redis.exceptions.ConnectionError:
    red = redis.Redis('redis-host')  # establish connection with redis server at redis-host (in docker)

def tryProxy(proxy, debug=False):
    global badProxies, red
    try:
        # allow 8 seconds for connection to complete, 5 seconds to process data
        req = requests.get('https://httpbin.org/ip', proxies={'http': proxy, 'https': proxy}, timeout=(10, 5))
        if debug:
            print(f'{req.json()["origin"]} is valid')
        red.sadd('proxies', proxy)
        req.close()
        return proxy
    except:     # catch any error to ignore proxy
        badProxies.append(proxy)
        return None


def validateProxies(debug=False):
    global badProxies
    proxies = set(open('proxyList.txt', 'r').readlines())
    if debug:
        print('Checking proxies...')
    threads = []
    for proxy in proxies:
        proxy = proxy.strip()
        if proxy:
            threads.append(threading.Thread(target=tryProxy, args=(proxy, debug)))
        else:
            badProxies.append(proxy)
    for thread in threads:
        thread.daemon = True
        thread.start()

    time.sleep(25)  # allow for requests to finish
    with open('proxyList.txt', 'w') as file:
        # purge bad proxies from file
        for proxy in badProxies:
            proxies.discard(proxy)
        # rewrite file with good proxies
        for proxy in proxies:
            file.write(proxy)


if __name__ == "__main__":
    validateProxies(True)
