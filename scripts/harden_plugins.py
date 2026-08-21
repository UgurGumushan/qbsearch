#!/usr/bin/env python3
"""Generate and audit the standalone qBittorrent plugin safety preamble.

The engines are copied into qBittorrent one file at a time, so the runtime
helpers in this file are deliberately rendered into every plugin rather than
imported from a repository module.  Use ``--write`` after changing the
template; ``--check`` is suitable for CI and never edits a plugin.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import NamedTuple, cast

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugins"
START_MARKER = "# BEGIN GENERATED QBITT SAFETY PREAMBLE"
END_MARKER = "# END GENERATED QBITT SAFETY PREAMBLE"
_HTML_PARSER_OVERRIDES = {
    "handle_comment",
    "handle_decl",
    "handle_data",
    "handle_endtag",
    "handle_entityref",
    "handle_startendtag",
    "handle_starttag",
}


class Arguments(NamedTuple):
    write: bool
    check: bool


SAFETY_PREAMBLE = r'''# BEGIN GENERATED QBITT SAFETY PREAMBLE
# This block is rendered into each standalone engine.  Keep it stdlib-only.
try:
    import socket as _qbt_socket
    import time as _qbt_time
    import urllib.error as _qbt_urllib_error
    from collections.abc import Iterable as _QBTIterable
    from concurrent.futures import Future as _QBTFuture
    from concurrent.futures import ThreadPoolExecutor as _QBTThreadPoolExecutor
    from concurrent.futures import TimeoutError as _qbt_FuturesTimeoutError
    from concurrent.futures import as_completed as _qbt_as_completed
    from threading import Lock as _qbt_Lock
    from types import TracebackType as _QBTTracebackType
    from typing import Callable as _QBTCallable
    from typing import Protocol as _QBTProtocol
    from typing import TypeVar as _QBTTypeVar
    from typing import cast as _qbt_cast
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
_qbt_search_deadline: float | None = None
_QBTJobResult = _QBTTypeVar("_QBTJobResult")


class _QBTResponse(_QBTProtocol):
    status: int | None

    def close(self) -> None: ...

    def read(self, *args: object, **kwargs: object) -> bytes: ...

    def getcode(self) -> int: ...

    def geturl(self) -> str: ...

    def getheader(self, name: str, default: object = None) -> object: ...

    def info(self) -> _QBTResponse: ...

    def get(self, name: str, default: object = None) -> object: ...


class _QBTResponseContext(_QBTResponse, _QBTProtocol):
    def __enter__(self) -> _QBTResponse: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: _QBTTracebackType | None,
    ) -> bool: ...


_qbt_urlopen_typed = _qbt_cast(_QBTCallable[..., _QBTResponseContext], _qbt_urlopen)


class _QBTEmptyResponse:
    """Response-shaped empty value used when a request is exhausted."""

    status: int | None = 200
    code: int = 200
    _url: str

    def __init__(self, url: object = "") -> None:
        self._url = str(getattr(url, "full_url", url))

    def __enter__(self) -> _QBTResponse:
        return _qbt_cast(_QBTResponse, _qbt_cast(object, self))

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: _QBTTracebackType | None,
    ) -> bool:
        self.close()
        return False

    def close(self) -> None:
        return None

    def read(self, *_args: object, **_kwargs: object) -> bytes:
        return b""

    def getcode(self) -> int:
        return self.code

    def geturl(self) -> str:
        return self._url

    def getheader(self, _name: str, default: object = None) -> object:
        return default

    def info(self) -> _QBTResponse:
        return _qbt_cast(_QBTResponse, _qbt_cast(object, self))

    def get(self, _name: str, default: object = None) -> object:
        return default


def _qbt_empty_response(url: object) -> _QBTResponseContext:
    return _qbt_cast(_QBTResponseContext, _qbt_cast(object, _QBTEmptyResponse(url)))


class _QBTTransientHTTPError(Exception):
    pass


def _qbt_sleep(attempt: int) -> None:
    _qbt_time.sleep(min(max(RETRY_DELAY, 0.0) * (attempt + 1), 1.0))


def _qbt_retry_call(operation: _QBTCallable[[], object]) -> str:
    """Run a helper request a bounded number of times and return empty data."""
    for attempt in range(max(1, int(MAX_ATTEMPTS))):
        if _qbt_time.monotonic() >= _qbt_get_deadline():
            return ""
        try:
            result: object = operation()
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


def _qbt_safe_urlopen(
    url: object,
    data: object | None = None,
    *,
    context: object | None = None,
) -> _QBTResponseContext:
    """Open a URL with explicit timeout/retry policy and an empty fallback."""
    attempts = max(1, int(MAX_ATTEMPTS))
    for attempt in range(attempts):
        remaining = _qbt_get_deadline() - _qbt_time.monotonic()
        if remaining <= 0:
            return _qbt_empty_response(url)
        response: _QBTResponseContext | None = None
        try:
            request_timeout = min(float(HTTP_TIMEOUT), remaining)
            if context is None:
                response = _qbt_urlopen_typed(url, data=data, timeout=request_timeout)
            else:
                response = _qbt_urlopen_typed(
                    url, data=data, timeout=request_timeout, context=context
                )
            status = response.status
            if status is None:
                status = response.getcode()
            if status in _QBT_RETRYABLE_HTTP_STATUS:
                response.close()
                response = None
                raise _QBTTransientHTTPError(status)
            if status >= 400:
                response.close()
                return _qbt_empty_response(url)
            return response
        except _qbt_urllib_error.HTTPError as error:
            if error.code not in _QBT_RETRYABLE_HTTP_STATUS:
                try:
                    error.close()
                except Exception:
                    pass
                return _qbt_empty_response(url)
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
            return _qbt_empty_response(url)
        if attempt + 1 < attempts:
            _qbt_sleep(attempt)
    return _qbt_empty_response(url)


_qbt_retrieve_url = _qbt_cast(_QBTCallable[..., object], _qbt_helper_retrieve_url)


def retrieve_url(*args: object, **kwargs: object) -> str:
    """Drop-in wrapper for qBittorrent's helper with bounded retries."""
    helper = _qbt_retrieve_url
    if not callable(helper):
        return ""
    return _qbt_retry_call(lambda: helper(*args, **kwargs))


_qbt_output_lock = _qbt_Lock()


def _qbt_prettyPrinter(result: object) -> None:
    """Serialize result records emitted by parallel workers."""
    with _qbt_output_lock:
        printer = _qbt_cast(_QBTCallable[[object], None], prettyPrinter)
        printer(result)


def _qbt_run_parallel(
    worker: _QBTCallable[..., _QBTJobResult],
    jobs: _QBTIterable[object],
    deadline: float | None = None,
) -> list[_QBTJobResult]:
    """Run bounded worker jobs, preserving completed work after failures."""
    jobs = list(jobs)
    if not jobs:
        return []
    if deadline is None:
        deadline = _qbt_get_deadline()
    executor = _QBTThreadPoolExecutor(max_workers=MAX_WORKERS)
    futures: list[_QBTFuture[_QBTJobResult]] = []
    for job in jobs:
        if isinstance(job, tuple):
            futures.append(executor.submit(worker, *job))
        else:
            futures.append(executor.submit(worker, job))
    results: list[_QBTJobResult] = []
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
            _ = future.cancel()
    finally:
        try:
            _ = executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # pragma: no cover - compatibility with old qBitt Python
            _ = executor.shutdown(wait=False)
    return results


def _qbt_new_deadline() -> float:
    return _qbt_get_deadline()


def _qbt_get_deadline() -> float:
    global _qbt_search_deadline
    if _qbt_search_deadline is None:
        _qbt_search_deadline = _qbt_time.monotonic() + max(0.0, float(SEARCH_DEADLINE))
    return _qbt_search_deadline


# These hooks are available to standalone engines even when a particular
# engine does not call every optional adapter directly.
__all__ = [
    "_qbt_new_deadline",
    "_qbt_prettyPrinter",
    "_qbt_run_parallel",
    "_qbt_safe_urlopen",
    "retrieve_url",
]


# END GENERATED QBITT SAFETY PREAMBLE'''

OVERRIDE_SUPPORT = r"""if TYPE_CHECKING:
    from typing_extensions import override
else:

    def override(function: _QBTCallable[..., object]) -> _QBTCallable[..., object]:
        return function
"""


def _remove_preamble(source: str) -> str:
    start = source.find(START_MARKER)
    if start < 0:
        return source
    end = source.find(END_MARKER, start)
    if end < 0:
        raise ValueError("generated preamble start marker has no end marker")
    end += len(END_MARKER)
    return source[:start].rstrip() + "\n\n" + source[end:].lstrip()


def _ensure_future_annotations(source: str) -> str:
    tree = ast.parse(source)
    if any(
        isinstance(node, ast.ImportFrom)
        and node.module == "__future__"
        and any(alias.name == "annotations" for alias in node.names)
        for node in tree.body
    ):
        return source

    lines = source.splitlines()
    insert_line = 0
    while insert_line < len(lines) and (
        lines[insert_line].startswith("#!") or re.match(r"^#.*coding[:=]", lines[insert_line])
    ):
        insert_line += 1
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        insert_line = tree.body[0].end_lineno or insert_line
    prefix = [""] if insert_line and lines[insert_line - 1].strip() else []
    suffix = [""] if insert_line == len(lines) or lines[insert_line].strip() else []
    lines[insert_line:insert_line] = [
        *prefix,
        "from __future__ import annotations",
        *suffix,
    ]
    return "\n".join(lines) + "\n"


def _alias_retrieve_imports(source: str) -> str:
    lines: list[str] = []
    for line in source.splitlines():
        if "retrieve_url as _qbt_retrieve_url" in line:
            line = line.replace(
                "retrieve_url as _qbt_retrieve_url",
                "retrieve_url as _qbt_helper_retrieve_url",
            )
        elif (
            line.startswith("from helpers import ")
            and "retrieve_url" in line
            and "retrieve_url as _qbt_helper_retrieve_url" not in line
        ):
            line = re.sub(
                r"\bretrieve_url\b",
                "retrieve_url as _qbt_helper_retrieve_url",
                line,
                count=1,
            )
        if "retrieve_url as _qbt_helper_retrieve_url" in line:
            line = line.replace("  # noqa: F401", "")
        lines.append(line)
    return "\n".join(lines) + ("\n" if source.endswith("\n") else "")


def _insert_after_imports(source: str, include_override: bool) -> str:
    tree = ast.parse(source)
    import_ends: list[int] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)) and node.end_lineno is not None:
            import_ends.append(node.end_lineno)
    # A plugin without top-level imports is not currently present, but keep
    # the fallback safe for future additions.
    line_no = max(import_ends, default=0)
    lines = source.splitlines()
    helper_fallback = (
        []
        if "retrieve_url as _qbt_helper_retrieve_url" in source
        else ["_qbt_helper_retrieve_url = None"]
    )
    preamble = SAFETY_PREAMBLE
    if include_override:
        preamble = preamble.replace(
            "    from typing import Callable as _QBTCallable\n",
            "    from typing import TYPE_CHECKING\n"
            + "    from typing import Callable as _QBTCallable\n",
        )
        preamble = preamble.replace(
            'except ImportError as error:\n    raise RuntimeError("qBittorrent safety preamble requires Python stdlib") from error\n',
            "except ImportError as error:\n"
            + '    raise RuntimeError("qBittorrent safety preamble requires Python stdlib") from error\n\n'
            + OVERRIDE_SUPPORT
            + "\n",
        )
    lines[line_no:line_no] = ["", *helper_fallback, *preamble.splitlines(), ""]
    return "\n".join(lines) + "\n"


def _add_override_decorators(source: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    insertions: list[tuple[int, str]] = []

    for class_node in ast.walk(tree):
        if not isinstance(class_node, ast.ClassDef):
            continue
        is_html_parser = any(
            isinstance(base, ast.Name) and base.id == "HTMLParser" for base in class_node.bases
        )
        for child in class_node.body:
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if child.name != "__repr__" and not (
                is_html_parser and child.name in _HTML_PARSER_OVERRIDES
            ):
                continue
            if any(
                isinstance(decorator, ast.Name) and decorator.id in {"override", "_qbt_override"}
                for decorator in child.decorator_list
            ):
                continue
            first_line = min(
                [child.lineno, *(decorator.lineno for decorator in child.decorator_list)]
            )
            insertions.append((first_line - 1, " " * child.col_offset + "@override"))

    for line_no, decorator in reversed(insertions):
        lines.insert(line_no, decorator)
    return "\n".join(lines) + ("\n" if source.endswith("\n") else "")


def render_plugin(source: str) -> str:
    source = _remove_preamble(source)
    source = _ensure_future_annotations(source)
    source = _alias_retrieve_imports(source)
    source = _add_override_decorators(source)
    source = _insert_after_imports(source, "@override\n" in source)
    # All result writes go through the generated lock, including engines that
    # are later changed from raw threads to the shared bounded runner.
    before, marker, after = source.partition(END_MARKER)
    if not marker:
        raise ValueError("preamble insertion failed")
    after = re.sub(r"(?:_qbt_)*prettyPrinter\(", "_qbt_prettyPrinter(", after)
    return before + marker + after


def _call_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def audit_plugin(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    errors: list[str] = []
    if START_MARKER not in source or END_MARKER not in source:
        errors.append("missing generated safety preamble")
    for constant in ("HTTP_TIMEOUT", "MAX_ATTEMPTS", "RETRY_DELAY", "MAX_WORKERS"):
        if not re.search(rf"^\s*{constant}\s*=", source, re.MULTILINE):
            errors.append(f"missing {constant}")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as error:
        return errors + [f"syntax error: {error}"]

    preamble_end = source.find(END_MARKER)
    preamble_line = source[:preamble_end].count("\n") + 1
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in {"urlopen", "_qbt_urlopen"} and not any(
                keyword.arg == "timeout" for keyword in node.keywords
            ):
                errors.append(f"line {node.lineno}: urlopen without timeout")
            if (
                name == "Thread" or name.endswith("ThreadPoolExecutor")
            ) and node.lineno > preamble_line:
                if name == "Thread":
                    errors.append(f"line {node.lineno}: raw thread creation")
                elif not any(k.arg == "max_workers" for k in node.keywords):
                    errors.append(f"line {node.lineno}: executor without max_workers")
        if (
            isinstance(node, ast.While)
            and node.lineno > preamble_line
            and isinstance(node.test, ast.Constant)
            and node.test.value is True
        ):
            errors.append(f"line {node.lineno}: unbounded while True")
        if isinstance(node, ast.While) and node.lineno > preamble_line:
            test_names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
            if test_names.intersection({"page", "pages", "lastPage", "total_results"}):
                function: ast.FunctionDef | ast.AsyncFunctionDef | None = next(
                    (
                        parent
                        for parent in ast.walk(tree)
                        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and parent.end_lineno is not None
                        and parent.lineno <= node.lineno <= parent.end_lineno
                    ),
                    None,
                )
                function_source = (
                    (ast.get_source_segment(source, function) or "") if function else ""
                )
                if "MAX_PAGES" not in function_source:
                    errors.append(f"line {node.lineno}: pagination loop lacks MAX_PAGES")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--write", action="store_true", help="render the preamble into plugins")
    _ = parser.add_argument("--check", action="store_true", help="audit plugins without editing")
    parsed = parser.parse_args()
    args = Arguments(write=cast(bool, parsed.write), check=cast(bool, parsed.check))
    if not args.write and not args.check:
        parser.error("choose --write or --check")

    failures: list[tuple[str, str]] = []
    for path in sorted(PLUGIN_DIR.glob("*.py")):
        if args.write:
            rendered = render_plugin(path.read_text(encoding="utf-8"))
            _ = path.write_text(rendered, encoding="utf-8")
        failures.extend((path.name, error) for error in audit_plugin(path))

    if failures:
        for name, error in failures:
            print(f"{name}: {error}")
        return 1
    print(f"Audited {len(list(PLUGIN_DIR.glob('*.py')))} plugins successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
