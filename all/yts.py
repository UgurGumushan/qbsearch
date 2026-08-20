# VERSION: 1.9
# AUTHORS: Lyra Aranha (lyra@lazulyra.com)

import dataclasses
import json
import re
from urllib.parse import urlencode, unquote
from helpers import retrieve_url
from novaprinter import prettyPrinter


# https://stackoverflow.com/a/78110564
def filter_unexpected_fields(cls):
    original_init = cls.__init__

    def new_init(self, *args, **kwargs):
        expected_fields = {field.name for field in dataclasses.fields(cls)}
        cleaned_kwargs = {
            key: value for key, value in kwargs.items() if key in expected_fields
        }
        original_init(self, *args, **cleaned_kwargs)

    cls.__init__ = new_init
    return cls


@filter_unexpected_fields
@dataclasses.dataclass
class yts_torrent:
    url: str
    seeds: int
    peers: int
    size_bytes: int
    hash: str | None = None
    size: str | None = None
    quality: str | None = None
    type: str | None = None
    is_repack: str | None = None
    video_codec: str | None = None
    date_uploaded: str | None = None
    date_uploaded_unix: int | None = None
    bit_depth: str | None = None
    audio_channels: str | None = None


@filter_unexpected_fields
@dataclasses.dataclass
class yts_movie:
    id: int
    url: str
    title: str
    title_long: str | None = None
    slug: str | None = None
    year: int | None = None
    genres: list[str] | None = None
    language: str | None = None
    torrents: list[yts_torrent] | None = None
    date_uploaded: str | None = None
    date_uploaded_unix: int | None = None

    def __post_init__(self):
        self.torrents = self.torrents and [yts_torrent(**torrent) for torrent in self.torrents]


@filter_unexpected_fields
@dataclasses.dataclass
class yts_data:
    movie_count: int
    limit: int
    page_number: int
    movies: list[yts_movie] | None = None

    def __post_init__(self):
        self.movies = self.movies and [yts_movie(**movie) for movie in self.movies]


@filter_unexpected_fields
@dataclasses.dataclass
class yts_response:
    status: str
    status_message: str
    data: yts_data

    def __post_init__(self):
        self.data = yts_data(**self.data)


class yts(object):
    """
    `url`, `name`, `supported_categories` should be static variables of the engine_name class,
     otherwise qbt won't install the plugin.

    `url`: The URL of the search engine.
    `name`: The name of the search engine, spaces and special characters are allowed here.
    `supported_categories`: What categories are supported by the search engine and their corresponding id,
    possible categories are ('all', 'anime', 'books', 'games', 'movies', 'music', 'pictures', 'software', 'tv').
    """

    url = "https://yts.bz/"
    api_url = " https://movies-api.accel.li/api/v2/list_movies.json?"
    name = "YTS"
    supported_categories = {"all": "0", "movies": "1"}

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what: str, cat: str = "all"):
        """
        Searches YTS' API for `what`.

        Automatically parses rating, codec, and quality from `what`.

        @param `what`: a string with the search tokens, already escaped (e.g. "Ubuntu+Linux")
        @param `cat`: the name of a search category in ('all', 'anime', 'books', 'games', 'movies', 'music', 'pictures', 'software', 'tv')
        """
        search_url = self.api_url

        what = unquote(what)
        search_params = {}

        # quality tagging
        quality_rstring = r"(?:quality=)?((?:2160|1440|1080|720|480|240)p|3D)"
        quality_re = re.search(quality_rstring, what)
        search_resolution = None
        if quality_re:
            search_resolution = quality_re.group(1)
            search_params["quality"] = search_resolution
            what = re.sub(quality_rstring, "", what).strip()

        # codec tagging
        # YTS only provides h264/h265 at time of writing
        codec_rstring = r"(?:x|h)(264|265)"
        codec_re = re.search(codec_rstring, what)
        search_codec = None
        if codec_re:
            search_codec = "x" + codec_re.group(1)
            # only add if quality also defined, will be checked separately anyways
            if "quality" in search_params:
                search_params["quality"] += f".{search_codec}"
            what = re.sub(codec_rstring, "", what).strip()

        # rating tagging
        rating_rstring = r"(?:min(?:imum)?_)?rating=(\d)"
        rating_re = re.search(rating_rstring, what)
        if rating_re:
            min_rating = rating_re.group(1)
            search_params["minimum_rating"] = min_rating
            what = re.sub(rating_rstring, "", what).strip()

        # genre tagging
        genre_rstring = r"genre=(\w+)"
        genre_re = re.search(genre_rstring, what)
        if genre_re:
            genre = genre_re.group(1)
            what = re.sub(genre_rstring, "", what).strip()
            search_params["genre"] = genre

        # prevent user causing page errors
        search_rstring = r"&page=\d+"
        what = re.sub(search_rstring, "", what).strip()

        # url finalisation
        if what:
            search_params["query_term"] = what

        search_url += urlencode(search_params)

        try:
            response_raw = retrieve_url(search_url)
            response_json = json.loads(response_raw)
            api_result = yts_response(**response_json)
        except Exception as e:
            print(f"Error parsing YTS response: {e}")
            return

        if api_result.status != "ok":
            print(
                f"Error querying YTS API: {api_result.status}: {api_result.status_message}"
            )
            return
        if not api_result.data or not api_result.data.movies:
            return

        self.process_movies(api_result.data.movies, search_params)
        for page_no in range(
            1, api_result.data.movie_count // api_result.data.limit + 1
        ):
            try:
                api_result = yts_response(
                    **json.loads(retrieve_url(search_url + f"&page={page_no}"))
                )
                self.process_movies(api_result.data.movies, search_params)
            except Exception as e:
                print(f"Error parsing YTS response: {e}")
                return

    def process_movies(self, movies: list[yts_movie], search_params: dict[str, str]):
        if not movies:
            return

        for movie in movies:
            for torrent in movie.torrents:
                if (
                    "search_codec" in search_params
                    and torrent.video_codec != search_params["search_codec"]
                ) or (
                    "search_resolution" in search_params
                    and torrent.quality != search_params["search_resolution"]
                ):
                    continue
                formatTorrent = {
                    "link": torrent.url,
                    "name": f"{movie.title_long or movie.title} {torrent.quality and f'[{torrent.quality}]'} {torrent.video_codec and f'[{torrent.video_codec}]'} {torrent.type and f'[{torrent.type}]'} {torrent.audio_channels and f'[{torrent.audio_channels}]'} [YTS]",
                    "size": torrent.size,
                    "seeds": str(torrent.seeds),
                    "leech": str(torrent.peers),
                    "engine_url": self.url,
                    "desc_link": movie.url,
                    "pub_date": torrent.date_uploaded_unix,
                }
                prettyPrinter(formatTorrent)
