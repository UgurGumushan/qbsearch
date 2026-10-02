import type { ParserReport } from "../support/parser_replay";

export interface Distribution {
  median: number;
  p95: number;
}

export function distribution(values: number[]): Distribution | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return {
    median: sorted.length % 2 === 0 ? (sorted[middle - 1] + sorted[middle]) / 2 : sorted[middle],
    p95: sorted[Math.ceil(sorted.length * 0.95) - 1],
  };
}

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([key, item]) => [key, canonical(item)]),
    );
  }
  return value;
}

export function resultSignature(report: ParserReport, ordered: boolean): string {
  const rows = report.records.map((row) => JSON.stringify(canonical(row)));
  return JSON.stringify(ordered ? rows : rows.sort());
}

export interface Measurements {
  import: Distribution | null;
  process: Distribution | null;
  first: Distribution | null;
  total: Distribution | null;
  cpu: Distribution | null;
  allocations: Distribution | null;
  rss: Distribution | null;
  requests: Distribution | null;
  bytes: Distribution | null;
  results: Distribution | null;
  peakConcurrency: number;
}

export function summarize(timing: ParserReport[], memory: ParserReport[]): Measurements {
  const metric = (
    key:
      | "importSeconds"
      | "firstResultSeconds"
      | "totalSeconds"
      | "cpuSeconds"
      | "responseBytes"
      | "usableResults",
    runs = timing,
  ) =>
    distribution(
      runs.flatMap((run) => (typeof run.metrics?.[key] === "number" ? [run.metrics[key]] : [])),
    );
  return {
    import: metric("importSeconds"),
    process: distribution(
      timing.flatMap((run) => (run.processSeconds === undefined ? [] : [run.processSeconds])),
    ),
    first: metric("firstResultSeconds"),
    total: metric("totalSeconds"),
    cpu: metric("cpuSeconds"),
    allocations: distribution(
      memory.flatMap((run) =>
        run.metrics?.peakAllocatedBytes == null ? [] : [run.metrics.peakAllocatedBytes],
      ),
    ),
    rss: distribution(
      timing.flatMap((run) =>
        run.metrics?.peakRssBytes == null ? [] : [run.metrics.peakRssBytes],
      ),
    ),
    requests: distribution(timing.map((run) => run.requests.length)),
    bytes: metric("responseBytes"),
    results: metric("usableResults"),
    peakConcurrency: Math.max(0, ...timing.map((run) => run.peakConcurrentRequests ?? 0)),
  };
}

export function improvement(before: number, after: number): number {
  return before === 0 ? 0 : (before - after) / before;
}

/** Absolute floors keep tiny CPU/allocation changes from becoming headline wins. */
export function acceptance(
  before: Measurements,
  after: Measurements,
): { wins: string[]; regressions: string[] } {
  const wins: string[] = [];
  const regressions: string[] = [];
  if (before.requests && after.requests && after.requests.median < before.requests.median)
    wins.push("fewer requests");
  if (before.total && after.total && improvement(before.total.median, after.total.median) >= 0.1)
    wins.push("total >=10%");
  if (before.first && after.first && improvement(before.first.median, after.first.median) >= 0.25)
    wins.push("first >=25%");
  if (
    before.cpu &&
    after.cpu &&
    before.cpu.median - after.cpu.median >= 0.005 &&
    improvement(before.cpu.median, after.cpu.median) >= 0.2
  )
    wins.push("CPU >=20% and 5ms");
  if (
    before.allocations &&
    after.allocations &&
    before.allocations.median - after.allocations.median >= 1024 * 1024 &&
    improvement(before.allocations.median, after.allocations.median) >= 0.25
  )
    wins.push("heap >=25% and 1MiB");
  if (before.total && after.total) {
    if (after.total.median > before.total.median * 1.05) regressions.push("total median >5%");
    if (after.total.p95 > before.total.p95 * 1.1) regressions.push("total p95 >10%");
  }
  return { wins, regressions };
}
