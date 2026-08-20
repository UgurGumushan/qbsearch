# VERSION: 1.00
# AUTHORS: OptimusKoala

import gzip
import io
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import unquote_plus, urlencode, urlsplit

from helpers import download_file
from novaprinter import prettyPrinter


CONFIG_FILE = "c411.json"
DEFAULT_CONFIG = {
    "site_url": "https://c411.org",
    "api_url": "https://c411.org/api",
    "api_key": "YOUR_API_KEY_HERE",
    "page_size": 100,
    "max_pages": 2,
    "debug": False,
    "debug_file": "c411.log",
}
MODULE_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_PATH = os.path.join(MODULE_DIR, CONFIG_FILE)
TORZNAB_NS = {"torznab": "http://torznab.com/schemas/2015/feed"}
INFOHASH_RE = re.compile(r"([0-9a-fA-F]{40})")


def _eprint(message):
    print(message, file=sys.stderr)


def _to_positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _save_default_config():
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
            json.dump(DEFAULT_CONFIG, handle, indent=2, sort_keys=True)
    except OSError:
        pass


def _load_configuration():
    config = DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            config.update(loaded)
    except ValueError:
        config["malformed"] = True
    except OSError:
        _save_default_config()

    config["site_url"] = str(config.get("site_url", DEFAULT_CONFIG["site_url"])).rstrip("/")
    config["api_url"] = str(config.get("api_url", DEFAULT_CONFIG["api_url"])).rstrip("/")
    config["api_key"] = str(config.get("api_key", "")).strip()
    config["page_size"] = min(_to_positive_int(config.get("page_size"), 100), 100)
    config["max_pages"] = min(_to_positive_int(config.get("max_pages"), 2), 10)
    config["debug"] = _to_bool(config.get("debug", False))
    config["debug_file"] = str(config.get("debug_file", DEFAULT_CONFIG["debug_file"])).strip() \
        or DEFAULT_CONFIG["debug_file"]
    return config


class c411:
    url = DEFAULT_CONFIG["site_url"]
    name = "C411"
    supported_categories = {
        "all": "",
        "anime": "2060,5070",
        "books": "7000,3030",
        "games": "1000,4050",
        "movies": "2000",
        "music": "3000",
        "software": "4000",
        "tv": "5000,5070,5080,5060",
    }

    def __init__(self):
        config = _load_configuration()
        self.site_url = config["site_url"]
        self.api_url = config["api_url"]
        self.api_key = config["api_key"]
        self.page_size = config["page_size"]
        self.max_pages = config["max_pages"]
        self.debug = config["debug"]
        self.debug_path = os.path.join(MODULE_DIR, config["debug_file"])
        self.malformed = bool(config.get("malformed"))

    def _sanitize(self, value):
        if not value:
            return value
        if self.api_key:
            return str(value).replace(self.api_key, "***")
        return str(value)

    def _log(self, message):
        if not self.debug:
            return
        line = "[%s] %s\n" % (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), self._sanitize(message))
        try:
            with open(self.debug_path, "a", encoding="utf-8") as handle:
                handle.write(line)
        except OSError:
            pass

    def _has_valid_api_key(self):
        return bool(self.api_key and self.api_key != DEFAULT_CONFIG["api_key"])

    def _emit_configuration_help(self):
        _eprint(
            "C411: missing API key. Edit `c411.json` next to the plugin and set `api_key`."
        )

    def _build_api_url(self, params):
        return "%s?%s" % (self.api_url, urlencode(params))

    def _get_browser_user_agent(self):
        base_date = datetime(2024, 4, 16)
        base_version = 125
        now_version = base_version + max(0, (datetime.utcnow() - base_date).days // 30)
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:%s.0) "
            "Gecko/20100101 Firefox/%s.0"
        ) % (now_version, now_version)

    def _http_get_raw(self, url):
        request = urllib.request.Request(url, headers={"User-Agent": self._get_browser_user_agent()})
        response = urllib.request.urlopen(request)  # nosec B310 # pylint: disable=consider-using-with
        data = response.read()
        if data[:2] == b"\x1f\x8b":
            with io.BytesIO(data) as compressed_stream, gzip.GzipFile(fileobj=compressed_stream) as gzipper:
                data = gzipper.read()

        charset = "utf-8"
        content_type = response.getheader("Content-Type", "")
        if "charset=" in content_type:
            charset = content_type.split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
        return data.decode(charset, "replace")

    def _get_torznab_attr(self, item, name):
        attr = item.find('./torznab:attr[@name="%s"]' % name, TORZNAB_NS)
        if attr is None:
            return None
        value = attr.attrib.get("value", "").strip()
        return value or None

    def _parse_pub_date(self, value):
        if not value:
            return -1
        try:
            return int(parsedate_to_datetime(value).timestamp())
        except (TypeError, ValueError, OverflowError):
            return -1

    def _parse_int(self, value, default=-1):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _extract_torrent_id(self, info):
        if not info:
            return None

        info = info.strip()
        match = INFOHASH_RE.search(info)
        if match is not None:
            return match.group(1).lower()

        path = urlsplit(info).path
        if path:
            for chunk in path.split("/"):
                match = INFOHASH_RE.fullmatch(chunk)
                if match is not None:
                    return match.group(1).lower()
        return None

    def _parse_response(self, payload):
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            self._log("Invalid XML response.")
            return []

        error = root.find("error")
        if error is not None:
            self._log(
                "API error %s - %s"
                % (error.attrib.get("code", "?"), error.attrib.get("description", "unknown"))
            )
            return []

        channel = root.find("channel")
        if channel is None:
            return []

        results = []
        for item in channel.findall("item"):
            infohash = (item.findtext("guid") or "").strip().lower()
            desc_link = (item.findtext("comments") or item.findtext("link") or "").strip()
            title = (item.findtext("title") or infohash or desc_link).strip()
            size_value = item.findtext("size") or self._get_torznab_attr(item, "size")
            seeds = self._parse_int(self._get_torznab_attr(item, "seeders"))
            peers = self._parse_int(self._get_torznab_attr(item, "peers"))
            leech = max(peers - seeds, 0) if seeds >= 0 and peers >= 0 else -1
            pub_date = self._parse_pub_date(item.findtext("pubDate"))

            if not desc_link and infohash:
                desc_link = "%s/torrents/%s" % (self.site_url, infohash)

            if not title or not desc_link:
                continue

            results.append({
                "link": desc_link,
                "name": title,
                "size": ("%s B" % size_value) if size_value else "-1",
                "seeds": seeds,
                "leech": leech,
                "engine_url": self.site_url,
                "desc_link": desc_link,
                "pub_date": pub_date,
                "_dedupe": infohash or desc_link,
            })

        return results

    def download_torrent(self, info):
        if self.malformed:
            _eprint("C411: malformed c411.json.")
            return
        if not self._has_valid_api_key():
            self._emit_configuration_help()
            return

        torrent_id = self._extract_torrent_id(info)
        if torrent_id is None:
            _eprint("C411: unable to extract torrent id from %r." % info)
            return

        download_url = self._build_api_url([("t", "get"), ("id", torrent_id), ("apikey", self.api_key)])
        print(download_file(download_url))

    def search(self, what, cat="all"):
        if self.malformed:
            _eprint("C411: malformed c411.json.")
            return
        if not self._has_valid_api_key():
            self._emit_configuration_help()
            return

        category = self.supported_categories.get(cat.lower(), "")
        query = unquote_plus(what or "").strip()
        seen = set()
        aggregated = []

        for page_index in range(self.max_pages):
            params = [("t", "search"), ("apikey", self.api_key), ("limit", self.page_size)]
            if query:
                params.append(("q", query))
            if category:
                params.append(("cat", category))
            if page_index:
                params.append(("offset", page_index * self.page_size))

            try:
                payload = self._http_get_raw(self._build_api_url(params))
            except Exception as error:  # pylint: disable=broad-exception-caught
                self._log("Search request failed - %s" % error)
                break

            page_results = self._parse_response(payload)
            if not page_results:
                break

            new_results = 0
            for result in page_results:
                dedupe_key = result.pop("_dedupe", result["desc_link"])
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                aggregated.append(result)
                new_results += 1

            if len(page_results) < self.page_size or new_results == 0:
                break

        aggregated.sort(
            key=lambda result: (
                self._parse_int(result.get("seeds"), -1),
                self._parse_int(result.get("pub_date"), -1),
            ),
            reverse=True,
        )

        for result in aggregated:
            prettyPrinter(result)
