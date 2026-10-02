import { createHash } from "node:crypto";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { discoverCatalogPlugins, pluginId } from "../../tool/core/plugins";
import { ROOT } from "../../tool/core/repo";
import { pythonCommand, runCapturedCommand } from "../../tool/core/run";
import {
  replayParserCase,
  type ParserCase,
  type ParserReport,
  type FixtureReply,
} from "../support/parser_replay";
import { benchmarkFixtures, type BenchmarkFixture } from "./fixtures";
import { acceptance, resultSignature, summarize, type Measurements } from "./statistics";

export interface BenchmarkOptions {
  baseline: string;
  plugins: string[];
  samples: number;
  warmups: number;
  matrix: boolean;
}

export function parseBenchmarkArguments(args: string[]): BenchmarkOptions {
  const options: BenchmarkOptions = {
    baseline: "v0.1.10",
    plugins: [],
    samples: 20,
    warmups: 2,
    matrix: false,
  };
  for (let index = 0; index < args.length; index += 1) {
    const flag = args[index];
    if (flag === "--matrix") {
      options.matrix = true;
      continue;
    }
    if (!["--baseline", "--plugin", "--samples", "--warmups"].includes(flag)) {
      throw new Error(`unsupported benchmark argument: ${flag}`);
    }
    const value = args[++index];
    if (!value || value.startsWith("--")) throw new Error(`${flag} requires a value`);
    if (flag === "--baseline") options.baseline = value;
    else if (flag === "--plugin") options.plugins.push(value);
    else {
      const number = Number(value);
      const minimum = flag === "--warmups" ? 0 : 1;
      if (!Number.isInteger(number) || number < minimum || number > 100)
        throw new Error(`invalid ${flag}`);
      if (flag === "--samples") options.samples = number;
      else options.warmups = number;
    }
  }
  return options;
}

interface Scenario {
  name: string;
  workers: number;
  delay: number;
  uneven: boolean;
}

function scenarios(matrix: boolean): Scenario[] {
  if (!matrix) return [{ name: "cpu", workers: 4, delay: 0, uneven: false }];
  return [1, 4, 16].flatMap((workers) => [
    { name: "cpu", workers, delay: 0, uneven: false },
    { name: "20ms", workers, delay: 20, uneven: false },
    { name: "100ms", workers, delay: 100, uneven: false },
    { name: "uneven", workers, delay: 0, uneven: true },
  ]);
}

export function scenarioCase(fixture: ParserCase, scenario: Scenario): ParserCase {
  const response = (reply: FixtureReply, index: number): FixtureReply => {
    const fields = typeof reply === "string" ? { body: reply } : reply;
    // Explicit fault delays remain available outside the scheduling matrix.
    return { ...fields, delayMs: scenario.uneven ? (index % 4 === 0 ? 150 : 5) : scenario.delay };
  };
  return {
    ...fixture,
    maxWorkers: scenario.workers,
    responseDelayMs: scenario.delay,
    responses: Object.fromEntries(
      Object.entries(fixture.responses).map(([url, reply], index) => [url, response(reply, index)]),
    ),
    exchanges: fixture.exchanges?.map((exchange, index) => ({
      ...exchange,
      response: response(exchange.response, index),
    })),
  };
}

interface VariantRuns {
  timing: ParserReport[];
  memory: ParserReport[];
}
interface Comparison {
  plugin: string;
  fixture: string;
  evidence: BenchmarkFixture["evidence"];
  fixtureSha256: string;
  scenario: Scenario;
  before: Measurements;
  after: Measurements;
  equalResults: boolean;
  errors: string[];
  wins: string[];
  regressions: string[];
  verdict: string;
  baseline: VariantRuns;
  candidate: VariantRuns;
}

export async function compareFixture(
  fixture: BenchmarkFixture,
  scenario: Scenario,
  options: BenchmarkOptions,
  baselineRoot: string,
  path: string,
  changed: boolean,
): Promise<Comparison> {
  const contents = JSON.stringify(scenarioCase(fixture.case, scenario));
  await Bun.write(path, contents);
  const baseline: VariantRuns = { timing: [], memory: [] };
  const candidate: VariantRuns = { timing: [], memory: [] };
  const errors: string[] = [];
  let signature: string | undefined;
  let equalResults = true;
  const run = async (variant: "baseline" | "candidate", trace: boolean, warmup: boolean) => {
    const report = await replayParserCase(path, {
      sourceRoot: variant === "baseline" ? baselineRoot : ROOT,
      measure: true,
      trace,
      timeoutSeconds: 60,
    });
    if (report.errors.length > 0)
      errors.push(...report.errors.map((error) => `${variant}: ${error}`));
    const actual = resultSignature(report, fixture.ordered);
    signature ??= actual;
    if (actual !== signature) equalResults = false;
    if ((report.peakConcurrentRequests ?? 0) > scenario.workers)
      errors.push(`${variant}: request concurrency exceeds worker limit`);
    if (!fixture.case.expectEmpty && (report.metrics?.usableResults ?? 0) === 0)
      errors.push(`${variant}: no usable results`);
    if (fixture.case.expectEmpty && (report.metrics?.usableResults ?? 0) !== 0)
      errors.push(`${variant}: expected empty results`);
    if (!warmup)
      (variant === "baseline" ? baseline : candidate)[trace ? "memory" : "timing"].push(report);
  };
  try {
    for (let index = 0; index < options.warmups; index += 1) {
      const order: ("baseline" | "candidate")[] =
        index % 2 === 0 ? ["baseline", "candidate"] : ["candidate", "baseline"];
      for (const variant of order) await run(variant, false, true);
    }
    // Tracing changes CPU and scheduling, so it runs in separate fresh processes.
    for (const trace of [false, true]) {
      for (let index = 0; index < options.samples; index += 1) {
        const order: ("baseline" | "candidate")[] =
          index % 2 === 0 ? ["baseline", "candidate"] : ["candidate", "baseline"];
        for (const variant of order) await run(variant, trace, false);
      }
    }
  } catch (error) {
    errors.push(error instanceof Error ? error.message : String(error));
  }
  const before = summarize(baseline.timing, baseline.memory);
  const after = summarize(candidate.timing, candidate.memory);
  const gate = acceptance(before, after);
  const meaningful = fixture.evidence !== "empty" && !fixture.case.expectEmpty;
  const verified = meaningful && errors.length === 0 && equalResults;
  const verdict = !verified
    ? "unverified"
    : !changed
      ? "unchanged"
      : options.samples < 20
        ? "exploratory"
        : gate.regressions.length > 0
          ? "regression"
          : gate.wins.length > 0
            ? "win"
            : "no material gain";
  return {
    plugin: fixture.case.plugin,
    fixture: fixture.name,
    evidence: fixture.evidence,
    fixtureSha256: createHash("sha256").update(contents).digest("hex"),
    scenario,
    before,
    after,
    equalResults,
    errors: [...new Set(errors)],
    ...gate,
    verdict,
    baseline,
    candidate,
  };
}

async function baselineSource(commit: string, id: string): Promise<Uint8Array> {
  const child = Bun.spawn(["git", "show", `${commit}:plugins/${id}.py`], {
    cwd: ROOT,
    stdout: "pipe",
    stderr: "pipe",
  });
  const [body, error, code] = await Promise.all([
    new Response(child.stdout).arrayBuffer(),
    new Response(child.stderr).text(),
    child.exited,
  ]);
  if (code !== 0) throw new Error(`baseline does not contain ${id}: ${error.trim()}`);
  return new Uint8Array(body);
}

function milliseconds(value: Measurements["total"]): string {
  return value ? `${(value.median * 1000).toFixed(1)}/${(value.p95 * 1000).toFixed(1)}` : "—";
}

export async function runBenchmark(args: string[]): Promise<number> {
  if (args.includes("--help") || args.includes("-h")) {
    console.log(`Usage: bun run test -- --benchmark [--plugin <id>] [--baseline <git-ref>]
  --matrix       Workers 1/4/16; CPU, 20ms, 100ms, and uneven 5/150ms responses
  --samples <n>  Measured pairs per timing/memory mode (default 20; <20 exploratory)
  --warmups <n>  Unmeasured pairs (default 2)
Outputs a table and JSON/fixtures under working/performance/. No network access.`);
    return 0;
  }
  let directory: string | undefined;
  try {
    const options = parseBenchmarkArguments(args);
    const ids = (await discoverCatalogPlugins()).map(pluginId);
    if (options.plugins.some((id) => !ids.includes(id)))
      throw new Error("unknown benchmark plugin");
    const selected =
      options.plugins.length > 0 ? ids.filter((id) => options.plugins.includes(id)) : ids;
    const ref = await runCapturedCommand([
      "git",
      "rev-parse",
      "--verify",
      "--end-of-options",
      `${options.baseline}^{commit}`,
    ]);
    if (ref.code !== 0 || !/^[a-f\d]{40}$/.test(ref.output))
      throw new Error(`invalid baseline ref: ${options.baseline}`);
    const python = await runCapturedCommand([
      ...pythonCommand(),
      "-c",
      "import sys; print(sys.version)",
    ]);
    if (python.code !== 0) throw new Error(python.output);
    directory = await mkdtemp(resolve(tmpdir(), "qbsearch-benchmark-"));
    const output = resolve(
      ROOT,
      "working",
      "performance",
      `benchmark-${new Date().toISOString().replace(/[:.]/g, "-")}`,
    );
    const comparisons: Comparison[] = [];
    const tooling: Record<string, string> = {};
    for (const path of [
      "test/parser_harness.py",
      "test/replay_transport.py",
      "test/engine_harness.py",
      "test/performance/runner.ts",
      "test/performance/fixtures.ts",
      "test/performance/statistics.ts",
      "test/support/parser_replay.ts",
    ]) {
      const bytes = await Bun.file(resolve(ROOT, path)).arrayBuffer();
      tooling[path] = createHash("sha256").update(new Uint8Array(bytes)).digest("hex");
      await Bun.write(resolve(output, "tooling", path), bytes);
    }
    const sources: Record<string, { baseline: string; candidate: string }> = {};
    const report = {
      schemaVersion: 2,
      createdAt: new Date().toISOString(),
      options,
      baselineCommit: ref.output,
      python: python.output,
      interpreter: pythonCommand(),
      platform: { os: process.platform, arch: process.arch },
      tooling,
      sources,
      comparisons,
    };
    console.log(
      "Plugin / fixture / scenario | total ms median/p95 (before → after) | requests | result",
    );
    for (const id of selected) {
      const source = await baselineSource(ref.output, id);
      await Bun.write(resolve(directory, "plugins", `${id}.py`), source);
      const candidate = await Bun.file(resolve(ROOT, "plugins", `${id}.py`)).arrayBuffer();
      await Bun.write(resolve(output, "sources", "baseline", "plugins", `${id}.py`), source);
      await Bun.write(resolve(output, "sources", "candidate", "plugins", `${id}.py`), candidate);
      sources[id] = {
        baseline: createHash("sha256").update(source).digest("hex"),
        candidate: createHash("sha256").update(new Uint8Array(candidate)).digest("hex"),
      };
      for (const fixture of await benchmarkFixtures(id)) {
        for (const scenario of scenarios(options.matrix)) {
          console.log(
            `Measuring ${id}/${fixture.name}/${scenario.name}, workers=${scenario.workers}...`,
          );
          const comparison = await compareFixture(
            fixture,
            scenario,
            options,
            directory,
            resolve(
              output,
              "fixtures",
              `${id}-${fixture.name}-${scenario.workers}-${scenario.name}.json`,
            ),
            sources[id].baseline !== sources[id].candidate,
          );
          comparisons.push(comparison);
          console.log(
            `${id}/${fixture.name}/${scenario.workers}:${scenario.name} | ${milliseconds(comparison.before.total)} → ${milliseconds(comparison.after.total)} | ${comparison.before.requests?.median ?? "—"} → ${comparison.after.requests?.median ?? "—"} | ${comparison.verdict}`,
          );
          await Bun.write(resolve(output, "report.json"), `${JSON.stringify(report, null, 2)}\n`);
        }
      }
    }
    console.log(`Report: ${resolve(output, "report.json")}`);
    return comparisons.some(
      (row) =>
        row.verdict === "regression" ||
        (row.evidence !== "empty" && (!row.equalResults || row.errors.length > 0)),
    )
      ? 1
      : 0;
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    return 2;
  } finally {
    if (directory) await rm(directory, { recursive: true, force: true });
  }
}
