# VERSION: 1.4
"""Academic Torrents engine (e-books, papers, and academic multimedia).

The site's full XML database is downloaded and cached locally (refreshed
daily), so matching happens in-process; only the "all" category is exposed.
"""

import concurrent.futures
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from typing import ClassVar
from urllib import request

from helpers import download_file, retrieve_url
from novaprinter import SearchResults, prettyPrinter

DATABASE_URL = "https://academictorrents.com/database.xml"
home = str(Path.home())
system_paths = {
    "win32": f"{home}/AppData/Roaming",
    "linux": f"{home}/.local/share",
    "darwin": f"{home}/Library/Application Support",
}
cache_path = Path(f"{system_paths[sys.platform]}/qbit_plugins_data/academic_cache.xml")


class academictorrents:
    url = "https://academictorrents.com/"
    name = "AcademicTorrents"
    """Force a full-catalog ("all") search.

    The site's categories are too fine-grained for qBittorrent's category
    list, so only "all" is supported and filtering is done in-process.
    """
    supported_categories: ClassVar[dict[str, str]] = {"all": "0"}

    def __init__(self, output: bool = True) -> None:
        self.output = output
        self.filters: list[str] = []

    def _torrent_filter(self, item: ET.Element) -> bool:
        title: str = (item.findtext("title") or "").lower()
        desc: str = (item.findtext("description") or "").lower()
        for f in self.filters:
            if f in title or f in desc:
                return True
        return False

    def _retrieve_database(self) -> ET.Element:
        folder_path = Path(f"{system_paths[sys.platform]}/qbit_plugins_data")
        if not folder_path.exists():
            folder_path.mkdir()
        self._update_database_cache()
        with open(cache_path, encoding="utf-8") as f:
            lines = f.readlines()[1:]
            return ET.fromstring("".join(lines))

    def _update_database_cache(self) -> None:
        if cache_path.exists():
            current_date = str(date.today())
            with open(cache_path, encoding="utf-8") as f:
                saved_date = f.readline().rstrip()
                if current_date == saved_date:
                    return
        req = request.urlopen(DATABASE_URL)
        db_local_text = req.read().decode("utf-8")
        with open(cache_path, "w", encoding="utf-8") as f:
            f.writelines([f"{date.today()!s}\n", db_local_text])
        req.close()

    def resolve_search_result(self, torrent: ET.Element) -> SearchResults:
        name = torrent.findtext("title") or ""
        size = torrent.findtext("size") or ""
        infohash = torrent.findtext("infohash") or ""
        desc_link = torrent.findtext("link") or ""
        torrent_desc = retrieve_url(f"{desc_link}/tech")
        peer_data = re.search(
            "<tr><td>Mirrors</td><td>(\\d+)\\s*complete,\\s*(\\d+)\\s*downloading",
            torrent_desc,
        )
        seeds = -1
        leech = -1
        if peer_data:
            seeds = int(peer_data.group(1))
            leech = int(peer_data.group(2))
        result: SearchResults = {
            "link": f"{self.url}download/{infohash}.torrent",
            "name": name,
            "size": size,
            "seeds": seeds,
            "leech": leech,
            "engine_url": self.url,
            "desc_link": desc_link,
        }
        added_date_data = re.search("<tr><td>Added</td><td>([^<]+)</td></tr>", torrent_desc)
        if added_date_data:
            date_str = added_date_data.group(1)
            result["pub_date"] = int(datetime.fromisoformat(date_str).timestamp())
        return result

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    def search(self, what: str, cat: str = "all") -> None:
        self.filters = [f.lower() for f in re.split("%20|\\s", str(what))]
        db = self._retrieve_database()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures: list[concurrent.futures.Future[SearchResults]] = []
            for torrent in db.findall("channel/item"):
                if self._torrent_filter(torrent):
                    futures.append(executor.submit(self.resolve_search_result, torrent))
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if self.output:
                    prettyPrinter(result)
