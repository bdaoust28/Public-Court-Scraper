FROM python:3.10

WORKDIR /usr/src/app

COPY dependencies.txt .

RUN pip3 install --no-cache-dir -r dependencies.txt
RUN scrapy startproject court
RUN apt-get -y update
RUN apt-get -y upgrade
RUN apt-get install -y sqlite3 libsqlite3-dev

COPY . .

CMD ["python3", "-u", "master.py"]