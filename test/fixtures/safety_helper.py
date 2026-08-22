import importlib.util
import sys
import time
from collections.abc import Callable
from types import ModuleType
from typing import Protocol, cast

# The fixture intentionally loads a generated module through importlib's
# dynamic loader API, whose Python 3.9 types are incomplete.
# pyright: reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownArgumentType=false


class Response(Protocol):
    def __enter__(self) -> "Response": ...  # noqa: PYI034

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None: ...

    def read(self) -> bytes: ...


class GeneratedHelpers(Protocol):
    HTTP_TIMEOUT: float
    MAX_ATTEMPTS: int
    RETRY_DELAY: float

    def _qbt_safe_urlopen(self, url: str) -> Response: ...

    def _qbt_run_parallel(
        self,
        worker: Callable[[str], str],
        arguments: list[tuple[str]],
        deadline: float,
    ) -> list[str]: ...

    def retrieve_url(self, url: str) -> str: ...


class ModuleLoader(Protocol):
    def exec_module(self, module: ModuleType) -> None: ...


helper_path, base_url = sys.argv[1:]
spec = importlib.util.spec_from_file_location("generated_helpers", helper_path)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load generated safety preamble")
module = importlib.util.module_from_spec(spec)
calls: list[int] = []


def helper(*_args: object, **_kwargs: object) -> str:
    calls.append(1)
    return "" if len(calls) < 3 else "ok"


def ignore_result(_result: object) -> None:
    return None


module.__dict__.update(
    {
        "_qbt_helper_retrieve_url": helper,
        "prettyPrinter": ignore_result,
    }
)
cast(ModuleLoader, cast(object, spec.loader)).exec_module(module)
generated = cast(GeneratedHelpers, cast(object, module))
generated.HTTP_TIMEOUT = 0.05
generated.MAX_ATTEMPTS = 3
generated.RETRY_DELAY = 0.01

with generated._qbt_safe_urlopen(base_url + "/ok") as response:
    assert response.read() == b"ok"

started = time.monotonic()
with generated._qbt_safe_urlopen(base_url + "/slow") as response:
    assert response.read() == b""
assert time.monotonic() - started < 0.5

with generated._qbt_safe_urlopen(base_url + "/retry") as response:
    assert response.read() == b"ok"

with generated._qbt_safe_urlopen(base_url + "/permanent") as response:
    assert response.read() == b""

assert generated.retrieve_url("ignored") == "ok"
assert len(calls) == 3


def worker(value: str) -> str:
    if value == "bad":
        raise RuntimeError("one worker failed")
    return value


results = generated._qbt_run_parallel(
    worker,
    [("first",), ("bad",), ("second",)],
    time.monotonic() + 1.0,
)
assert set(results) == {"first", "second"}
print("Safety helper tests passed.")
