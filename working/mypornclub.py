# VERSION: 1.1


import base64
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import ClassVar

from helpers import download_file, retrieve_url
from novaprinter import prettyPrinter


class mypornclub:
    url = "https://myporn.club"
    name = "MyPorn Club"
    supported_categories: ClassVar[dict[str, str]]  = {"all": "all"}

    pagination_regex = r"<div>Page\s\d\sof\s\d+</div>"

    class MyHtmlParser(HTMLParser):
        def error(self, message):
            pass

        DIV, A, SPAN, I, B = ("div", "a", "span", "i", "b")

        def __init__(self, url):
            HTMLParser.__init__(self)
            self.url = url
            self.row = {}
            self.rows = []

            self.foundResults = False
            self.insideRow = False
            self.insideTorrentData = False
            self.insideTorrentName = False
            self.insideMetaData = False
            self.insideLabelCell = False
            self.insideSizeCell = False
            self.insideSeedCell = False
            self.insideLeechCell = False
            self.shouldAddBrackets = False
            self.shouldAddName = False
            self.web_seed = False
            self.shouldGetDate = False
            self.magnet_regex = r'href=["\']magnet:.+?["\']'
            self.has_web_regex = (
                r"(sxyprn\.com[^\w]*?post[^\w]*?[\w]*?\.html)"
            )

        def preda(self, arg):
            arg[5] = int(arg[5])
            arg[5] -= int(self.ssut51(arg[6])) + int(self.ssut51(arg[7]))
            arg[5] = str(arg[5])
            return arg

        def ssut51(self, arg):
            str_num = ''.join(filter(str.isdigit, arg))
            sut = 0
            for char in str_num:
                sut += int(char)
            return sut

        def boo(self, ss, es):
            b = base64.b64encode((ss + "-" + "sxyprn.com" + "-" + es).encode()).decode()
            return b.replace('+', '-').replace('/', '_').replace('=', '.')

        def check_for_web_seed(self, web_page_url):
            id = web_page_url.split("/")[-1].split(".")[0]
            web_page_url = re.sub(r'\\', r'', web_page_url)
            page = retrieve_url(web_page_url)
            match = re.search(r'data-vnfo=(["\'])(?P<data>{.+?})\1', page)
            if match:
                data1 = json.loads(match.group("data"))
                parts = data1[id].split("/")
                parts[1] += "8" + "/" + self.boo(str(self.ssut51(parts[6])), str(self.ssut51(parts[7])))
                parts = self.preda(parts)
                final_url = 'https://sxyprn.com' + "/".join(parts)

                return "&ws=" + final_url + "&ws=" + urllib.request.urlopen(final_url).geturl() 
                       
            else:
                return None

        def handle_starttag(self, tag, attrs):
            params = dict(attrs)
            cssClasses = params.get("class", "")
            if "torrents_list" in cssClasses:
                self.foundResults = True
                return

            if (
                self.foundResults
                and "torrent_element" in cssClasses
                and tag == self.DIV
            ):
                self.insideRow = True
                if (
                    self.insideRow
                    and "torrent_element_text_div" in cssClasses
                    and tag == self.DIV
                ):
                    self.insideTorrentData = True

                if (
                    self.insideRow
                    and "torrent_element_info" in cssClasses
                    and tag == self.DIV
                ):
                    self.insideMetaData = True
                return

            if (
                self.insideTorrentData
                and "torrent_element_text_span" in cssClasses
                and tag == self.SPAN
            ):
                self.row["name"] = ""
                self.insideTorrentName = True
                self.shouldAddName = True

            if self.insideTorrentName and tag == self.B:
                self.shouldAddBrackets = True

            if self.insideTorrentName and tag == self.I:
                self.shouldAddBrackets = False
                self.shouldAddName = False
            
            if self.insideMetaData and 'linkadd' in cssClasses and tag == self.A:
                    self.shouldGetDate = True

            if (
                self.insideTorrentData
                and tag == self.A
                and "uploader_tel" not in cssClasses
            ):
                href = params.get("href")
                link = f"{self.url}{href}"
                self.row["desc_link"] = link
                torrent_page = retrieve_url(link)
                matches = re.finditer(self.magnet_regex, torrent_page, re.MULTILINE)
                magnet_urls = [x.group() for x in matches]
                self.row["link"] = magnet_urls[0].replace("'", '"').split('"')[1]

                _has_page = re.finditer(self.has_web_regex, torrent_page, re.MULTILINE)
                has_page = ["https://" + x.group(1) for x in _has_page]
                if has_page:
                    self.web_seed = self.check_for_web_seed(has_page[0])
                    if self.web_seed:
                        self.row["link"] = self.row["link"] + self.web_seed

                return

            if self.insideMetaData and "teis" in cssClasses:
                self.insideLabelCell = True

        def handle_data(self, data):

            if self.shouldGetDate:
                self.shouldGetDate = False
                from datetime import datetime
                if len(data.split(' ')) == 3 and data.split(' ')[2] == 'ago':
                    if data.split(' ')[1] == 'minutes':
                        self.row['pub_date'] = int(datetime.now().timestamp() - (int(data.split(' ')[0]) * 60))
                    if data.split(' ')[1] == 'hours':
                        self.row['pub_date'] = int(datetime.now().timestamp() - (int(data.split(' ')[0]) * 60 * 60))
                    if data.split(' ')[1] == 'days':
                        self.row['pub_date'] = int(datetime.now().timestamp() - (int(data.split(' ')[0]) * 60 * 60 * 24))
                    if data.split(' ')[1] == 'months':
                        self.row['pub_date'] = int(datetime.now().timestamp() - (int(data.split(' ')[0]) * 60 * 60 * 24 * 30))
                    if data.split(' ')[1] == 'years':
                        self.row['pub_date'] = int(datetime.now().timestamp() - (int(data.split(' ')[0]) * 60 * 60 * 24 * 365))
                    
                    

            if self.insideRow:
                if self.insideTorrentData and self.insideTorrentName:
                    if self.shouldAddBrackets:
                        self.row["name"] += f"[{data}]".strip()
                        self.shouldAddBrackets = False
                        return
                    if self.shouldAddName:
                        self.row["name"] += f" {data}".strip()
                        return

                if self.insideMetaData:
                    if self.insideSizeCell:
                        size = data.replace(",", ".")
                        self.row["size"] = size
                        self.insideSizeCell = False
                        self.insideLabelCell = False

                    if self.insideSeedCell:
                        self.row["seeds"] = data
                        self.insideSeedCell = False
                        self.insideLabelCell = False

                    if self.insideLeechCell:
                        self.row["leech"] = data
                        self.insideLeechCell = False
                        self.insideLabelCell = False

                    if self.insideLabelCell:
                        if data == "[size]:":
                            self.insideSizeCell = True
                        if data == "[seeders]:":
                            self.insideSeedCell = True
                        if data == "[leechers]:":
                            self.insideLeechCell = True

                

        def handle_endtag(self, tag):
            if self.insideRow and tag == self.DIV:
                if self.insideTorrentData and tag == self.DIV:
                    self.insideTorrentData = False
                    self.insideTorrentName = False
                    return

                if self.insideMetaData and tag == self.DIV:
                    self.insideMetaData = False
                    return

                self.row["engine_url"] = self.url

                if self.web_seed:
                    self.row["name"] = "💥 " + self.row["name"]
                    self.web_seed = False

                prettyPrinter(self.row)
                self.row = {}
                self.insideRow = False

    def download_torrent(self, info):
        print(download_file(info))

    def do_search(self, page, what):
        parser = self.MyHtmlParser(self.url)
        page_url = f"{self.url}/s/{what}/seeders/{page}"
        retrievedHtml = retrieve_url(page_url)
        parser.feed(retrievedHtml)
        parser.close()

    def search(self, what, cat="all"):
        parser = self.MyHtmlParser(self.url)
        what = what.replace("%20", "-")
        what = what.replace(" ", "-")
        page = 1

        page_url = f"{self.url}/s/{what}/seeders/{page}"
        retrievedHtml = retrieve_url(page_url)
        pagination_matches = re.finditer(
            self.pagination_regex, retrievedHtml, re.MULTILINE
        )
        pagination_pages = [x.group() for x in pagination_matches]
        lastPage = int(
            pagination_pages[0]
            .replace("<div>", "")
            .replace("</div>", "")
            .split(" ")[-1]
        )
        page += 1
        parser.feed(retrievedHtml)
        parser.close()

        threads = []
        while page <= lastPage:
            t = threading.Thread(args=(page, what), target=self.do_search)
            t.start()
            time.sleep(0.5)
            threads.append(t)
            page += 1

        for t in threads:
            t.join()