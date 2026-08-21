#VERSION: 0.13
"""dark-libria.it engine: Russian torrent site focused on anime.

Search result pages and then each series page are fetched in parallel;
magnets are taken from the Russian-language download buttons.
"""
from __future__ import annotations

SITE_URL = 'https://darklibria.it/'


import logging
import os
from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime, timezone
from html.parser import HTMLParser
from math import ceil
from re import compile as re_compile
from time import mktime
from typing import ClassVar
from urllib import parse

from helpers import retrieve_url as _qbt_helper_retrieve_url  # noqa: F401
from novaprinter import SearchResults, prettyPrinter

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


_qbt_retrieve_url = globals().get("_qbt_helper_retrieve_url")


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


LOG_FORMAT = '[%(asctime)s] %(levelname)s:%(name)s:%(funcName)s - %(message)s'
LOG_DT_FORMAT = '%d-%b-%y %H:%M:%S'


class darklibria:
    url = SITE_URL
    name = 'dark-libria'
    supported_categories: ClassVar[dict[str, str]]  = {'all': '0'}

    units_dict: ClassVar[dict[str, str]] = {"Тб": "TB", "Гб": "GB", "Мб": "MB", "Кб": "KB", "б": "B"}
    page_search_url_pattern = SITE_URL + 'search?page={page}&find={what}'
    dt_regex = re_compile(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')

    def __init__(self, output: bool = True) -> None:
        self.output = output
        self.torrents_count = 0
        self.pages_count = 0

    def search(self, what: str, cat: str = 'all') -> None:
        self.torrents_count = 0
        what = parse.quote(parse.unquote(what))
        logger.info(parse.unquote(what))
        first_page = self.handle_page(what, 1)
        if first_page is not None:
            self.set_search_data(first_page)
        pages = range(2, min(self.pages_count, MAX_PAGES) + 1)
        _qbt_run_parallel(self.handle_page, [(what, page) for page in pages], _qbt_new_deadline())
        logger.info('%s torrents', self.torrents_count)

    def handle_page(self, what: str, page: int) -> Parser | None:
        url = self.page_search_url_pattern.format(page=page, what=what)
        data = self.request_get(url)
        if not data:
            return
        parser = Parser(data)
        serials = parser.find_all('tbody', {'style': 'vertical-align: center'})
        jobs = []
        for serial in serials[:MAX_DETAILS]:
            link_tag = serial.a
            if link_tag is None:
                continue
            href = link_tag['href']
            if href is not None:
                jobs.append((href,))
        _qbt_run_parallel(self.handle_serial, jobs, _qbt_new_deadline())
        return parser

    def handle_serial(self, url: str) -> None:
        data = self.request_get(url)
        if not data:
            return
        parser = Parser(data)
        name_el = parser.find(attrs={'id': 'russian_name'})
        name = name_el.text if name_el is not None else ''
        for torrent_row in parser.find_all('tr', {'class': 'torrent'}):
            self.handle_torrent_row(torrent_row, name, url)

    def handle_torrent_row(self, torrent_row: Tag, name: str, url: str) -> None:
        type, quality, size_data, date_time, download, seeds, leech, *_ = torrent_row.children
        self.pretty_printer({
            'link': self.get_link(download),
            'name': self.get_name(name, quality, type, date_time),
            'size': self.get_size(size_data),
            'seeds': int(seeds.text),
            'leech': int(leech.text),
            'engine_url': self.url,
            'desc_link': url
        })
        self.torrents_count += 1

    def get_link(self, download: Tag) -> str:
        magnet = download.find(attrs={'title': 'Magnet-ссылка'})
        if magnet is not None:
            href = magnet['href']
            if href:
                return href

        torrent = download.find(attrs={'title': 'Скачать торрент'})
        if torrent is not None:
            href = torrent['href']
            if href:
                return href
        return ''
            
    def get_name(self, name: str, quality: Tag, type: Tag, date_time: Tag) -> str:
        return f'[{self.get_date(date_time)}] {name} [{type.text}] {quality.text}'

    def get_date(self, date_time: Tag) -> str:
        m = self.dt_regex.search(date_time.text)
        if m is None:
            return str(date_time.text)
        utc_dt_string = m.group()
        utc = datetime.strptime(utc_dt_string, '%Y-%m-%d %H:%M:%S')
        return str(utc2local(utc))

    def get_size(self, size_data: Tag) -> str:
        size, unit = size_data.text.split()
        return size + ' ' + self.units_dict[unit]

    def request_get(self, url: str) -> str | None:
        try:
            return retrieve_url(url)
        except Exception as exp:
            logger.error(exp)
            self.pretty_printer({
                'link': 'Error',
                'name': 'Connection failed',
                'size': "0",
                'seeds': -1,
                'leech': -1,
                'engine_url': self.url,
                'desc_link': self.url
            })

    def pretty_printer(self, dictionary: SearchResults) -> None:
        logger.debug(str(dictionary))
        if self.output:
            _qbt_prettyPrinter(dictionary)

    def set_search_data(self, parser: Parser) -> None:
        results = parser.find('span', {'class': 'text text-light mt-0'})
        if results:
            parts = results.text.split()
            items_count = int(parts[4])
            items_on_page = int(parts[2].split('-')[1])
            self.pages_count = ceil(items_count / items_on_page)

            logger.info('%s animes', items_count)
        else:
            self.pages_count = 0

        logger.info('%s pages', self.pages_count)


# Minimal BeautifulSoup-like DOM so the engine stays dependency-free.


class Tag:
    def __init__(
        self,
        tag: str | None = None,
        attrs: Sequence[tuple[str, str | None]] = (),
        is_self_closing: bool | None = None,
    ) -> None:
        self.type = tag
        self.is_self_closing = is_self_closing
        self._attrs = tuple(attrs)
        self._content: tuple[Tag | str, ...] = ()

    @property
    def attrs(self) -> dict[str, str | None]:
        """returns dict of Tag's attrs"""
        return dict(self._attrs)

    @property
    def text(self) -> str:
        """returns str of all contained text"""
        return ''.join(c if isinstance(c, str) else c.text for c in self._content)

    def _add_content(self, obj: object) -> None:
        if isinstance(obj, (Tag, str)):
            self._content += (obj,)
        else:
            raise TypeError(f'Argument must be str or {self.__class__}, not {obj.__class__}')

    def find(
        self,
        tag: str | Tag | None = None,
        attrs: Mapping[str, str | None] | None = None,
    ) -> Tag | None:
        """returns Tag or None"""
        return next(self._find_all(tag, attrs), None)

    def find_all(
        self,
        tag: str | Tag | None = None,
        attrs: Mapping[str, str | None] | None = None,
    ) -> list[Tag]:
        """returns list"""
        return list(self._find_all(tag, attrs))

    def _find_all(
        self,
        tag_type: str | Tag | None = None,
        attrs: Mapping[str, str | None] | None = None,
    ) -> Iterator[Tag]:
        """returns generator"""
        # get tags-descendants generator
        results = self.descendants

        # filter by Tag.type
        if tag_type is not None:
            if isinstance(tag_type, Tag):
                tag_type, attrs = tag_type.type, (
                    attrs if attrs else tag_type.attrs)

            results = filter(lambda t: t.type == tag_type, results)

        # filter by Tag.attrs
        if attrs:
            # remove Tags without attrs
            results = filter(lambda t: t._attrs, results)

            def filter_func(tag: Tag) -> bool:
                for key, expected in attrs.items():
                    actual = tag.attrs.get(key)
                    if actual is None or (expected is not None and expected not in actual):
                        return False
                return True

            # filter by attrs
            results = filter(filter_func, results)

        yield from results

    @property
    def children(self) -> Iterator[Tag]:
        """returns generator of tags-children"""
        return (obj for obj in self._content if isinstance(obj, Tag))

    @property
    def descendants(self) -> Iterator[Tag]:
        """returns generator of tags-descendants"""
        for child_tag in self.children:
            yield child_tag
            yield from child_tag.descendants

    def __getitem__(self, key: str) -> str | None:
        return self.attrs[key]

    def __getattr__(self, attr: str) -> Tag | None:
        if not attr.startswith("__"):
            return self.find(tag=attr)
        raise AttributeError(attr)

    def __repr__(self) -> str:
        attrs = ' '.join(str(k) if v is None else f'{k}="{v}"'
                         for k, v in self._attrs)
        starttag = f'{self.type} {attrs}' if attrs else self.type

        if self.is_self_closing:
            return f'<{starttag}>\n'
        else:
            nested = '\n' * bool(next(self.children, None)) + \
                ''.join(map(str, self._content))
            return f'<{starttag}>{nested}</{self.type}>\n'


class Parser(HTMLParser):
    """Feed HTML through and expose the root Tag tree for querying."""

    def __init__(self, html_code: str, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)

        self._root = Tag('_root')
        self._path: list[object] = [self._root]

        self.feed(''.join(map(str.strip, html_code.splitlines())))
        self.handle_endtag(str(self._root.type))
        self.close()

        self.find = self._root.find
        self.find_all = self._root.find_all

    @property
    def attrs(self) -> dict[str, str | None]:
        return self._root.attrs

    @property
    def text(self) -> str:
        return self._root.text

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._path.append(Tag(tag=tag, attrs=attrs))

    def handle_endtag(self, tag: str) -> None:
        for pos, node in tuple(enumerate(self._path))[::-1]:
            if isinstance(node, Tag) and node.type == tag and node.is_self_closing is None:
                node.is_self_closing = False

                for obj in self._path[pos + 1:]:
                    if isinstance(obj, Tag) and obj.is_self_closing is None:
                        obj.is_self_closing = True

                    node._add_content(obj)

                self._path = self._path[:pos + 1]

                break

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._path.append(Tag(tag=tag, attrs=attrs, is_self_closing=True))

    def handle_decl(self, decl: str) -> None:
        self._path.append(Tag(tag='!'+decl, is_self_closing=True))

    def handle_data(self, data: str) -> None:
        self._path.append(data)

    def __getitem__(self, key: str) -> str | None:
        return self.attrs[key]

    def __getattr__(self, attr: str) -> Tag | None:
        if not attr.startswith("__"):
            return getattr(self._root, attr)
        raise AttributeError(attr)

    def __repr__(self) -> str:
        return ''.join(str(c) for c in self._root._content)


def utc2local(utc: datetime) -> datetime:
    epoch = mktime(utc.timetuple())
    offset = datetime.fromtimestamp(epoch) - datetime.fromtimestamp(epoch, timezone.utc).replace(tzinfo=None)
    return utc + offset


is_main = __name__ == '__main__'
STORAGE = os.path.abspath(os.path.dirname(__file__))
if is_main:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt=LOG_DT_FORMAT)
else:
    logging.basicConfig(
        filename=os.path.join(STORAGE, 'darklibria.log'),
        level=logging.WARNING,
        format=LOG_FORMAT,
        datefmt=LOG_DT_FORMAT,
    )
logger = logging.getLogger('darklibria')

if is_main:
    import sys
    darklibria(output=False).search(sys.argv[-1])
