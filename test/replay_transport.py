"""Fixture HTTP transport for offline standalone-engine replay."""

from __future__ import annotations

import base64
import io
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from email.message import Message
from threading import Lock
from types import TracebackType
from typing import cast, final


def object_record(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    values = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in values):
        raise TypeError(f"{label} keys must be strings")
    return cast(dict[str, object], value)


def string_map(value: object, label: str) -> dict[str, str]:
    values = object_record(value, label)
    if not all(isinstance(item, str) for item in values.values()):
        raise TypeError(f"{label} values must be strings")
    return cast(dict[str, str], values)


@dataclass(frozen=True)
class Reply:
    body: bytes
    status: int = 200
    final_url: str = ""
    headers: Mapping[str, str] | None = None
    delay_ms: int | None = None


def parse_reply(value: object) -> Reply:
    if isinstance(value, str):
        return Reply(value.encode())
    fields = object_record(value, "response")
    body = fields.get("body", "")
    encoded = fields.get("bodyBase64")
    if not isinstance(body, str) or (encoded is not None and not isinstance(encoded, str)):
        raise TypeError("response body must be text or bodyBase64")
    status = fields.get("status", 200)
    delay = fields.get("delayMs")
    final_url = fields.get("finalUrl", "")
    if (
        not isinstance(status, int)
        or isinstance(status, bool)
        or not 100 <= status <= 599
        or not isinstance(final_url, str)
    ):
        raise ValueError("invalid fixture response status or finalUrl")
    if delay is not None and (
        not isinstance(delay, int) or isinstance(delay, bool) or not 0 <= delay <= 1000
    ):
        raise ValueError("invalid fixture response delayMs")
    headers = string_map(fields.get("headers", {}), "response headers")
    return Reply(
        base64.b64decode(encoded, validate=True) if isinstance(encoded, str) else body.encode(),
        status,
        final_url,
        headers,
        delay,
    )


@final
class FixtureResponse:
    def __init__(self, reply: Reply, url: str, transport: FixtureTransport) -> None:
        self.status: int = reply.status
        self.code: int = reply.status
        self.headers: Message = Message()
        for name, value in (reply.headers or {}).items():
            self.headers[name] = value
        self._url = reply.final_url or url
        self._body = io.BytesIO(reply.body)
        self._length = len(reply.body)
        self._transport = transport
        self._closed = False

    def __enter__(self) -> FixtureResponse:
        return self

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.close()

    def read(self, size: int = -1) -> bytes:
        if self._closed:
            return b""
        data = self._body.read(size)
        self._transport.add_bytes(len(data))
        if self._body.tell() == self._length:
            self.close()
        return data

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self._url

    def info(self) -> Message:
        return self.headers

    def getheader(self, name: str, default: str | None = None) -> str | None:
        return self.headers.get(name, default)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._body.close()
            self._transport.finish()


@final
class FixtureTransport:
    def __init__(self, case: dict[str, object], errors: list[str]) -> None:
        self.responses = {
            url: parse_reply(value)
            for url, value in object_record(case.get("responses", {}), "responses").items()
        }
        self.exchanges: dict[tuple[str, str, bytes], Reply] = {}
        raw_exchanges = case.get("exchanges", [])
        if not isinstance(raw_exchanges, list):
            raise TypeError("exchanges must be a list")
        for raw in cast(list[object], raw_exchanges):
            fields = object_record(raw, "exchange")
            url, method, body = (
                fields.get("url"),
                fields.get("method", "GET"),
                fields.get("data", ""),
            )
            if (
                not isinstance(url, str)
                or method not in ("GET", "POST")
                or not isinstance(body, str)
            ):
                raise ValueError("exchange requires a URL, GET/POST method, and text data")
            key = (str(method), url, body.encode())
            if key in self.exchanges:
                raise ValueError("duplicate fixture exchange")
            self.exchanges[key] = parse_reply(fields.get("response", ""))
        self.default_reply = parse_reply(case["emptyResponse"]) if "emptyResponse" in case else None
        if self.default_reply is not None and case.get("expectEmpty") is not True:
            raise ValueError("emptyResponse is only allowed for an explicitly empty fixture")
        delay = case.get("responseDelayMs", 0)
        if not isinstance(delay, int) or isinstance(delay, bool) or not 0 <= delay <= 1000:
            raise ValueError("invalid responseDelayMs")
        self.delay_ms: int = delay
        self.errors = errors
        self.requests: list[str] = []
        self.request_details: list[dict[str, object]] = []
        self.request_concurrency: list[int] = []
        self.active = 0
        self.peak = 0
        self.response_bytes = 0
        self.lock = Lock()

    def add_bytes(self, size: int) -> None:
        with self.lock:
            self.response_bytes += size

    def finish(self) -> None:
        with self.lock:
            self.active -= 1

    def _start(
        self, url: str, data: bytes | None, headers: Mapping[str, str], method: str | None = None
    ) -> Reply:
        method = method or ("POST" if data is not None else "GET")
        body = data.decode("utf-8", errors="replace") if data is not None else ""
        key = (method, url, data or b"")
        legacy = self.responses.get(url) if method == "GET" and data is None else None
        reply = self.exchanges.get(key) or legacy or self.default_reply
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.requests.append(url)
            self.request_concurrency.append(self.active)
            self.request_details.append(
                {
                    "url": url,
                    "method": method,
                    "data": body,
                    "headers": dict(headers),
                    "status": reply.status if reply else None,
                    "fixtureBytes": len(reply.body) if reply else 0,
                    "finalUrl": (reply.final_url or url) if reply else url,
                }
            )
            if reply is None:
                description = url if method == "GET" else f"POST {url} {body}".rstrip()
                self.errors.append(f"unexpected request: {description}")
        if reply is None:
            reply = Reply(b"")
        delay = self.delay_ms if reply.delay_ms is None else reply.delay_ms
        if delay:
            time.sleep(delay / 1000)
        return reply

    def urlopen(
        self,
        url: str | urllib.request.Request,
        data: bytes | None = None,
        **_kwargs: object,
    ) -> FixtureResponse:
        headers: dict[str, str] = {}
        method: str | None = None
        target = url
        if isinstance(url, urllib.request.Request):
            target = url.full_url
            if data is None:
                raw_data = cast(object, url.data)
                if raw_data is not None and not isinstance(raw_data, bytes):
                    raise TypeError("fixture request data must be bytes")
                data = raw_data
            headers = dict(url.header_items())
            explicit_method = cast(object, getattr(url, "method", None))
            method = explicit_method if isinstance(explicit_method, str) else None
        if not isinstance(target, str):
            raise TypeError("fixture request URL must be text")
        reply = self._start(target, data, headers, method)
        key = (
            method or ("POST" if data is not None else "GET"),
            target,
            data or b"",
        )
        legacy = target in self.responses and key[0] == "GET" and data is None
        if key not in self.exchanges and not legacy and self.default_reply is None:
            self.finish()
            raise RuntimeError("unexpected fixture HTTP request")
        response = FixtureResponse(reply, target, self)
        if reply.status >= 400:
            response.close()
            raise urllib.error.HTTPError(
                target, reply.status, "fixture HTTP error", response.headers, io.BytesIO(reply.body)
            )
        return response

    def retrieve(
        self,
        url: str,
        custom_headers: Mapping[str, str] | None = None,
        request_data: bytes | None = None,
        *_args: object,
        **_kwargs: object,
    ) -> str:
        reply = self._start(url, request_data, custom_headers or {})
        try:
            if reply.status >= 400:
                raise urllib.error.HTTPError(
                    url, reply.status, "fixture HTTP error", Message(), None
                )
            self.add_bytes(len(reply.body))
            return reply.body.decode("utf-8")
        finally:
            self.finish()
