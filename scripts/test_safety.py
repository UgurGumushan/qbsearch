#!/usr/bin/env python3
"""Deterministic tests for the generated standalone request/worker helpers."""

from __future__ import annotations

import importlib.util
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import import_module
from importlib.machinery import SourceFileLoader
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Callable, ClassVar, Protocol, TypedDict, cast

if TYPE_CHECKING:
    from typing_extensions import override
else:

    def override(function: Callable[..., object]) -> Callable[..., object]:
        return function


class _Response(Protocol):
    def read(self) -> bytes: ...


class _ResponseContext(Protocol):
    def __enter__(self) -> _Response: ...

    def __exit__(self, *args: object) -> bool: ...


class _Checker(Protocol):
    PLUGIN_DIR: Path

    def audit_plugin(self, path: Path) -> list[str]: ...


class _HelperNamespace(TypedDict):
    _qbt_safe_urlopen: Callable[[str], _ResponseContext]
    retrieve_url: Callable[[str], str]
    _qbt_run_parallel: Callable[[Callable[[str], str], list[tuple[str]], float], list[str]]


class _Handler(BaseHTTPRequestHandler):
    counts: ClassVar[dict[str, int]] = {}

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        self.counts[path] = self.counts.get(path, 0) + 1
        if path == "/slow":
            time.sleep(0.2)
            body = b"late"
            status = 200
        elif path == "/retry" and self.counts[path] < 3:
            body = b"busy"
            status = 503
        elif path == "/permanent":
            body = b"missing"
            status = 404
        else:
            body = b"ok"
            status = 200
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            _ = self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    @override
    def log_message(self, format: str, *args: object) -> None:
        return None


def _load_helpers() -> tuple[_HelperNamespace, list[int]]:
    module = import_module("harden_plugins")
    safety_preamble = cast(str, module.SAFETY_PREAMBLE)
    calls: list[int] = []

    def helper(*_args: object, **_kwargs: object) -> str:
        calls.append(1)
        return "" if len(calls) < 3 else "ok"

    with TemporaryDirectory() as directory:
        preamble_path = Path(directory) / "generated_helpers.py"
        _ = preamble_path.write_text(
            "from __future__ import annotations\n\n" + safety_preamble,
            encoding="utf-8",
        )
        loader = SourceFileLoader("_qbt_safety_test", str(preamble_path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        if spec is None or spec.loader is None:
            raise RuntimeError("could not load generated safety preamble")
        generated_module = importlib.util.module_from_spec(spec)

        def ignore_result(_result: object) -> None:
            return None

        generated_module.__dict__.update(
            {
                "_qbt_helper_retrieve_url": helper,
                "prettyPrinter": ignore_result,
            }
        )
        loader.exec_module(generated_module)
        namespace = cast(dict[str, object], vars(generated_module))
    namespace.update({"HTTP_TIMEOUT": 0.05, "MAX_ATTEMPTS": 3, "RETRY_DELAY": 0.01})
    helpers = _HelperNamespace(
        _qbt_safe_urlopen=cast(Callable[[str], _ResponseContext], namespace["_qbt_safe_urlopen"]),
        retrieve_url=cast(Callable[[str], str], namespace["retrieve_url"]),
        _qbt_run_parallel=cast(
            Callable[[Callable[[str], str], list[tuple[str]], float], list[str]],
            namespace["_qbt_run_parallel"],
        ),
    )
    return helpers, calls


def main() -> None:
    checker = cast(_Checker, cast(object, import_module("harden_plugins")))
    plugin_paths = sorted(checker.PLUGIN_DIR.glob("*.py"))
    assert len(plugin_paths) == 61
    for plugin_path in plugin_paths:
        assert checker.audit_plugin(plugin_path) == []

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    helpers, helper_calls = _load_helpers()
    try:
        with helpers["_qbt_safe_urlopen"](base + "/ok") as response:
            assert response.read() == b"ok"
        assert _Handler.counts["/ok"] == 1

        started = time.monotonic()
        with helpers["_qbt_safe_urlopen"](base + "/slow") as response:
            assert response.read() == b""
        assert time.monotonic() - started < 0.5
        assert _Handler.counts["/slow"] == 3

        with helpers["_qbt_safe_urlopen"](base + "/retry") as response:
            assert response.read() == b"ok"
        assert _Handler.counts["/retry"] == 3

        with helpers["_qbt_safe_urlopen"](base + "/permanent") as response:
            assert response.read() == b""
        assert _Handler.counts["/permanent"] == 1

        assert helpers["retrieve_url"]("ignored") == "ok"
        assert len(helper_calls) == 3

        def worker(value: str) -> str:
            if value == "bad":
                raise RuntimeError("one worker failed")
            return value

        results = helpers["_qbt_run_parallel"](
            worker,
            [("first",), ("bad",), ("second",)],
            time.monotonic() + 1.0,
        )
        assert set(results) == {"first", "second"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1.0)
    print("Safety helper tests passed.")


if __name__ == "__main__":
    main()
