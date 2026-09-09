import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { runPythonCaptured } from "../tool/core/run";
import { SAFETY_PREAMBLE } from "../tool/harden/safety_preamble";
import { auditPlugins } from "./safety/plugin_audit";
import { runSafetyPythonHarness } from "./safety/python_harness";

const SAFETY_BEHAVIOR_HARNESS = [
  "import importlib.util",
  "import sys",
  "import threading",
  "import time",
  "from types import ModuleType",
  "from typing import cast",
  "",
  "",
  "helper_path = sys.argv[1]",
  "spec = importlib.util.spec_from_file_location('generated_helpers', helper_path)",
  "if spec is None or spec.loader is None:",
  "    raise RuntimeError('could not load generated safety preamble')",
  "module = importlib.util.module_from_spec(spec)",
  "module.__dict__.update(",
  "    {",
  "        '_qbt_helper_retrieve_url': lambda *_args, **_kwargs: '',",
  "        'prettyPrinter': lambda _result: None,",
  "    }",
  ")",
  "cast(object, spec.loader).exec_module(module)",
  "generated = cast(ModuleType, module)",
  "",
  "",
  "generated.SEARCH_DEADLINE = 0.2",
  "first_deadline = generated._qbt_new_deadline()",
  "time.sleep(0.01)",
  "second_deadline = generated._qbt_new_deadline()",
  "assert second_deadline > first_deadline",
  "assert second_deadline - time.monotonic() > 0.1",
  "",
  "",
  "class Clock:",
  "    def __init__(self) -> None:",
  "        self.now = 100.0",
  "        self.sleeps: list[float] = []",
  "",
  "    def monotonic(self) -> float:",
  "        return self.now",
  "",
  "    def sleep(self, duration: float) -> None:",
  "        self.sleeps.append(duration)",
  "        self.now += duration",
  "",
  "",
  "clock = Clock()",
  "generated._qbt_time = clock",
  "generated.SEARCH_DEADLINE = 1.0",
  "generated.RETRY_DELAY = 0.6",
  "generated.MAX_ATTEMPTS = 3",
  "generated._qbt_new_deadline()",
  "retry_calls: list[float] = []",
  "",
  "",
  "def fail_request() -> str:",
  "    retry_calls.append(clock.monotonic())",
  "    return ''",
  "",
  "",
  "assert generated._qbt_retry_call(fail_request) == ''",
  "assert len(retry_calls) == 2",
  "assert len(clock.sleeps) == 2",
  "assert abs(clock.sleeps[0] - 0.6) < 0.000001",
  "assert abs(clock.sleeps[1] - 0.4) < 0.000001",
  "assert clock.now <= 101.000001",
  "",
  "",
  "real_time = time",
  "generated._qbt_time = real_time",
  "generated.MAX_WORKERS = 4",
  "recorded_worker_limits: list[int] = []",
  "real_executor = generated._QBTThreadPoolExecutor",
  "",
  "",
  "class RecordingExecutor(real_executor):",
  "    def __init__(self, *args: object, **kwargs: object) -> None:",
  "        recorded_worker_limits.append(cast(int, kwargs['max_workers']))",
  "        super().__init__(*args, **kwargs)",
  "",
  "",
  "generated._QBTThreadPoolExecutor = RecordingExecutor",
  "assert generated._qbt_run_parallel(",
  "    lambda value: value,",
  "    [('only',)],",
  "    real_time.monotonic() + 1.0,",
  ") == ['only']",
  "assert recorded_worker_limits == [1]",
  "generated._QBTThreadPoolExecutor = real_executor",
  "",
  "",
  "generated.MAX_WORKERS = 2",
  "active = 0",
  "peak_active = 0",
  "active_lock = threading.Lock()",
  "started = threading.Event()",
  "release = threading.Event()",
  "consumed: list[int] = []",
  "parallel_results: list[str] = []",
  "",
  "",
  "def blocking_worker(value: int) -> str:",
  "    global active, peak_active",
  "    with active_lock:",
  "        active += 1",
  "        peak_active = max(peak_active, active)",
  "        started.set()",
  "    release.wait(2.0)",
  "    with active_lock:",
  "        active -= 1",
  "    return str(value)",
  "",
  "",
  "def bounded_jobs():",
  "    for value in range(5):",
  "        consumed.append(value)",
  "        yield (value,)",
  "",
  "",
  "def run_parallel() -> None:",
  "    parallel_results.extend(",
  "        generated._qbt_run_parallel(",
  "            blocking_worker,",
  "            bounded_jobs(),",
  "            real_time.monotonic() + 5.0,",
  "        )",
  "    )",
  "",
  "",
  "parallel_thread = threading.Thread(target=run_parallel)",
  "parallel_thread.start()",
  "assert started.wait(1.0)",
  "wait_deadline = real_time.monotonic() + 1.0",
  "while active < 2 and real_time.monotonic() < wait_deadline:",
  "    real_time.sleep(0.001)",
  "assert active == 2",
  "assert len(consumed) == 2",
  "release.set()",
  "parallel_thread.join(2.0)",
  "assert not parallel_thread.is_alive()",
  "assert peak_active <= 2",
  "assert set(parallel_results) == {'0', '1', '2', '3', '4'}",
  "",
  "",
  "class FakeResponse:",
  "    status = 200",
  "",
  "    def __init__(self) -> None:",
  "        self.read_sizes: list[int] = []",
  "        self.closed = False",
  "",
  "    def __enter__(self):",
  "        return self",
  "",
  "    def __exit__(self, _exc_type, _exc_value, _traceback) -> bool:",
  "        self.close()",
  "        return False",
  "",
  "    def read(self, size: int) -> bytes:",
  "        self.read_sizes.append(size)",
  "        return b'0123456789'[:size]",
  "",
  "    def close(self) -> None:",
  "        self.closed = True",
  "",
  "    def getcode(self) -> int:",
  "        return self.status",
  "",
  "",
  "generated.MAX_RESPONSE_BYTES = 4",
  "direct_response = FakeResponse()",
  "assert generated._qbt_read_response(direct_response) == b'0123'",
  "assert direct_response.read_sizes == [4]",
  "",
  "safe_response = FakeResponse()",
  "",
  "",
  "def fake_urlopen(*_args: object, **_kwargs: object):",
  "    return safe_response",
  "",
  "",
  "generated._qbt_urlopen_typed = fake_urlopen",
  "generated.MAX_ATTEMPTS = 1",
  "generated.SEARCH_DEADLINE = 1.0",
  "generated._qbt_new_deadline()",
  "with generated._qbt_safe_urlopen('https://example.invalid') as response:",
  "    assert response.read() == b'0123'",
  "assert safe_response.read_sizes == [4]",
  "print('Safety behavior tests passed.')",
].join("\n");

async function runSafetyBehaviorHarness(helperPath: string, scriptPath: string): Promise<void> {
  const result = await runPythonCaptured([scriptPath, helperPath]);
  if (result.code !== 0) {
    throw new Error(
      `Python safety behavior test failed with exit code ${result.code}.\n${result.output}`,
    );
  }
  process.stdout.write(result.output);
}

async function waitForRequests(
  counts: Map<string, number>,
  path: string,
  expected: number,
): Promise<void> {
  const deadline = performance.now() + 500;
  while ((counts.get(path) ?? 0) < expected && performance.now() < deadline) {
    await Bun.sleep(10);
  }
}

export async function runSafetySuite(): Promise<void> {
  await auditPlugins();

  const serverCounts = new Map<string, number>();
  const server = Bun.serve({
    port: 0,
    fetch: async (request) => {
      const path = new URL(request.url).pathname;
      const count = (serverCounts.get(path) ?? 0) + 1;
      serverCounts.set(path, count);
      if (path === "/slow") {
        await Bun.sleep(200);
        return new Response("late");
      }
      if (path === "/retry" && count < 3) {
        return new Response("busy", { status: 503 });
      }
      if (path === "/permanent") {
        return new Response("missing", { status: 404 });
      }
      return new Response("ok");
    },
  });

  const temporaryDirectory = await mkdtemp(resolve(tmpdir(), "qbsearch-safety-"));
  const helperPath = resolve(temporaryDirectory, "generated_helpers.py");
  const behaviorHarnessPath = resolve(temporaryDirectory, "safety_behavior.py");
  try {
    await writeFile(behaviorHarnessPath, SAFETY_BEHAVIOR_HARNESS, "utf8");
    await writeFile(helperPath, "from __future__ import annotations\n\n" + SAFETY_PREAMBLE, "utf8");
    await runSafetyBehaviorHarness(helperPath, behaviorHarnessPath);
    await runSafetyPythonHarness(helperPath, `http://127.0.0.1:${server.port}`);
    await waitForRequests(serverCounts, "/slow", 3);
    if (serverCounts.get("/ok") !== 1) {
      throw new Error(`expected one /ok request, saw ${serverCounts.get("/ok") ?? 0}`);
    }
    if (serverCounts.get("/slow") !== 3) {
      throw new Error(`expected three /slow requests, saw ${serverCounts.get("/slow") ?? 0}`);
    }
    if (serverCounts.get("/retry") !== 3) {
      throw new Error(`expected three /retry requests, saw ${serverCounts.get("/retry") ?? 0}`);
    }
    if (serverCounts.get("/permanent") !== 1) {
      throw new Error(
        `expected one /permanent request, saw ${serverCounts.get("/permanent") ?? 0}`,
      );
    }
  } finally {
    await server.stop(true);
    await rm(temporaryDirectory, { recursive: true, force: true });
  }
}
