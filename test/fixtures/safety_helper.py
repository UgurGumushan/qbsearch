import importlib.util
import os
import sys
import threading
import time
from collections.abc import Callable, Generator, Iterable, Iterator
from types import ModuleType
from typing import Protocol, TypeVar, cast
from unittest.mock import patch

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


JobResult = TypeVar("JobResult")


class GeneratedHelpers(Protocol):
    HTTP_TIMEOUT: float
    MAX_ATTEMPTS: int
    RETRY_DELAY: float
    MAX_WORKERS: int

    def _qbt_default_workers(self) -> int: ...

    def _qbt_safe_urlopen(self, url: str) -> Response: ...

    def _qbt_run_parallel(
        self,
        worker: Callable[..., JobResult],
        arguments: Iterable[object],
        deadline: float,
    ) -> list[JobResult]: ...

    def _qbt_iter_parallel(
        self,
        worker: Callable[..., JobResult],
        arguments: Iterable[object],
        deadline: float,
        *,
        ordered: bool = False,
    ) -> Iterator[JobResult]: ...

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

with patch.dict(os.environ):
    _ = os.environ.pop("QBSEARCH_MAX_WORKERS", None)
    for cores, expected in [(None, 4), (1, 4), (8, 8), (128, 16)]:
        with patch("os.cpu_count", return_value=cores):
            assert generated._qbt_default_workers() == expected
    for value, expected in [("1", 1), ("8", 8), ("1000", 16), ("0", 1), ("-3", 1)]:
        os.environ["QBSEARCH_MAX_WORKERS"] = value
        assert generated._qbt_default_workers() == expected
    for value in ["", "invalid", "2.5"]:
        os.environ["QBSEARCH_MAX_WORKERS"] = value
        with patch("os.cpu_count", return_value=8):
            assert generated._qbt_default_workers() == 8

generated.MAX_WORKERS = 2
release = threading.Event()
finished = threading.Event()


def uneven_worker(value: int) -> int:
    if value == 1:
        _ = release.wait(5.0)
        finished.set()
    return value


stream = generated._qbt_iter_parallel(uneven_worker, [(0,), (1,)], time.monotonic() + 3.0)
try:
    assert next(stream) == 0
    assert not finished.is_set(), "first result must not wait for the slow job"
finally:
    release.set()
assert list(stream) == [1]

release.clear()
finished.clear()
first_started = threading.Event()
second_finished = threading.Event()
consumed: list[int] = []
ordered_results: list[int] = []


def ordered_jobs() -> Iterator[tuple[int]]:
    for value in range(8):
        consumed.append(value)
        yield (value,)


def ordered_worker(value: int) -> int:
    if value == 0:
        first_started.set()
        _ = release.wait(5.0)
    else:
        second_finished.set()
    return value


def collect_ordered() -> None:
    ordered_results.extend(
        generated._qbt_iter_parallel(
            ordered_worker, ordered_jobs(), time.monotonic() + 4.0, ordered=True
        )
    )


collector = threading.Thread(target=collect_ordered)
collector.start()
try:
    assert first_started.wait(2.0) and second_finished.wait(2.0)
    assert len(consumed) == 2, "ordered buffering must bound speculative work"
finally:
    release.set()
    collector.join(3.0)
assert not collector.is_alive()
assert ordered_results == list(range(8))

release.clear()
consumed.clear()
stream = generated._qbt_iter_parallel(uneven_worker, ordered_jobs(), time.monotonic() + 3.0)
try:
    assert next(stream) == 0
    cast(Generator[int, None, None], stream).close()
    assert consumed == [0, 1], "closing a stream must stop job consumption"
finally:
    release.set()

nested_threads: set[int] = set()
nested_lock = threading.Lock()
nested_barrier = threading.Barrier(2)


def nested_worker(value: int) -> int:
    with nested_lock:
        nested_threads.add(threading.get_ident())
    _ = nested_barrier.wait(2.0)
    return value


def page_worker(page: int) -> list[int]:
    return generated._qbt_run_parallel(
        nested_worker, [(page * 10 + n,) for n in range(3)], time.monotonic() + 3.0
    )


nested_results = generated._qbt_run_parallel(page_worker, [(1,), (2,)], time.monotonic() + 4.0)
assert sorted(item for page in nested_results for item in page) == [10, 11, 12, 20, 21, 22]
assert len(nested_threads) == 2, "nested details must reuse their page worker"

release.clear()
try:
    partial = list(
        generated._qbt_iter_parallel(
            ordered_worker, [(0,), (1,)], time.monotonic() + 0.2, ordered=True
        )
    )
    assert partial == [1], "a slow earlier job must not discard completed work at the deadline"
finally:
    release.set()

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
