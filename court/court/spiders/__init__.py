# This package will contain all scrapy spiders
import logging

#logging.getLogger('scrapy').propagate = False   # turns off debug feed when spider is ran

# disables all logging in project
for name, logger in logging.root.manager.loggerDict.items():
    logger.disabled = True
