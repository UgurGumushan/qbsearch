from collections.abc import Mapping
from ssl import SSLContext

_headers: dict[str, str]

def enable_socks_proxy(enable: bool) -> None: ...
def htmlentitydecode(s: str) -> str: ...
def retrieve_url(
    url: str,
    custom_headers: Mapping[str, str] = ...,
    request_data: object | None = None,
    ssl_context: SSLContext | None = None,
    unescape_html_entities: bool = True,
) -> str: ...
def download_file(
    url: str,
    referer: str | None = None,
    ssl_context: SSLContext | None = None,
) -> str: ...
