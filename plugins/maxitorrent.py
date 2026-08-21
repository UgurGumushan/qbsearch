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

_qbt_helper_retrieve_url = None
# BEGIN GENERATED QBITT SAFETY PREAMBLE
# This block is rendered into each standalone engine.  Keep it stdlib-only.
try:
    import socket as _qbt_socket
    import time as _qbt_time
    import urllib.error as _qbt_urllib_error
    from concurrent.futures import ThreadPoolExecutor as _QBTThreadPoolExecutor
    from concurrent.futures import TimeoutError as _qbt_FuturesTimeoutError
    from concurrent.futures import as_completed as _qbt_as_completed
    from threading import Lock as _qbt_Lock
    from urllib.request import urlopen as _qbt_urlopen
except ImportError as error:
    raise RuntimeError("qBittorrent safety preamble requires Python stdlib") from error

HTTP_TIMEOUT = 20.0
MAX_ATTEMPTS = 3
RETRY_DELAY = 0.25
MAX_WORKERS = 4
SEARCH_DEADLINE = 60.0
MAX_PAGES = 30
MAX_DETAILS = 100

_qbt_socket.setdefaulttimeout(HTTP_TIMEOUT)
_QBT_RETRYABLE_HTTP_STATUS = frozenset((408, 425, 429, 500, 502, 503, 504))
_qbt_search_deadline = None


class _QBTEmptyResponse:
    """Response-shaped empty value used when a request is exhausted."""

    status = 200
    code = 200

    def __init__(self, url: object = "") -> None:
        self._url = str(getattr(url, "full_url", url))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def close(self) -> None:
        return None

    def read(self, *args, **kwargs) -> bytes:
        return b""

    def getcode(self) -> int:
        return self.code

    def geturl(self) -> str:
        return self._url

    def getheader(self, name: str, default: object = None):
        return default

    def info(self):
        return self

    def get(self, name: str, default: object = None):
        return default


class _QBTTransientHTTPError(Exception):
    pass


def _qbt_sleep(attempt: int) -> None:
    _qbt_time.sleep(min(max(RETRY_DELAY, 0.0) * (attempt + 1), 1.0))


def _qbt_retry_call(operation) -> str:
    """Run a helper request a bounded number of times and return empty data."""
    for attempt in range(max(1, int(MAX_ATTEMPTS))):
        if _qbt_time.monotonic() >= _qbt_get_deadline():
            return ""
        try:
            result = operation()
            if isinstance(result, str) and result:
                return result
            if result not in (None, "", b""):
                return str(result)
        except _qbt_urllib_error.HTTPError as error:
            if error.code not in _QBT_RETRYABLE_HTTP_STATUS:
                try:
                    error.close()
                except Exception:
                    pass
                return ""
            try:
                error.close()
            except Exception:
                pass
        except Exception:
            pass
        if attempt + 1 < max(1, int(MAX_ATTEMPTS)):
            _qbt_sleep(attempt)
    return ""


def _qbt_safe_urlopen(url, data=None, *, context=None):
    """Open a URL with explicit timeout/retry policy and an empty fallback."""
    attempts = max(1, int(MAX_ATTEMPTS))
    for attempt in range(attempts):
        remaining = _qbt_get_deadline() - _qbt_time.monotonic()
        if remaining <= 0:
            return _QBTEmptyResponse(url)
        response = None
        try:
            request_timeout = min(float(HTTP_TIMEOUT), remaining)
            if context is None:
                response = _qbt_urlopen(url, data=data, timeout=request_timeout)
            else:
                response = _qbt_urlopen(
                    url, data=data, timeout=request_timeout, context=context
                )
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            if status in _QBT_RETRYABLE_HTTP_STATUS:
                response.close()
                response = None
                raise _QBTTransientHTTPError(status)
            if status is not None and status >= 400:
                response.close()
                return _QBTEmptyResponse(url)
            return response
        except _qbt_urllib_error.HTTPError as error:
            if error.code not in _QBT_RETRYABLE_HTTP_STATUS:
                try:
                    error.close()
                except Exception:
                    pass
                return _QBTEmptyResponse(url)
            try:
                error.close()
            except Exception:
                pass
        except (_QBTTransientHTTPError, OSError, EOFError, TimeoutError):
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
        except Exception:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            # A malformed request is not useful to retry, but it must not
            # abort the qBittorrent search process.
            return _QBTEmptyResponse(url)
        if attempt + 1 < attempts:
            _qbt_sleep(attempt)
    return _QBTEmptyResponse(url)


_qbt_retrieve_url = _qbt_helper_retrieve_url


def retrieve_url(*args, **kwargs) -> str:
    """Drop-in wrapper for qBittorrent's helper with bounded retries."""
    helper = _qbt_retrieve_url
    if not callable(helper):
        return ""
    return _qbt_retry_call(lambda: helper(*args, **kwargs))


_qbt_output_lock = _qbt_Lock()


def _qbt_prettyPrinter(result) -> None:
    """Serialize result records emitted by parallel workers."""
    with _qbt_output_lock:
        prettyPrinter(result)


def _qbt_run_parallel(worker, jobs, deadline=None):
    """Run bounded worker jobs, preserving completed work after failures."""
    jobs = list(jobs)
    if not jobs:
        return []
    if deadline is None:
        deadline = _qbt_get_deadline()
    executor = _QBTThreadPoolExecutor(max_workers=MAX_WORKERS)
    futures = []
    for job in jobs:
        if isinstance(job, tuple):
            futures.append(executor.submit(worker, *job))
        else:
            futures.append(executor.submit(worker, job))
    results = []
    try:
        remaining = max(0.0, deadline - _qbt_time.monotonic())
        for future in _qbt_as_completed(futures, timeout=remaining):
            try:
                results.append(future.result())
            except Exception:
                # One dead site/detail page must not discard other results.
                pass
    except _qbt_FuturesTimeoutError:
        for future in futures:
            future.cancel()
    finally:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # pragma: no cover - compatibility with old qBitt Python
            executor.shutdown(wait=False)
    return results


def _qbt_new_deadline() -> float:
    return _qbt_get_deadline()


def _qbt_get_deadline() -> float:
    global _qbt_search_deadline
    if _qbt_search_deadline is None:
        _qbt_search_deadline = _qbt_time.monotonic() + max(0.0, float(SEARCH_DEADLINE))
    return _qbt_search_deadline


# END GENERATED QBITT SAFETY PREAMBLE


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
            with _qbt_safe_urlopen(req) as response:
                return response.read()
        except urllib.error.URLError:
            return ""

    def do_post(self, full_url: str, what: str) -> bytes:
        query_args = {'s': what, 'pg': self.pg}
        encoded_args = urllib.parse.urlencode(query_args).encode('ascii')
        req = urllib.request.Request(full_url, data=encoded_args, headers=headers)
        with _qbt_safe_urlopen(req) as response:
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

        
        _qbt_prettyPrinter(item)
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

        while 0 < self.pg <= MAX_PAGES:
            json_data = self.do_post(self.url+'/get/result/', what)
            try:
                payload = cast(object, json.loads(json_data))
            except (TypeError, ValueError):
                return
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
