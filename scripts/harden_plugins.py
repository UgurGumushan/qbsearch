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

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugins"
START_MARKER = "# BEGIN GENERATED QBITT SAFETY PREAMBLE"
END_MARKER = "# END GENERATED QBITT SAFETY PREAMBLE"


SAFETY_PREAMBLE = r'''# BEGIN GENERATED QBITT SAFETY PREAMBLE
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


_qbt_retrieve_url = globals().get("_qbt_helper_retrieve_url")


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


# END GENERATED QBITT SAFETY PREAMBLE'''


def _remove_preamble(source: str) -> str:
    start = source.find(START_MARKER)
    if start < 0:
        return source
    end = source.find(END_MARKER, start)
    if end < 0:
        raise ValueError("generated preamble start marker has no end marker")
    end += len(END_MARKER)
    return source[:start].rstrip() + "\n\n" + source[end:].lstrip()


def _alias_retrieve_imports(source: str) -> str:
    lines = []
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
        if "_qbt_helper_retrieve_url" in line and "# noqa" not in line:
            line += "  # noqa: F401"
        lines.append(line)
    return "\n".join(lines) + ("\n" if source.endswith("\n") else "")


def _insert_after_imports(source: str) -> str:
    tree = ast.parse(source)
    import_ends = [
        node.end_lineno
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    # A plugin without top-level imports is not currently present, but keep
    # the fallback safe for future additions.
    line_no = max(import_ends, default=0)
    lines = source.splitlines()
    lines[line_no:line_no] = ["", *SAFETY_PREAMBLE.splitlines(), ""]
    return "\n".join(lines) + "\n"


def render_plugin(source: str) -> str:
    source = _remove_preamble(source)
    source = _alias_retrieve_imports(source)
    source = _insert_after_imports(source)
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
    errors = []
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
                isinstance(keyword, ast.keyword) and keyword.arg == "timeout"
                for keyword in node.keywords
            ):
                errors.append(f"line {node.lineno}: urlopen without timeout")
            if (
                (name == "Thread" or name.endswith("ThreadPoolExecutor"))
                and node.lineno > preamble_line
            ):
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
                function = next(
                    (
                        parent
                        for parent in ast.walk(tree)
                        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and parent.lineno <= node.lineno <= parent.end_lineno
                    ),
                    None,
                )
                function_source = ast.get_source_segment(source, function) if function else ""
                if "MAX_PAGES" not in function_source:
                    errors.append(f"line {node.lineno}: pagination loop lacks MAX_PAGES")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="render the preamble into plugins")
    parser.add_argument("--check", action="store_true", help="audit plugins without editing")
    args = parser.parse_args()
    if not args.write and not args.check:
        parser.error("choose --write or --check")

    failures = []
    for path in sorted(PLUGIN_DIR.glob("*.py")):
        if args.write:
            rendered = render_plugin(path.read_text(encoding="utf-8"))
            path.write_text(rendered, encoding="utf-8")
        failures.extend((path.name, error) for error in audit_plugin(path))

    if failures:
        for name, error in failures:
            print(f"{name}: {error}")
        return 1
    print(f"Audited {len(list(PLUGIN_DIR.glob('*.py')))} plugins successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
