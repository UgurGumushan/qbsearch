# VERSION: 2.2
"""Cpasbien (French) engine: movies and TV torrents.

The current site domain is pulled from a public URL file since the site
moves often; sizes arrive in French units (ex. 'Ko') which are converted.
"""

from __future__ import annotations

import logging
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import ClassVar

from helpers import _headers as headers
from helpers import download_file
from helpers import retrieve_url as _qbt_helper_retrieve_url
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


logger = logging.getLogger()

class cpasbien:
    # This is a fake url only for engine associations in file download
    url = "http://www.cpasbien.fr"
    name = "Cpasbien (french)"
    results_per_page = 50
    supported_categories: ClassVar[dict[str, list[str]]] = {"all": [""]}

    def __init__(self) -> None:
        self.real_url: str = self.find_url()
        logger.debug("Cpasbien URL: %s", self.real_url)

    def find_url(self) -> str:
        """Fetch the current site domain from a GitHub URL file so the engine
        keeps working when the domain moves."""
        link_github = "https://raw.githubusercontent.com/MarcBresson/cpasbien/master/cpasbien.url"
        try:
            req = urllib.request.Request(link_github, headers=headers)
            with _qbt_safe_urlopen(req) as response:
                content: str = response.read().decode()
            cpasbien_url = content.strip()
            return cpasbien_url or "http://www.cpasbien.biz"

        except urllib.error.URLError as e:
            default_url = "http://www.cpasbien.biz"

            if str(e.reason).lower() == "not found":
                logger.warning(
                    "Could not find URL '%s', defaulting to '%s'", link_github, default_url
                )
            else:
                logger.warning(
                    "Error '%s' while tring to find the current cpasbien URL, defaulting to '%s'",
                    e.reason,
                    default_url,
                )
            return default_url

    def download_torrent(self, desc_link: str) -> None:
        """find the link to the torrent"""
        logger.debug("Looking for the torrent download link at URL %s", desc_link)
        req = urllib.request.Request(desc_link, headers=headers)

        try:
            with _qbt_safe_urlopen(req) as response:
                content = response.read().decode()
        except urllib.error.URLError as errno:
            print(" ".join(("Connection error:", str(errno.reason))))
            return
        if not content:
            return

        link = self.real_url + re.findall(r'<a href="(/get_torrent/.*?)">', content)[0]
        logger.info("Found torrent download link with URL %s", link)

        print(download_file(link))

    def search(self, what: str, cat: str | None = None) -> None:
        results: list[SearchResults] = []
        len_old_result = 0
        for page in range(10):
            url = f"{self.real_url}/recherche/{what}/{page * self.results_per_page + 1}"

            parser = TableRowExtractor(self.real_url, self.url, results)

            try:
                data = retrieve_url(url)
            except urllib.error.URLError as errno:
                print(" ".join(("Connection error:", str(errno.reason))))
                break

            parser.feed(data)
            results.extend(parser.results)
            parser.close()

            # if there is no new result on the page, stop the search
            if len(results) - len_old_result == 0:
                break

            len_old_result = len(results)

        # Sort results
        good_order = [
            ord_res
            for _, ord_res in sorted(
                zip(
                    [[int(res["seeds"]), int(res["leech"])] for res in results], range(len(results))
                )
            )
        ]
        results = [results[x] for x in good_order[::-1]]

        logger.info("found %d torrents from cpasbien search engine", len(results))

        # Add engine
        for res in results:
            res["engine_url"] = self.url
        # Print
        for res in results:
            _qbt_prettyPrinter(res)


class TableRowExtractor(HTMLParser):
    map_name: dict[str, str]
    current_div_class: str = ""

    def __init__(self, url: str, engine_url: str, results: list[SearchResults]):
        self.results = results
        self.map_name = {"titre": "name", "poid": "size", "up": "seeds", "down": "leech"}
        self.in_tr = False
        self.in_table_corps = False
        self.in_div_or_anchor = False
        self.current_row: dict[str, str] = {}
        self.url = url
        self.engine_url = engine_url
        super().__init__()

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            # Only the results table (class "table-corps") is parsed.
            attrs = dict(attrs)
            if attrs.get("class") == "table-corps":
                self.in_table_corps = True

        if self.in_table_corps and tag == "tr":
            self.in_tr = True

        if self.in_tr and tag in ["div", "a"]:
            # Map the cell's class ("titre", "poid", "up", "down") to a result
            # field so the following text lands in the right column.
            self.in_div_or_anchor = True
            attrs = dict(attrs)
            self.current_div_class = self.map_name.get(attrs.get("class") or "", "")
            if tag == "a" and self.current_div_class == "name":
                href = attrs.get("href")
                if href is not None:
                    self.current_row["link"] = self.url + href
                    self.current_row["desc_link"] = self.url + href

    def handle_endtag(self, tag):
        if tag == "tr":
            if (
                self.in_table_corps
                and "desc_link" in self.current_row
                and self.current_row["desc_link"]
                not in [res.get("desc_link") for res in self.results]
            ):
                self.results.append(
                    SearchResults(
                        link=self.current_row["link"],
                        name=self.current_row["name"],
                        size=unit_fr2en(self.current_row["size"]),
                        seeds=int(self.current_row["seeds"]),
                        leech=int(self.current_row["leech"]),
                        engine_url=self.engine_url,
                        desc_link=self.current_row["desc_link"],
                    )
                )
            self.in_tr = False

            self.current_row = {}
        if tag == "table":
            self.in_table_corps = False
        if tag in ["div", "a"]:
            self.in_div_or_anchor = False

    def handle_data(self, data):
        if self.in_div_or_anchor and self.current_div_class:
            self.current_row[self.current_div_class] = data

    def get_rows(self) -> list[SearchResults]:
        return self.results


def unit_fr2en(size: str) -> str:
    """Convert French size units (Ko, Mo, ...) to English (KB, MB, ...)."""
    return re.sub(r"([KMGTP])o", lambda match: match.group(1) + "B", size, flags=re.IGNORECASE)
