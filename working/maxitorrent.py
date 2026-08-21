#VERSION: 1.25
"""
MaxiTorrent search (atomixhq.com). POSTs the query to the site's JSON result
endpoint, then follows each torrent's redirect page to the .torrent URL,
retrying against alternate page layouts when the redirect is absent.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import ClassVar, cast

from helpers import _headers as headers
from novaprinter import SearchResults, prettyPrinter


class maxitorrent:
    url = 'https://atomixhq.com'
    name = 'MaxiTorrent'
    size = ""
    count = 1
    pg: int = 0
    torrent_list: ClassVar[list[str]] = []
    
    class HTMLParser1(HTMLParser):
        indicador = 0
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == 'a' and self.indicador == 1:
                params = dict(attrs)
                href = params.get("href")
                if href is not None:
                    print("30 "+href)
                    maxitorrent.get_torrent3(href)
                self.indicador = 0
            elif tag == "div":
                params = dict(attrs)
                if params.get("style") == "float:left;width:100%;height:auto;text-align:center;":
                    self.indicador = 1

    class HTMLParser3(HTMLParser):
        indicador = 0
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == 'a' and self.indicador == 1:
                params = dict(attrs)
                href = params.get("href")
                if href is not None:
                    maxitorrent.get_torrent2(href)
            elif tag == "ul":
                params = dict(attrs)
                if params.get("class") == "buscar-list":
                    #print("indicador 1")
                    self.indicador = 1

        def handle_endtag(self, tag: str) -> None:
            if tag == 'ul':
                #print("end tag")
                self.indicador = 0

    class HTMLParser2(HTMLParser):
        indicador = 0
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == 'a' and self.indicador == 1:
                params = dict(attrs)
                href = params.get("href")
                if href is not None:
                    print("44 "+href)
                    maxitorrent.get_torrent2(href)
                self.indicador = 0
            elif tag == "span":
                params = dict(attrs)
                if params.get("class") == "color":
                    self.indicador = 1

    @staticmethod
    def retrieve_url2(url: str) -> bytes | str:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                return response.read()
        except urllib.error.URLError:
            return ""

    def do_post(self, full_url: str, what: str) -> bytes:
        query_args = {'s': what, 'pg': self.pg}
        encoded_args = urllib.parse.urlencode(query_args).encode('ascii')
        req = urllib.request.Request(full_url, data=encoded_args, headers=headers)
        with urllib.request.urlopen(req) as response:
            the_page = response.read()
            self.pg = self.pg + 1
            return the_page
            
    @staticmethod
    def montar_torrent(link: str) -> None:
        #print("montar_torrent")
        num = -1
        name = link
        if (name[-1] == "/"):
            name = name[:-1]
        
        #print(name)
        while name.find("/") >= 0 and name.split("/")[num].split('.')[0] != "":
            name = name.split("/")[num].split('.')[0]
            num = num - 1
            #print(name)
        
        link = maxitorrent.url + link[link.find("/"):]
        
        item: SearchResults = {
            'seeds': -1,
            'leech': -1,
            'name': name,
            'size': maxitorrent.size,
            'link': link,
            'engine_url': maxitorrent.url,
            'desc_link': link,
        }

        
        prettyPrinter(item)
        maxitorrent.count = maxitorrent.count + 1
        
    @staticmethod
    def get_torrent_core(link: str) -> None:
        if link not in maxitorrent.torrent_list: 
            print("ya está en lista")
            maxitorrent.torrent_list.append(link) 
        else:
            return
        
        html_virgen = maxitorrent.retrieve_url2(link)
        html_virgen = str(html_virgen)
        
        print("112 "+link)
        idx = html_virgen.find("window.location.href = \"//")
        print("114" + str(idx))
        html = html_virgen[idx:]
        html = html[:html.find("\";")]
        html = html[26:]
        if html == "":
            print("html vacio 1")
            idx = html_virgen.find("window.location.href = \"")
            html = html_virgen[idx-2:]
            html = html[:html.find("\";")]
            html = html[26:]
            if html != "":
                print("NO VACIO html vacio 1")
                maxitorrent.get_torrent3(html)
                return
        if html == "":
            print("html vacio 2")
            if html_virgen.find("float:left;width:100%;height:auto;text-align:center;") != -1:
                print("Parser1")
                maxitorrent.HTMLParser1().feed(str(html_virgen))
            if html_virgen.find(" style=\"color:#000;font-size:23px;\"") != -1:
                print("Parser3")
                #print(html_virgen)
                maxitorrent.HTMLParser3().feed(str(html_virgen))
            else:
                print("Parser2")
                maxitorrent.HTMLParser2().feed(str(html_virgen))
        else:
            print("Montar torrent")
            maxitorrent.montar_torrent(html)
        return
    
    @staticmethod
    def get_torrent2(link: str) -> None:
        maxitorrent.get_torrent_core(link)

    @staticmethod
    def get_torrent3(link: str) -> None:
        maxitorrent.get_torrent_core(maxitorrent.url + link)
    
    @staticmethod
    def get_torrent(guid: str) -> None:
        #print(guid)
        link = maxitorrent.url + "/" +  guid
        maxitorrent.get_torrent_core(link)
    
    def search(self, what: str, cat: str = 'all') -> None:
        self.pg = 1
        #print("search")
            
        while self.pg > 0:
            json_data = self.do_post(self.url+'/get/result/', what)
            payload = cast(object, json.loads(json_data))
            if not isinstance(payload, dict):
                return
            raw_data = payload.get('data')
            if not isinstance(raw_data, dict):
                return
            raw_torrents = raw_data.get('torrents')
            if not isinstance(raw_torrents, dict):
                return
            torrents = cast(dict[str, object], raw_torrents)
            #print (torrents)
            
            for v in torrents.values():
                # The API fills trailing slots of the last page with null; a
                # null entry is the signal to stop paginating.
                if v is None:
                    return
                if not isinstance(v, dict):
                    continue
                for v2 in cast(dict[str, object], v).values():
                    if not isinstance(v2, dict):
                        continue
                    for k3, v3 in cast(dict[str, object], v2).items():
                        if k3 == 'torrentSize':
                            maxitorrent.size = str(v3)
                        elif k3 == 'guid' and isinstance(v3, str):
                            self.get_torrent(v3)
                            
                            
            self.pg = self.pg + 1
        #print(maxitorrent.count)

if __name__ == "__main__":
    m = maxitorrent()
    m.search('calamar')
