from typing import TypedDict
from typing_extensions import NotRequired

class SearchResults(TypedDict):
    link: str
    name: str
    size: float | int | str
    seeds: int
    leech: int
    engine_url: str
    # Mirrors nova3/novaprinter.py: qBitt's prettyPrinter resolves these via
    # .get(...), i.e. they are genuinely optional per the engine contract.
    desc_link: NotRequired[str]
    pub_date: NotRequired[int]

def prettyPrinter(dictionary: SearchResults) -> None: ...
def anySizeToBytes(size_string: float | str) -> int: ...
