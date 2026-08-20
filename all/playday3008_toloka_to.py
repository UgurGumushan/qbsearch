# VERSION: 1.20
# AUTHORS: PlayDay

# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# CHANGELOG:
# 1.00 - Initial release
# 1.01 - Changed logger level from INFO to WARNING (as qBittorrent treats anything in stderr as an error)
# 1.10 - Moved config flags to JSON file; added Config/ConfigJson dataclasses; auto-create template config; save config back to propagate new fields
# 1.11 - Code quality: sorted imports (PEP8); replaced runtime assertion with Literal type; default seeds/leech to -1; added type checker/linter ignore comments; added class-time assert to validate SearchResultsKeys matches TypedDict
# 1.12 - Added inline tests (run with: pytest toloka_to.py or python toloka_to.py --test)
# 1.13 - Fixed search: decode pre-encoded query from nova2.py to avoid double URL-encoding
# 1.14 - Added log_level config option (DEBUG, INFO, WARNING, ERROR, CRITICAL); default/unset = WARNING
# 1.15 - Fixed URL construction (avoid double slashes, handle full URLs); removed unused download_url attribute; improved log_level default handling
# 1.16 - Refactored ConfigJson to reference Config class defaults instead of hardcoded values
# 1.17 - Fixed size parsing: now returns bytes (int) instead of string for qBittorrent compatibility
# 1.18 - Added FileHandler for logging to toloka_to.log file
# 1.19 - Added browser headers (User-Agent, etc.) to fix 403 Forbidden errors; better response handling; use logger.exception() for full tracebacks
# 1.20 - Extracted tests to dedicated test files; code formatting with ruff

# INSTALLATION:
# 1. Install the plugin: https://github.com/qbittorrent/search-plugins/wiki/Install-search-plugins
#
# 2. On first search, a config file (toloka_to.json) will be created automatically.
#    Edit it with your toloka.to credentials:
#    {
#        "username": "your_username",
#        "password": "your_password",
#        "cache_login_cookies": true,
#        "log_level": "WARNING"
#    }
#
#    Config file location:
#    - Linux:   ~/.local/share/qBittorrent/nova3/engines/toloka_to.json
#    - macOS:   ~/Library/Application Support/qBittorrent/nova3/engines/toloka_to.json
#    - Windows: %LOCALAPPDATA%\qBittorrent\nova3\engines\toloka_to.json
#
# 3. Optional settings:
#    - cache_login_cookies: true (default) - saves session cookies to avoid re-login
#    - log_level: DEBUG, INFO, WARNING (default), ERROR, CRITICAL
#
# REQUIREMENTS:
# - A valid toloka.to account (registration required)
# - qBittorrent 4.1.0+ with Search functionality enabled

import gzip
import json
import logging
import os
import re
import sys
import tempfile
import zlib
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import IntEnum
from html.parser import HTMLParser
from http.client import HTTPResponse
from http.cookiejar import LoadError, LWPCookieJar
from pathlib import Path
from typing import Literal, Optional, TypedDict, cast, get_args
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urlparse
from urllib.request import HTTPCookieProcessor, OpenerDirector, Request, build_opener

from nova2 import Category, Engine  # pyright: ignore[reportMissingModuleSource]
from novaprinter import SearchResults, prettyPrinter  # pyright: ignore[reportMissingModuleSource]

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger(__name__)


__all__ = ["toloka_to"]


class SubForum(TypedDict):
    forum_id: int
    subforums: dict[str, int]


class CategoryEntry(TypedDict):
    category_id: int
    forums: dict[str, SubForum]


# fmt: off
FORUM_MAP: dict[str, CategoryEntry] = {
    "Фільми українською": {
        "category_id": 8,
        "forums": {
            "Українське кіно": {
                "forum_id": 117,
                "subforums": {
                    "Мультфільми і казки": 84,
                    "Художні фільми": 42,
                    "Телесеріали": 124,
                    "Мультсеріали": 125,
                    "АртХаус": 129,
                    "Аматорське відео": 219,
                },
            },
            "Українське озвучення": {
                "forum_id": 118,
                "subforums": {
                    "Фільми": 16,
                    "Телесеріали": 32,
                    "Мультфільми": 19,
                    "Мультсеріали": 44,
                    "Аніме": 127,
                    "АртХаус": 55,
                    "Трейлери": 94,
                    "Короткометражні": 144,
                },
            },
            "Українські субтитри": {
                "forum_id": 190,
                "subforums": {
                    "Фільми": 70,
                    "Телесеріали": 192,
                    "Мультфільми": 193,
                    "Мультсеріали": 195,
                    "Аніме": 194,
                    "АртХаус": 196,
                    "Короткометражні": 197,
                },
            },
            "Документальні фільми українською": {
                "forum_id": 225,
                "subforums": {
                    "Українські наукові документальні фільми": 21,
                    "Українські історичні документальні фільми": 131,
                    "BBC": 226,
                    "Discovery": 227,
                    "National Geographic": 228,
                    "History Channel": 229,
                    "Інші іноземні документальні фільми": 230,
                },
            },
            "Телепередачі українською": {
                "forum_id": 119,
                "subforums": {
                    "Музичне відео": 18,
                    "Телевізійні шоу та програми": 132,
                },
            },
            "Український спорт": {
                "forum_id": 157,
                "subforums": {
                    "Олімпіада": 235,
                    "Чемпіонати Європи з футболу": 170,
                    "Чемпіонати світу з футболу": 162,
                    "Чемпіонат та Кубок України з футболу": 166,
                    "Єврокубки": 167,
                    "Збірна України": 168,
                    "Закордонні чемпіонати": 169,
                    "Футбольне відео": 54,
                    "Баскетбол, хоккей, волейбол, гандбол, футзал": 158,
                    "Бокс, реслінг, бойові мистецтва": 159,
                    "Авто, мото": 160,
                    "Інший спорт, активний відпочинок": 161,
                },
            },
            "HD українською": {
                "forum_id": 136,
                "subforums": {
                    "Фільми в HD": 96,
                    "Серіали в HD": 173,
                    "Мультфільми в HD": 139,
                    "Мультсеріали в HD": 174,
                    "Документальні фільми в HD": 140,
                },
            },
            "DVD українською": {
                "forum_id": 120,
                "subforums": {
                    "Художні фільми та серіали в DVD": 66,
                    "Мультфільми та мультсеріали в DVD": 137,
                    "Документальні фільми в DVD": 138,
                },
            },
            "Відео для мобільних (iOS, Android, Windows Phone)": {
                "forum_id": 237,
                "subforums": {},
            },
            "Звукові доріжки та субтитри": {
                "forum_id": 33,
                "subforums": {},
            },
        },
    },
    "Українська музика": {
        "category_id": 7,
        "forums": {
            "Українська музика (lossy)": {
                "forum_id": 8,
                "subforums": {
                    "Поп, Естрада": 23,
                    "Джаз, Блюз": 24,
                    "Етно, Фольклор, Народна, Бардівська": 43,
                    "Інструментальна, Класична та неокласична": 35,
                    "Рок, Метал, Альтернатива, Панк, СКА": 37,
                    "Реп, Хіп-хоп, РнБ": 36,
                    "Електронна музика": 38,
                    "Невидане": 56,
                },
            },
            "Українська музика (lossless)": {
                "forum_id": 98,
                "subforums": {
                    "Поп, Естрада": 100,
                    "Джаз, Блюз": 101,
                    "Етно, Фольклор, Народна, Бардівська": 102,
                    "Інструментальна, Класична та неокласична": 103,
                    "Рок, Метал, Альтернатива, Панк, СКА": 104,
                    "Реп, Хіп-хоп, РнБ": 105,
                    "Електронна музика": 106,
                },
            },
        },
    },
    "Література українською": {
        "category_id": 3,
        "forums": {
            "Друкована література": {
                "forum_id": 11,
                "subforums": {
                    "Українська художня література (до 1991 р.)": 134,
                    "Українська художня література (після 1991 р.)": 177,
                    "Зарубіжна художня література": 178,
                    "Наукова література (гуманітарні дисципліни)": 179,
                    "Наукова література (природничі дисципліни)": 180,
                    "Навчальна та довідкова": 183,
                    "Періодика": 181,
                    "Батькам та малятам": 182,
                    "Графіка (комікси, манґа, BD та інше)": 184,
                },
            },
            "Аудіокниги українською": {
                "forum_id": 185,
                "subforums": {
                    "Українська художня література": 135,
                    "Зарубіжна художня література": 186,
                    "Історія, біографістика, спогади": 187,
                    "Сирий матеріал": 189,
                },
            },
        },
    },
    "Програми українською": {
        "category_id": 3,
        "forums": {
            "Windows": {
                "forum_id": 9,
                "subforums": {
                    "Windows": 25,
                    "Офіс": 199,
                    "Антивіруси та безпека": 200,
                    "Мультимедія": 201,
                    "Утиліти, обслуговування, мережа": 202,
                },
            },
            "Linux, Mac OS": {
                "forum_id": 239,
                "subforums": {
                    "Linux": 26,
                    "Mac OS": 27,
                },
            },
            "Інші OS": {
                "forum_id": 240,
                "subforums": {
                    "Android": 211,
                    "iOS": 122,
                    "Інші мобільні платформи": 40,
                },
            },
            "Інше": {
                "forum_id": 241,
                "subforums": {
                    "Інфодиски, електронні підручники, відеоуроки": 203,
                    "Шпалери, фотографії та зображення": 12,
                    "Веб-скрипти": 249,
                },
            },
        },
    },
    "Ігри українською": {
        "category_id": 4,
        "forums": {
            "Ігри українською": {
                "forum_id": 10,
                "subforums": {
                    "PC ігри": 28,
                    "Mac ігри": 259,
                    "Українізації, доповнення, патчі...": 29,
                    "Мобільні та консольні ігри": 30,
                    "iOS": 41,
                    "Android": 212,
                },
            },
            "Переклад ігор українською": {
                "forum_id": 205,
                "subforums": {},
            },
        },
    },
    "Архів та смітник": {
        "category_id": 9,
        "forums": {
            "Закритий розділ": {
                "forum_id": 236,
                "subforums": {},
            },
            "Архіви": {
                "forum_id": 71,
                "subforums": {
                    "Архів відео": 72,
                    "Архів музики": 73,
                    "Архів програм": 74,
                    "Архів ігор": 75,
                    "Архів літератури": 76,
                },
            },
            "Неоформлені": {
                "forum_id": 121,
                "subforums": {
                    "Неоформлене відео": 45,
                    "Неоформлена музика": 46,
                    "Неоформлене програмне забезпечення": 47,
                    "Неоформлені ігри": 48,
                    "Неоформлена література": 208,
                },
            },
        },
    },
}
# fmt: on


class Payload:
    """Base class for payload data structures."""

    def to_dict(self) -> dict[str, str | list[str]]:
        """Convert dataclass fields to a dictionary suitable for urlencode."""
        result: dict[str, str | list[str]] = {}
        for k, v in vars(self).items():
            if v is None:
                continue
            if isinstance(v, list):
                # Convert IntEnum to int for Python 3.10 compatibility
                result[k] = [str(int(item) if isinstance(item, IntEnum) else item) for item in cast("list[object]", v)]
            elif isinstance(v, IntEnum):
                # Convert IntEnum to int for Python 3.10 compatibility
                result[k] = str(int(v))
            else:
                result[k] = str(v)
        return result


@dataclass
class LoginPayload(Payload):
    """Data structure for login payload."""

    username: str = ""
    """Username"""

    password: str = ""
    """Password"""

    autologin: Optional[Literal["on"]] = "on"
    """Remember me"""

    ssl: Optional[Literal["on"]] = "on"
    """HTTPS"""

    redirect: str = ""
    """Redirect URL"""

    login: Literal["Вхід"] = "Вхід"
    """The login action"""


@dataclass
class Config:
    """Configuration schema for the engine."""

    credentials: LoginPayload
    """Login credentials"""

    cache_login_cookies: bool = True
    """Whether to cache login cookies to disk"""

    log_level: str = logging.getLevelName(logger.getEffectiveLevel())
    """Logger level: DEBUG, INFO, WARNING, ERROR, CRITICAL. Default is WARNING."""

    def to_json(self) -> "ConfigJson":
        """Convert Config dataclass to ConfigJson."""
        return ConfigJson(
            username=self.credentials.username,
            password=self.credentials.password,
            cache_login_cookies=self.cache_login_cookies,
            log_level=self.log_level,
        )


@dataclass
class ConfigJson:
    username: str
    password: str
    cache_login_cookies: Optional[bool] = Config.cache_login_cookies
    log_level: Optional[str] = Config.log_level

    def to_config(self) -> "Config":
        """Convert ConfigJson to Config dataclass."""
        return Config(
            credentials=LoginPayload(username=self.username, password=self.password),
            cache_login_cookies=self.cache_login_cookies
            if self.cache_login_cookies is not None
            else Config.cache_login_cookies,
            log_level=self.log_level if self.log_level is not None else Config.log_level,
        )


@dataclass
class SearchPayload(Payload):
    """Data structure for search payload."""

    class SortByField(IntEnum):
        """Fields to sort by."""

        Registered = 1
        TopicName = 2
        Section = 3
        Downloaded = 4
        Replies = 5
        Views = 6
        Size = 7
        LastMessage = 8
        LastSeeder = 9
        Seeders = 10
        Leechers = 11

    class SortOrder(IntEnum):
        """Sort order directions."""

        Ascending = 1
        Descending = 2

    class ReleaseStatus(IntEnum):
        """Release status options."""

        Any = -1
        Regular = 0
        Gold = 1
        Silver = 2
        Bronze = 3
        Authors = 4

    # Search query
    nm: str = ""
    """Search query"""

    pn: Optional[str] = None
    """Author name"""

    # Forum selection
    f: Optional[list[int]] = None
    """Forum IDs"""

    c: Optional[int] = None
    """Category ID"""

    # Sorting options
    o: SortByField = SortByField.Registered
    """Sort by field"""

    s: SortOrder = SortOrder.Descending
    """Sort direction"""

    # Time filter
    tm: int = -1
    """Time period filter (days): -1 = Any time"""

    # Show only filters
    my: Optional[Literal[1]] = None
    """Show only my torrents"""

    sd: Optional[Literal[1]] = None
    """Show only with seeder"""

    n: Optional[Literal[1]] = None
    """Show only with new messages"""

    # Verification status filters (checkboxes)
    cg: Optional[Literal[1]] = None
    """Show checking status - green ?"""

    ct: Optional[Literal[1]] = None
    """Show verified/correct - green +"""

    at: Optional[Literal[1]] = None
    """Show almost correct - yellow ±"""

    nt: Optional[Literal[1]] = None
    """Show not correct - red -"""

    de: Optional[Literal[1]] = None
    """Show duplicates - red ∞"""

    nd: Optional[Literal[1]] = None
    """Show not checked - red ?"""

    # Column visibility
    shc: Optional[Literal[1]] = 1
    """Show category column"""

    shf: Optional[Literal[1]] = 1
    """Show forum column"""

    sha: Optional[Literal[1]] = 1
    """Show author column"""

    shs: Optional[Literal[1]] = 1
    """Show speed column"""

    tcs: Optional[Literal[1]] = 1
    """Show verification status column"""

    # Additional filters
    sns: int = -1
    """No seeders filter (days): -1 = Ignore, -2 = Never"""

    sds: ReleaseStatus = ReleaseStatus.Any
    """Release status filter"""

    # Submit
    send: Literal["Пошук"] = "Пошук"
    """Submit button value"""


def size_string_to_bytes(size_str: str) -> int:
    """Convert a human-readable size string to bytes.

    Supports both English (GB, MB, KB, TB, B) and Ukrainian (ГБ, МБ, КБ, ТБ, Б) units.
    Handles non-breaking spaces (\\xa0) and regular spaces.

    Args:
        size_str: Size string like "2.6 GB", "208 MB", "2.6\\xa0GB"

    Returns:
        Size in bytes as integer, or -1 if parsing fails

    """  # noqa: D301
    if not size_str:
        return -1

    # Normalize: replace non-breaking space with regular space and strip
    size_str = size_str.replace("\xa0", " ").strip()

    # Unit multipliers (case-insensitive for English, exact match for Ukrainian)
    units: dict[str, int] = {
        # English units
        "TB": 1024**4,
        "GB": 1024**3,
        "MB": 1024**2,
        "KB": 1024,
        "B": 1,
        # Ukrainian units
        "ТБ": 1024**4,
        "ГБ": 1024**3,
        "МБ": 1024**2,
        "КБ": 1024,
        "Б": 1,
    }

    # Try to extract number and unit
    # Match number (int or float) followed by optional space and unit
    match = re.match(r"^([\d.,]+)\s*([A-Za-zА-Яа-яІіЇїЄє]+)$", size_str)
    if not match:
        logger.debug("Failed to parse size string: %r", size_str)
        return -1

    number_str, unit = match.groups()
    # Handle both comma and dot as decimal separator
    number_str = number_str.replace(",", ".")

    try:
        number = float(number_str)
    except ValueError:
        logger.debug("Failed to parse size number: %r", number_str)
        return -1

    # Find matching unit (case-insensitive for English)
    multiplier = units.get(unit) or units.get(unit.upper())
    if multiplier is None:
        logger.debug("Unknown size unit: %r", unit)
        return -1

    return int(number * multiplier)


class TolokaHTMLParser(HTMLParser):
    """Parser for Toloka search results HTML using header-based column detection."""

    # Valid keys derived from SearchResults TypedDict
    # Type checkers cannot infer Literal types from TypedDict keys, so we define them manually
    # and validate at class-load time that they match the actual TypedDict
    SearchResultsKeys = Literal["link", "name", "size", "seeds", "leech", "engine_url", "desc_link", "pub_date"]
    assert set(get_args(SearchResultsKeys)) == set(SearchResults.__annotations__.keys()), (  # noqa: S101
        f"SearchResultsKeys out of sync: {set(get_args(SearchResultsKeys))} != {set(SearchResults.__annotations__.keys())}"
    )  # nosec B101

    # Mapping from header text to SearchResults field names
    HEADER_TO_FIELD: dict[str, SearchResultsKeys] = {  # noqa: RUF012
        "Назва": "name",
        "Посил": "link",
        "Розмір": "size",
        "S": "seeds",
        "L": "leech",
        "Додано": "pub_date",
    }

    @staticmethod
    def _empty_search_result() -> SearchResults:
        """Create an empty SearchResults with default values."""
        return SearchResults(
            {
                "link": "",
                "name": "",
                "size": -1,
                "seeds": -1,
                "leech": -1,
                "engine_url": "",
                "desc_link": "",
                "pub_date": -1,
            },
        )

    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResults] = []

        # Pagination: list of next page URLs (relative)
        self.next_page_urls: list[str] = []

        # Column index -> field name mapping (populated from header row)
        self._col_to_field: dict[int, TolokaHTMLParser.SearchResultsKeys] = {}

        # Parsing state
        self._in_header_cell: bool = False
        self._in_data_row: bool = False
        self._header_col_index: int = 0
        self._header_text: str = ""
        self._data_col_index: int = 0
        self._current_field: Optional[TolokaHTMLParser.SearchResultsKeys] = None
        self._current_result: Optional[SearchResults] = None
        self._capture_text: bool = False
        self._current_text: str = ""

        # Pagination parsing state
        self._in_navigation_span: bool = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attrs_dict = dict(attrs)

        # Detect navigation span for pagination
        if tag == "span" and attrs_dict.get("class") == "navigation":
            self._in_navigation_span = True

        # Parse pagination links inside navigation span
        if tag == "a" and self._in_navigation_span:
            href = attrs_dict.get("href") or ""
            if "tracker.php?" in href and "start=" in href:
                # Avoid duplicates and skip current page (no start= means page 1)
                if href not in self.next_page_urls:
                    self.next_page_urls.append(href)

        if tag == "tr":
            class_attr = attrs_dict.get("class") or ""
            if class_attr in ("prow1", "prow2"):
                self._in_data_row = True
                self._data_col_index = 0
                self._current_result = TolokaHTMLParser._empty_search_result()

        elif tag == "th":
            self._in_header_cell = True
            self._header_text = ""

        elif tag == "td" and self._in_data_row and self._current_result:
            self._current_field = self._col_to_field.get(self._data_col_index)
            self._data_col_index += 1

            if self._current_field in ("size", "pub_date"):
                self._capture_text = True
                self._current_text = ""

        elif tag == "a" and self._in_data_row and self._current_result:
            href = attrs_dict.get("href") or ""

            if self._current_field == "link" and href.startswith("download.php?id="):
                self._current_result["link"] = href

            elif self._current_field == "name" and href.startswith("t") and len(href) > 1:
                if href[1:].isdigit():
                    self._current_result["desc_link"] = href
                    self._capture_text = True
                    self._current_text = ""

        elif tag == "b" and self._in_data_row:
            if self._current_field in ("seeds", "leech"):
                self._capture_text = True
                self._current_text = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self._in_navigation_span:
            self._in_navigation_span = False

        elif tag == "th" and self._in_header_cell:
            header_text = self._header_text.strip()
            if header_text in self.HEADER_TO_FIELD:
                self._col_to_field[self._header_col_index] = self.HEADER_TO_FIELD[header_text]
            self._header_col_index += 1
            self._in_header_cell = False

        elif tag == "tr":
            if self._in_data_row:
                if self._current_result and self._current_result["link"] and self._current_result["name"]:
                    self.results.append(self._current_result)
                self._in_data_row = False
                self._current_result = None

        elif tag == "td":
            self._current_field = None
            self._capture_text = False

        elif tag == "a" and self._current_field == "name" and self._current_result:
            if self._capture_text and self._current_text:
                self._current_result["name"] = self._current_text.strip()
            self._capture_text = False

        elif tag == "b" and self._current_result:
            if self._current_field in ("seeds", "leech") and self._capture_text:
                try:
                    self._current_result[self._current_field] = int(self._current_text.strip())
                except ValueError:
                    logger.debug("Failed to parse %s value: %r", self._current_field, self._current_text.strip())
                self._capture_text = False

    def handle_data(self, data: str) -> None:
        if self._in_header_cell:
            self._header_text += data

        if self._capture_text:
            self._current_text += data

        if not self._current_result:
            return

        if self._current_field == "size" and self._current_result["size"] == -1:
            size_text = data.strip()
            if size_text and any(
                unit in size_text for unit in ("TB", "GB", "MB", "KB", "B", "ТБ", "ГБ", "МБ", "КБ", "Б")
            ):
                self._current_result["size"] = size_string_to_bytes(size_text)

        if self._current_field == "pub_date":
            date_text = data.strip()
            if date_text and "-" in date_text:
                try:
                    dt = datetime.strptime(date_text, "%Y-%m-%d")
                    self._current_result["pub_date"] = int(dt.timestamp())
                except ValueError:
                    logger.debug("Failed to parse pub_date: %r", date_text)


class toloka_to(Engine):  # noqa: N801
    url: str = "https://toloka.to/"
    name: str = "Гуртом — торрент-толока"

    # Shorthand aliases for FORUM_MAP paths
    _F = FORUM_MAP["Фільми українською"]["forums"]
    _L = FORUM_MAP["Література українською"]["forums"]
    _M = FORUM_MAP["Українська музика"]["forums"]
    _P = FORUM_MAP["Програми українською"]["forums"]
    _G = FORUM_MAP["Ігри українською"]["forums"]

    supported_categories: dict[str, str] = {  # noqa: RUF012
        Category.all.name: "-1",
        Category.books.name: ",".join(
            str(x)
            for x in [
                _L["Друкована література"]["forum_id"],
                _L["Аудіокниги українською"]["forum_id"],
            ]
        ),
        Category.games.name: ",".join(
            str(x)
            for x in [
                _G["Ігри українською"]["forum_id"],
                _G["Переклад ігор українською"]["forum_id"],
            ]
        ),
        Category.music.name: ",".join(
            str(x)
            for x in [
                _M["Українська музика (lossy)"]["forum_id"],
                _M["Українська музика (lossless)"]["forum_id"],
                _F["Телепередачі українською"]["subforums"]["Музичне відео"],
            ]
        ),
        Category.software.name: ",".join(
            str(x)
            for x in [
                _P["Windows"]["forum_id"],
                _P["Linux, Mac OS"]["forum_id"],
                _P["Інші OS"]["forum_id"],
                _P["Інше"]["forum_id"],
            ]
        ),
        Category.anime.name: ",".join(
            str(x)
            for x in [
                _F["Українське озвучення"]["subforums"]["Аніме"],
                _F["Українські субтитри"]["subforums"]["Аніме"],
            ]
        ),
        Category.movies.name: ",".join(
            str(x)
            for x in [
                # Українське кіно
                _F["Українське кіно"]["subforums"]["Мультфільми і казки"],
                _F["Українське кіно"]["subforums"]["Художні фільми"],
                _F["Українське кіно"]["subforums"]["АртХаус"],
                _F["Українське кіно"]["subforums"]["Аматорське відео"],
                # Українське озвучення
                _F["Українське озвучення"]["subforums"]["Фільми"],
                _F["Українське озвучення"]["subforums"]["Мультфільми"],
                _F["Українське озвучення"]["subforums"]["АртХаус"],
                _F["Українське озвучення"]["subforums"]["Короткометражні"],
                # Українські субтитри
                _F["Українські субтитри"]["subforums"]["Фільми"],
                _F["Українські субтитри"]["subforums"]["Мультфільми"],
                _F["Українські субтитри"]["subforums"]["АртХаус"],
                _F["Українські субтитри"]["subforums"]["Короткометражні"],
                # Документальні фільми українською
                _F["Документальні фільми українською"]["forum_id"],
                # HD українською
                _F["HD українською"]["subforums"]["Фільми в HD"],
                _F["HD українською"]["subforums"]["Мультфільми в HD"],
                _F["HD українською"]["subforums"]["Документальні фільми в HD"],
                # DVD українською (combined film & series categories)
                _F["DVD українською"]["subforums"]["Художні фільми та серіали в DVD"],
                _F["DVD українською"]["subforums"]["Мультфільми та мультсеріали в DVD"],
                _F["DVD українською"]["subforums"]["Документальні фільми в DVD"],
            ]
        ),
        Category.tv.name: ",".join(
            str(x)
            for x in [
                # Українське кіно
                _F["Українське кіно"]["subforums"]["Телесеріали"],
                _F["Українське кіно"]["subforums"]["Мультсеріали"],
                # Українське озвучення
                _F["Українське озвучення"]["subforums"]["Телесеріали"],
                _F["Українське озвучення"]["subforums"]["Мультсеріали"],
                # Українські субтитри
                _F["Українські субтитри"]["subforums"]["Телесеріали"],
                _F["Українські субтитри"]["subforums"]["Мультсеріали"],
                # Телепередачі українською
                _F["Телепередачі українською"]["subforums"]["Телевізійні шоу та програми"],
                # Український спорт
                _F["Український спорт"]["forum_id"],
                # HD українською
                _F["HD українською"]["subforums"]["Серіали в HD"],
                _F["HD українською"]["subforums"]["Мультсеріали в HD"],
                # DVD українською (combined film & series categories)
                _F["DVD українською"]["subforums"]["Художні фільми та серіали в DVD"],
                _F["DVD українською"]["subforums"]["Мультфільми та мультсеріали в DVD"],
                # Documentary channels (also in movies)
                _F["Документальні фільми українською"]["subforums"]["BBC"],
                _F["Документальні фільми українською"]["subforums"]["Discovery"],
                _F["Документальні фільми українською"]["subforums"]["National Geographic"],
                _F["Документальні фільми українською"]["subforums"]["History Channel"],
            ]
        ),
        # Category.pictures.name: "",
    }

    del _F, _L, _M, _P, _G

    login_url: str = f"{url}login.php"
    search_url: str = f"{url}tracker.php"

    def __init__(self) -> None:
        engine_dir = Path(os.path.realpath(__file__)).parent
        self.config_file_path: Path = engine_dir / f"{self.__class__.__name__}.json"
        self.cookies_file_path: Path = engine_dir / f"{self.__class__.__name__}.cookies"
        self.config: Config = self._load_config()
        self.cookie_jar: LWPCookieJar = LWPCookieJar(self.cookies_file_path)
        self.opener: OpenerDirector = build_opener(HTTPCookieProcessor(self.cookie_jar))
        self.opener.addheaders = [
            (
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            ),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            ),
            ("Accept-Language", "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7"),
            ("Accept-Encoding", "gzip, deflate"),
            ("Connection", "keep-alive"),
            ("Upgrade-Insecure-Requests", "1"),
        ]
        self.logged_in: bool = False

        # Apply configured log level (default: WARNING)
        if self.config.log_level:
            level = getattr(logging, self.config.log_level.upper(), None)
            if isinstance(level, int):
                logger.setLevel(level)

        # Add file handler for logging
        self.log_file_path: Path = engine_dir / f"{self.__class__.__name__}.log"
        file_handler = logging.FileHandler(self.log_file_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

        if self.config.cache_login_cookies and self.cookies_file_path.exists():
            try:
                self.cookie_jar.load(str(self.cookies_file_path.resolve()), ignore_discard=True, ignore_expires=True)
                logger.info("Loaded %d cached cookies from %s", len(self.cookie_jar), self.cookies_file_path)
            except (LoadError, OSError) as e:
                logger.warning("Failed to load cached cookies from %s: %s", self.cookies_file_path, e)

    def _load_config(self) -> Config:
        """Load configuration from config file.

        Config file format (JSON):
        {
            "username": "your_username",
            "password": "your_password",
            "cache_login_cookies": true,
            "log_level": "WARNING"
        }

        log_level options: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: WARNING)
        """
        defaults = Config(credentials=LoginPayload())

        if not self.config_file_path.exists():
            template: ConfigJson = ConfigJson(  # nosec B106
                username="",
                password="",
            )
            try:
                with Path(self.config_file_path).open("w", encoding="utf-8") as f:
                    json.dump(asdict(template), f, indent=4)
                logger.warning(
                    "Config file created: %s. Fill in 'username' and 'password' fields.",
                    self.config_file_path,
                )
            except OSError:
                logger.exception("Failed to create config file %s", self.config_file_path)
            return defaults

        try:
            with Path(self.config_file_path).open(encoding="utf-8") as f:
                data: ConfigJson = ConfigJson(**json.load(f))

            if not data.username or not data.password:
                logger.warning("Config file missing 'username' or 'password' field")

            # Save config back to propagate any missing fields
            with Path(self.config_file_path).open("w", encoding="utf-8") as f:
                json.dump(asdict(data), f, indent=4)

            logger.debug("Loaded credentials for user: %s", data.username)
            return data.to_config()

        except json.JSONDecodeError:
            logger.exception("Invalid JSON in config file %s", self.config_file_path)
            return defaults
        except OSError:
            logger.exception("Failed to read config file %s", self.config_file_path)
            return defaults

    def _is_session_valid(self) -> bool:
        """Check if current session is authenticated by testing login.php redirect."""
        try:
            response: HTTPResponse = self.opener.open(self.login_url, timeout=10)
            redirect_path = urlparse(response.geturl()).path
        except (URLError, HTTPError, TimeoutError, OSError) as e:
            logger.debug("Session validation failed: %s", e)
            return False
        # If redirected to main page, session is valid
        return redirect_path == "/"

    def _login(self) -> Literal[True]:
        """Authenticate with Toloka using stored credentials."""
        if self.logged_in:
            logger.debug("Already logged in, skipping login")
            return True

        # Check if cached cookies are still valid
        if len(self.cookie_jar) > 0:
            logger.debug("Validating %d cached cookies...", len(self.cookie_jar))
            if self._is_session_valid():
                self.logged_in = True
                logger.info("Cached cookies are valid, skipping login")
                return True
            logger.info("Cached cookies expired, performing fresh login")
            self.cookie_jar.clear()

        if not self.config.credentials.username or not self.config.credentials.password:
            logger.error(
                "Missing credentials: username=%s, password=%s",
                bool(self.config.credentials.username),
                bool(self.config.credentials.password),
            )
            raise Exception("Username and password must be provided")

        logger.info("Attempting login for user: %s", self.config.credentials.username)
        login_data: bytes = urlencode(self.config.credentials.to_dict()).encode("utf-8")

        try:
            request = Request(toloka_to.login_url, data=login_data)
            request.add_header("Content-Type", "application/x-www-form-urlencoded")
            logger.debug("Sending login request to %s", toloka_to.login_url)

            response: HTTPResponse = self.opener.open(request, timeout=30)
            redirect_path = urlparse(response.geturl()).path
            logger.debug("Login response redirected to: %s", redirect_path)

            # Check if login was successful by looking for redirect to main page
            if redirect_path == "/":
                self.logged_in = True
                logger.info("Login successful for user: %s", self.config.credentials.username)

                if self.config.cache_login_cookies:
                    try:
                        self.cookie_jar.save(
                            str(self.cookies_file_path.resolve()),
                            ignore_discard=True,
                            ignore_expires=True,
                        )
                        logger.info("Saved %d cookies to %s", len(self.cookie_jar), self.cookies_file_path)
                    except OSError as e:
                        logger.warning("Failed to save cookies to %s: %s", self.cookies_file_path, e)

                return True
            logger.error(
                "Login failed for user %s: unexpected redirect to %s",
                self.config.credentials.username,
                redirect_path,
            )
            raise Exception(f"Login failed: unexpected redirect to {redirect_path}")

        except HTTPError as e:
            logger.exception("Login HTTP error: %s %s", e.code, e.reason)
            raise Exception(f"Login failed with HTTP {e.code}: {e.reason}") from e
        except URLError as e:
            logger.exception("Login URL error: %s", e.reason)
            raise Exception(f"Login failed: {e.reason}") from e
        except TimeoutError:
            logger.exception("Login request timed out after 30s")
            raise Exception("Login request timed out") from None
        except OSError as e:
            logger.exception("Login network error")
            raise Exception(f"Login failed: {e}") from e

    def _parse_and_print_results(self, html_content: str) -> TolokaHTMLParser:
        """Parse HTML content and print results. Returns the parser with pagination info."""
        parser = TolokaHTMLParser()
        parser.feed(html_content)

        for result in parser.results:
            # Ensure full URLs
            if result["link"] and not result["link"].startswith("http"):
                result["link"] = f"{toloka_to.url}{result['link'].lstrip('/')}"
            result["engine_url"] = toloka_to.url
            if result["desc_link"] and not result["desc_link"].startswith("http"):
                result["desc_link"] = f"{toloka_to.url}{result['desc_link'].lstrip('/')}"
            prettyPrinter(result)

        return parser

    def _decompress_response(self, response: HTTPResponse) -> bytes:
        """Read and decompress HTTP response based on Content-Encoding header."""
        data: bytes = response.read()
        match response.getheader("Content-Encoding"):
            case "gzip":
                data = gzip.decompress(data)
            case "deflate":
                data = zlib.decompress(data)
            case _:
                pass
        return data

    def _fetch_page(self, url: str) -> str:
        """Fetch a page and return decoded HTML content."""
        request = Request(url)
        response: HTTPResponse = self.opener.open(request, timeout=30)
        return self._decompress_response(response).decode("utf-8")

    def download_torrent(self, info: str) -> None:
        """Download torrent file and print path for qBittorrent."""
        logger.debug("Downloading torrent from: %s", info)
        self._login()

        try:
            request = Request(info)
            response: HTTPResponse = self.opener.open(request, timeout=30)
            data: bytes = self._decompress_response(response)

            # Write to temp file
            fd, path = tempfile.mkstemp(suffix=".torrent")
            with os.fdopen(fd, "wb") as f:
                f.write(data)

            result = f"{path} {info}"
            logger.info("Downloaded torrent: %s", result)
            print(result)

        except HTTPError as e:
            logger.exception("Download HTTP error: %s %s", e.code, e.reason)
            raise Exception(f"Download failed with HTTP {e.code}: {e.reason}") from e
        except URLError as e:
            logger.exception("Download URL error: %s", e.reason)
            raise Exception(f"Download failed: {e.reason}") from e
        except TimeoutError:
            logger.exception("Download request timed out for: %s", info)
            raise Exception("Download request timed out") from None
        except OSError as e:
            logger.exception("Download error")
            raise Exception(f"Download failed: {e}") from e

    def search(self, query: str, category: str = Category.all.name) -> None:
        """Search for torrents and print results via prettyPrinter."""
        if not query or not query.strip():
            logger.warning("Empty search query provided")
            return

        # nova2.py pre-encodes query with urllib.parse.quote(), so decode it first
        # to avoid double-encoding when we use urlencode() below
        query = unquote(query.strip())

        logger.info("Starting search for: %r in category: %s", query, category)
        self._login()

        # Parse forum IDs from category
        forum_ids: list[int] | None = None
        category_value = self.supported_categories.get(category, "-1")
        if category_value != "-1":
            forum_ids = [int(x) for x in category_value.split(",")]
            logger.debug("Searching in %d forums", len(forum_ids))

        search_payload = SearchPayload(nm=query, f=forum_ids)
        search_data: bytes = urlencode(search_payload.to_dict(), doseq=True).encode("utf-8")

        try:
            # Fetch first page via POST
            request = Request(toloka_to.search_url, data=search_data)
            logger.debug("Sending search request to %s", toloka_to.search_url)

            response: HTTPResponse = self.opener.open(request, timeout=30)
            logger.debug("Search response status: %s", response.status)
            html_content: str = self._decompress_response(response).decode("utf-8")
            logger.debug("Received %d bytes of HTML content", len(html_content))

            parser = self._parse_and_print_results(html_content)
            total_results = len(parser.results)
            logger.info("Page 1: found %d results for query: %r", total_results, query.strip())

            # Fetch remaining pages
            fetched_urls: set[str] = set()
            for page_url in parser.next_page_urls:
                if page_url in fetched_urls:
                    continue
                fetched_urls.add(page_url)

                full_url = f"{toloka_to.url}{page_url.lstrip('/')}"
                logger.debug("Fetching next page: %s", full_url)

                try:
                    page_html = self._fetch_page(full_url)
                    page_parser = self._parse_and_print_results(page_html)
                    total_results += len(page_parser.results)
                    logger.debug("Page fetched: %d results", len(page_parser.results))
                except (HTTPError, URLError, TimeoutError, OSError) as e:
                    logger.warning("Failed to fetch page %s: %s", page_url, e)
                    continue

            logger.info("Search completed, total %d results", total_results)

        except HTTPError as e:
            logger.exception("Search HTTP error: %s %s", e.code, e.reason)
            raise Exception(f"Search failed with HTTP {e.code}: {e.reason}") from e
        except URLError as e:
            logger.exception("Search URL error: %s", e.reason)
            raise Exception(f"Search failed: {e.reason}") from e
        except TimeoutError:
            logger.exception("Search request timed out after 30s for query: %r", query)
            raise Exception("Search request timed out") from None
        except OSError as e:
            logger.exception("Search network error")
            raise Exception(f"Search failed: {e}") from e


# Manual testing entry point (--test is handled at top of file before imports)
if __name__ == "__main__":
    engine = toloka_to()
    query = sys.argv[1] if len(sys.argv) > 1 else "ASDF"
    logger.info("Running standalone search for: %r", query)
    try:
        engine.search(query)
    except Exception:
        logger.exception("Search failed")
        sys.exit(1)
