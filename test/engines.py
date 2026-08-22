#!/usr/bin/env python3
"""Command adapter for the qBittorrent installability harness."""

import sys
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
main = cast(Callable[[], int], import_module("test.engine_harness").main)


if __name__ == "__main__":
    raise SystemExit(main())
