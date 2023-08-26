# Public Court Scraper
###### by Beau Daoust (2022)

## Disclaimer
This project was originally developed as part of a job application (which is why this README is so verbose).
Although said application didn't lead to an offer, I believe in the principles of free and open-source software and have decided to make the source code available for educational purposes.
No warranty or guarantee is provided and the user assumes all responsibility for any actions or consequences resulting from the use of this project.

This project is open to contributions. 
If you would like to make changes or improve the project, feel free to submit a pull request.


## Dependencies
This project was written using Python 3.10.

Required modules:
* scrapy
* redis
* bs4
* html-text
* json2
* fake-useragent

This project expects a JSON file called 'target.json', which includes the following keys:
* host
* landing
* search
* docket
* searchReferer
* docketReferer


## Introduction

This project fills a SQLite database with case docket data obtained from a public court website via the Scrapy module.

This README assumes that you are using Docker Desktop on Windows and/or that you have Python 3.10 installed on your system (only necessary if not using Docker).
Windows PowerShell is recommended over Command Prompt (CMD) for ease of use.
I was not able to test run this project in Linux, but if you are familiar with the OS, you should be able to follow along.

Abbreviations/terms this README uses:
* CMD = Command Prompt
* CLI = Command Line Interface
* PowerShell = Windows PowerShell

IMPORTANT in case you are not familiar with navigating directories in Windows PowerShell or CMD:
* Open PowerShell or CMD by typing its name in Windows Search.
* Enter `cd folder/` to move into another directory
* Enter `cd ..` to move up a directory.
* You can autocomplete a folder or file name by pressing the Tab key on your keyboard.


## Running this project

### Running via Docker:

0. Ensure that the docker daemon is running and all project files are downloaded and unzipped in your filesystem.
    - An easy way to ensure that Docker is running is to open CMD and enter command: `docker ps`. If an error is thrown, then docker is not running.
    - Recommendation: place sqlite3.exe in this project to perform step 5.
1. Open PowerShell (recommended) or CMD and navigate to the root directory of this project.
2. Run the command: `docker compose up -d --build` to build and run this project in a Docker container.
    - Verify this by opening Docker Desktop and ensure that 'public-court' is running.
    - If this did not work, refer to step 0 or move on to 'Running this project via .zip' below if all else fails.
3. In Docker Desktop, open 'public-court' and then open 'scraper-1' to view the project progress.
    - More details about project functionality in later sections.
4. Once the project finishes, click the CLI button at the top right of the window to access the container's filesystem.
    - NOTE ABOUT DOCKER: a container must be running to access its filesystem. Run the project again to gain access to the CLI. The container will likely stay open for at least 5 minutes.
    - NOTE ABOUT PROJECT: it is safe to run the project multiple times. The database will not contain duplicates.
5. To open the SQLite database, run the command: "sqlite3 public_court.db".
    - The database will have 3 tables: cases, parties, dockets
    - Try running a command, such as `SELECT * FROM cases WHERE id like 'J%';` to get all case IDs that start with J.
        - Note the quotation marks aroud "J%". This is important for SQLite to understand this command as a string.


### Running via unzipped folder (only necessary if Docker method fails):

0. Ensure that all project files are downloaded and unzipped in your filesystem.
    - Recommendation: place this project in your Desktop folder for ease of navigation.
1. Start a Redis server on your localhost.
    - Redis is a key-value store that is built for Linux. Memurai developed their own version for Windows that is functionally identical.
        - This service was mentioned by Microsoft as an alternative, seen [here](https://github.com/MicrosoftArchive/redis).
    - There will likely be a Windows Firewall pop-up asking about network permissions. Leave private network checked only, and click OK.
    - IMPORTANT: leave Memurai's CMD window open while running this project, as it is what allows the Redis server to run.
    - Failure to complete this step will result in an error and the project ceasing to function.
2. Open PowerShell (recommended) or CMD and navigate to the root directory of this project.
    - Note: all the following commands can be copied and pasted into the command line rather than typed.
3. Run the command: `.\venv\Scripts\activate.ps1`
    - If you're having trouble, follow along: type 'venv', press Tab, type 'scripts', press Tab, type 'activate.ps1', press Tab, then press Enter.
    - This activates the project's virtual environment, which is crucial.
4. Run the command: 'memurai.exe' to start a Redis server on your localhost.
5. Run the command: 'python master.py' to run the project. You should begin to see information about proxies and requests begin to appear.
    - If there are no valid proxies available, wait a minute or two and try again.
    - If there is an error, ensure that Python 3.10 is installed on your Windows system.
6. Once the project finishes, run the command: `.\sqlite3.exe .\public_court.db` to open the SQLite database for querying.
    - It is recommended to use the Tab key to autocomplete this command as it can be tricky.
    - The database will have 3 tables: cases, parties, dockets
    - Try running a command, such as `SELECT * FROM cases WHERE id like 'J%';` to get all case IDs that start with J.
        - Note the quotation marks aroud "J%". This is important for SQLite to understand this command as a string.


## Querying the database

_Refer to 'database-design-flow.png' for a visual of the database tables and their relationships._

This database contains 3 tables: 'cases', 'parties', and 'dockets':
* cases:      *id, title, date_filed, type, type_description, status, status_description, trial, related_cases
* parties:    *id, name, type, address, aliases, case_ids
* dockets:    *id, entry_date, description, entry, party_name, monetary, **case_id

_* = primary key_

_** = foreign key_

Note: parties.case_ids is not a foreign key due to it potentially containing multiple case IDs in one row. 
The constraint would have failed.


SQLite supports all usual SQL commands. If you aren't familiar with any, here are a few to try:

`SELECT * FROM parties;`
- Get all parties and their information, including address, aliases, and all case IDs they are found to associate with.

`SELECT * FROM cases WHERE id like 'J%';`
- Get all case IDs that start with "J".
- Note the percentage sign to the right of J. This means that any character to the right of J is accepted, but not to the left.

`SELECT dockets.id, parties.name, dockets.description FROM parties INNER JOIN dockets ON parties.name = dockets.party_name;"`    
- Get all docket IDs, party names, and docket descriptions from 'parties' and 'dockets' tables, linked via party names.

`SELECT * FROM cases INNER JOIN parties ON cases.id = parties.case_ids WHERE parties.name LIKE 'Jackson%';`    
- Get all columns from 'cases' table where party name starts with 'Jackson'

`SELECT name FROM parties WHERE case_ids LIKE '%SN98C-09-99%';`    
- Get all party names that contain 'SN98C-09-99' in the case_ids column
    - Note the parenthese on the left and right, which specify a string that exists within search parameters
        - A Python equivalent would be "if 'SN98C-09-99' in case_ids"



## Project Tasks

At a high level, this project accomplishes the following 3 tasks:
1. Scrape public court website for case docket data, evading any bot prevention measures in the process.
2. Clean, normalize, and deduplicate all scraped data.
3. Push clean data to a database to be queried later.

## Pipeline Architecture and Features

1. Ensure that the target website is up and responsive.
2. Create/connect to SQLite database titled 'public_court.db'.
    - This includes making 3 new tables: cases, parties, dockets
3. Retrieve list of free proxies from a scraped website.
4. Validate that the proxies are usable by querying an open API.
5. Find proxy that target website accepts.
6. Start scrapy spider by requesting 25 pages of partial last name search, starting at 'A'. Each page requests up to 20 case docket pages.
    - This project currently has hard limits set for time and ease of use. This will change if put into production.
    - If proxy fails during spider crawl, find new proxy to use in future requests.
    - If all proxies fail, generate new list of proxies to try.
        - If proxy list generation occurs over 3 times, project closes and recommends trying again later.
7. Cleans all scraped data through various means, primarily via regular expressions (RegEx) and stripping.
8. Appends data to three CSV files for visualization and debugging purposes.
9. Queries database to see if case docket data already exists, and inserts new data if not.
10. Queries database to ensure new values have been added after spider is finished.
11. Informs user of project runtime and how to query database.

## Project Limitations

Due to the limited time frame of this project (1 week), there are intentional limitations in place.
I wrote this program so that it functions as a "proof-of-concept", as its current purpose is to showcase my programming skills and methodology.

_To be clear, the functionality to scale this project is in place, but it is not enabled for the sake of simplicity._

The following are some limitations placed on the project for the time being:
1. There is a hard limit of 25 search page requests.
    - This is so the project can run and fill the database within a reasonable time frame for the end user.
    - The amount of time it takes to retrieve data from 25 pages of 20 case dockets each ranges from 3 minutes to 20 minutes.
    - If this project going into production, the limit will of course be lifted.
2. The project only crawls the results from one letter (A).
    - This is another feature limited for the sake of time.
    - Due to time constraints, I also did not have enough time to implement the 'scrapyd' package which would allow me to run spiders concurrently.
        - However, the project is designed to dynamically change letters if need be, so this implementation would likely not require any large changes.
3. There is no print flushing, or in-line terminal updates, for the user to keep track of progress.
    - This is minor, but could be a good quality of life feature for the end user.
    - This would prevent the project output from spamming 'Page finished (?/?)', and instead would update that line in the terminal with the new value.
    - This feature will be more crucial when the project is scaled up to crawl all available pages under every letter of the alphabet.
4. The Docker container does not stay up to allow for database querying once the project is done running.
    - This is due to time constraints, as the well-known methods of leaving the container running caused the project to fail.
    - I explored an alternative where I would install an always-up Ubuntu image with SQLite to share the Docker volume with, but I did not have enough time to implement it properly.
    - For the time being, the only way to query the SQLite database is to continually re-run the image.

## Major Decisions Made

Throughout this project, many decisions were made either for the sake of improvement or compromise.
The following are a few of those decisions, in no particular order:
1. I began to figure out an approach to doing mass searches of case docket information.
    - I decided against using a random number generator to search case IDs, as that would be very inefficient and could DDoS the website with so many requests.
    - I researched potential case IDs that could be given via other sources, such as news outlets. After little luck, I then investigated the search capabilities of each site.
    - I discovered the site allowed for partial last name searches, even down to a single letter.
        - This meant I could crawl all search results given per letter, allowing for a scalability down the line when scraping all 26 letters of the alphabet.
2. I discovered a potential bot prevention technique that ended up working in my favor.
    - The public court site's pages were actually made up of multiple subdocuments/forms, each with their own URL structure and set of headers.
    - This prevented the ability to scrape the main document as there was no relevant data there, however the subdocuments followed a rigid URL structure that could be reused dynamically for further requests.
    - This method fully evaded the subdocument structure that could have hindered progress, and perhaps improved the scraping process as there was no need for "clicking" on hyperlinks.
3. I decided not to include Case Event Schedule for active (or even sometimes closed) cases in the database.
    - This decision was made to reduce potential redundancy in the event that the site is scraped at a later date, and the schedule data is added to the case docket.
4. I made my own primary key for the docket table in the database.
    - When crawling docket data, there was no true way to identify whether such data was being re-crawled as there could sometimes be multiple docket entries done in the same minute, with the same names and title.
    - This resulted in lots of duplicate data in the docket table, so I made a new key formatted as: 'case_id:entry_index'.
        - For example, the first docket entry in the 'S16J-06-029' case is 'S16J-06-029:0'
5. I added functionality to check if the site is down before beginning the crawl.
    - This may be a given, but this was crucial in determining which proxies to use, as I had to be sure that the site was up before beginning the proxy rotation system.
6. I wrote my own middleware for scrapy to handle proxy-related errors.
    - Most, if not all, publicly available alternatives found online were years old and were error-prone and/or non-configurable.
    - Writing my own middleware ensured that it would be compatible with this project's architecture and as configurable as I wanted.
        - This also had the benefit of being much faster than said alternatives, as they would often look for a new proxy per request, which would dramatically slow down the process.
7. I decided to include a Redis server in this project.
    - Not only did this decision make the project easier to use, but it made it faster due to Redis's O(1) runtime.
    - This dramatically helped in project scalability, as most functionality in this project utilizes concurrent threading. Using a global set of data is essential for such tasks.
8. I chose SQLite as my database for this project.
    - This is due to SQLite's lightweight nature, ease of use and portability.
        - It is trivial create new database files, and testing SQLite's features is also hassle-free as you can load a temporary database in memory.
        - There is no need to install any additional software, as all that is needed is the portable sqlite3.exe.

## Notable Project Files

In this final section, I will give a summary of the important files in this project.

'master.py'
- This script runs the entire project, calling every other script as well as doing some initial checks.

'public_court.db'
- This is the database file that this project pushes scraped data into.

'proxyGenerator.py'
- This script crawls a site containing an always-updating list of free proxies to use.
- It outputs these proxies to a file called 'proxyList.txt'

'proxyChecker.py'
- This script takes 'proxyList.txt' and validates hundreds of proxies per second, uploading the ones that work to the Redis server.
- It also removes the bad proxies from 'proxyList.txt'

'PublicCourt.py'
- This script contains the scrapy spider that crawls the public court website.
- It cleans and strips all relevant data it gathers, then uploads it to the SQLite database

'crawler_script.py'
- This script calls the PublicCourtSpider class from PublicCourt.py and initializes a scripted instance of the spider, replacing the need to run the spider in the terminal.

'middlewares.py'
- This file contains the custom middleware I wrote to handle proxy failure and request timeouts.

'settings.py' and 'script_settings.py'
- These scripts are the settings files for the main Scrapy configuration and for the scripted version, respectively.

'case_*.csv'
- These files are generated on first run of the project and appended to on further runs (which does duplicate data).
- This simply provides a method of visualizing the gathered data without the need to query the database.

'Dockerfile', 'docker-compose.yml' and 'dependencies.txt'
- These files are crucial for the Docker image to be built and ran properly.
---

Thank you for taking the time to read this document!
This project was developed by Beau Daoust.
