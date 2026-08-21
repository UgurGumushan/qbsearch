#!/usr/bin/env python3
"""Run every qBittorrent plugin test concurrently and report a clear verdict.

By default each plugin is searched against its configured remote service in its
own subprocess.  The coordinator uses one worker per logical CPU by default.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugins"
ENGINE_TEST = ROOT / "test_engines.py"
LIVE_TEST = ROOT / "scripts" / "test_live_plugin.py"
SAFETY_TEST = ROOT / "scripts" / "test_safety.py"

# A single query is a poor smoke test for heterogeneous indexes.  These are
# conservative, read-only queries chosen to match each site's subject area.
# --query overrides the profile for every plugin.
DEFAULT_LIVE_QUERIES = {
    "academictorrents": "machine learning",
    "acgrip": "one piece",
    "ali213": "minecraft",
    "anidex": "one piece",
    "animetosho": "one piece",
    "apachetorrent": "inception",
    "audiobookbay": "the hobbit",
    "bitsearch": "inception",
    "bt4gprx": "ubuntu",
    "btdig": "ubuntu",
    "calidadtorrent": "inception",
    "cloudtorrents": "ubuntu",
    "cpasbien": "inception",
    "darklibria": "the hobbit",
    "divxtotal": "inception",
    "dmhy": "one piece",
    "dodi_repacks": "elden ring",
    "dontorrent": "inception",
    "elitetorrent": "inception",
    "esmeraldatorrent": "inception",
    # EZTV's current API supports IMDb ids; its keyword parameter is ignored.
    "eztvx": "tt0903747",
    "fitgirl_repacks": "elden ring",
    "glotorrents": "inception",
    "goggames": "minecraft",
    "kickasstorrents": "inception",
    "magnetdl": "ubuntu",
    "maxitorrent": "inception",
    "mejortorrent": "inception",
    "mikan": "one piece",
    "mikanani": "one piece",
    "mypornclub": "test",
    "naranjatorrent": "inception",
    "nekobt": "one piece",
    "nyaa_phuong": "one piece",
    "nyaapantsu": "one piece",
    "nyaasi": "one piece",
    "onlinefix": "minecraft",
    "pirateiro": "inception",
    "redetorrent": "inception",
    "rockbox": "ubuntu",
    "rutor": "inception",
    "sktorrent": "inception",
    "smallgames": "minecraft",
    "snowfl": "inception",
    "solidtorrents": "ubuntu",
    "subsplease": "one piece",
    "sukebeisi": "one piece",
    "thepiratebay": "inception",
    "therarbg": "inception",
    "tokyotoshokan": "one piece",
    "tomadivx": "inception",
    "torrent9": "inception",
    "torrentdownload": "inception",
    "torrentdownloads": "inception",
    "torrentgalaxy": "inception",
    "traht": "inception",
    "uniondht": "ubuntu",
    "xxxclubto": "test",
    "yggtracker": "ubuntu",
    "yourbittorrent": "inception",
    "yts": "inception",
}


@dataclass(frozen=True)
class TestResult:
    name: str
    passed: bool
    elapsed: float
    output: str
    detail: str = ""


def logical_cpu_count() -> int:
    """Return the machine's available logical CPU/thread count."""
    return max(1, os.cpu_count() or 1)


def run_command(command: list[str], timeout: float | None = None) -> tuple[bool, str, float]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = "\n".join(
            part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
        )
        return completed.returncode == 0, output, time.monotonic() - started
    except subprocess.TimeoutExpired as error:
        output = f"timed out after {timeout:g}s"
        if error.stderr:
            output += f"\n{error.stderr.decode(errors='replace').strip()}"
        return False, output, time.monotonic() - started
    except OSError as error:
        return False, f"could not start test process: {error}", time.monotonic() - started


def _live_detail(output: str) -> str:
    return next(
        (line for line in output.splitlines() if line.startswith("LIVE ")), ""
    )


def run_plugin(
    path: Path,
    timeout: float | None,
    live: bool,
    query: str,
    category: str,
    allow_empty: bool,
) -> TestResult:
    command = [sys.executable, str(LIVE_TEST if live else ENGINE_TEST), str(path)]
    if live:
        command.extend(["--query", query, "--category", category])
        if allow_empty:
            command.append("--allow-empty")
    passed, output, elapsed = run_command(command, timeout)
    return TestResult(
        path.stem,
        passed,
        elapsed,
        output,
        _live_detail(output) if live else "",
    )


def run_safety_test(timeout: float | None) -> TestResult:
    passed, output, elapsed = run_command([sys.executable, str(SAFETY_TEST)], timeout)
    return TestResult("safety helpers", passed, elapsed, output)


def print_failure_details(result: TestResult) -> None:
    if result.passed or not result.output:
        return
    print(f"\n--- {result.name} test output ---")
    print(result.output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test all standalone qBittorrent plugins in parallel."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="maximum seconds allowed for each isolated test process (default: 120)",
    )
    parser.add_argument(
        "--skip-safety",
        action="store_true",
        help="skip the local fake-server safety helper suite",
    )
    parser.add_argument(
        "--install-only",
        action="store_true",
        help="only validate imports and metadata; do not contact remote services",
    )
    parser.add_argument(
        "--query",
        default=None,
        help="override the per-plugin live query profile for every plugin",
    )
    parser.add_argument(
        "--category",
        default="all",
        help="qBittorrent category sent to every live plugin (default: all)",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="accept live tests that complete with zero parsed results (default)",
    )
    parser.add_argument(
        "--require-results",
        action="store_true",
        help="fail live tests that complete without parsed result records",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.timeout <= 0:
        print("ERROR: --timeout must be greater than zero.", file=sys.stderr)
        return 2

    plugins = sorted(PLUGIN_DIR.glob("*.py"))
    if not plugins:
        print(f"ERROR: no plugins found in {PLUGIN_DIR}", file=sys.stderr)
        return 2

    workers = logical_cpu_count()
    mode = "live searches" if not args.install_only else "installability checks"
    print(f"Testing {len(plugins)} plugins with {workers} parallel workers ({mode}).")
    print(f"Per-plugin timeout: {args.timeout:g}s")
    if not args.install_only:
        query_mode = "override: " + repr(args.query) if args.query else "per-plugin defaults"
        print(f"Live queries: {query_mode} | category: {args.category!r}")
        result_policy = "required" if args.require_results else "empty results allowed"
        print(f"Live result policy: {result_policy}")

    allow_empty = args.allow_empty or not args.require_results

    results: list[TestResult] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                run_plugin,
                path,
                args.timeout,
                not args.install_only,
                args.query or DEFAULT_LIVE_QUERIES.get(path.stem, "ubuntu"),
                args.category,
                allow_empty,
            ): path
            for path in plugins
        }
        for future in as_completed(futures):
            path = futures[future]
            try:
                result = future.result()
            except Exception as error:
                result = TestResult(
                    path.stem,
                    False,
                    0.0,
                    f"worker crashed: {type(error).__name__}: {error}",
                )
            results.append(result)
            status = "PASS" if result.passed else "FAIL"
            detail = f" — {result.detail}" if result.detail else ""
            print(f"[{status}] {result.name} ({result.elapsed:.2f}s){detail}", flush=True)

    results.sort(key=lambda result: result.name)
    failed_plugins = [result for result in results if not result.passed]
    print(f"\nPlugin result: {len(plugins) - len(failed_plugins)} passed, "
          f"{len(failed_plugins)} failed.")
    for result in failed_plugins:
        print_failure_details(result)

    if args.skip_safety:
        safety_result = None
        print("Safety helper suite: skipped.")
    else:
        print("\nRunning safety helper suite...")
        safety_result = run_safety_test(args.timeout)
        status = "PASS" if safety_result.passed else "FAIL"
        print(f"[{status}] {safety_result.name} ({safety_result.elapsed:.2f}s)")
        print_failure_details(safety_result)

    if failed_plugins or (safety_result is not None and not safety_result.passed):
        print("\nOVERALL: FAIL")
        return 1
    print("\nOVERALL: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
