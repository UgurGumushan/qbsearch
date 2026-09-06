import { join } from "node:path";
import { format } from "prettier";
import { ROOT } from "../../tool/core/repo";
import { inspectPluginFile, readPluginSource } from "../../tool/core/plugins";
import { loadLiveCatalog } from "./catalog";
import { buildProbeUrls } from "./plugin_source";
import { pluginPath } from "./runner";

export const PROBE_FIXTURES_PATH = join(ROOT, "test", "live", "fixtures", "probe-urls.json");

export interface ProbeFixture {
  query: string;
  siteUrl: string;
  urls: string[];
}

export type ProbeFixtures = Record<string, ProbeFixture>;

/** Build the current probe fixtures for every catalog plugin (no network). */
export async function buildProbeFixtures(queryOverride: string | null): Promise<ProbeFixtures> {
  const catalog = await loadLiveCatalog();
  const fixtures: ProbeFixtures = {};
  for (const entry of [...catalog].sort((a, b) => a.id.localeCompare(b.id))) {
    const query = queryOverride ?? entry.defaultQuery;
    const path = pluginPath(entry.id);
    const [source, metadata] = await Promise.all([readPluginSource(path), inspectPluginFile(path)]);
    fixtures[entry.id] = {
      query,
      siteUrl: metadata.site_url,
      urls: buildProbeUrls(source, metadata.site_url, query, "all"),
    };
  }
  return fixtures;
}

export async function writeProbeFixtures(queryOverride: string | null): Promise<void> {
  const fixtures = await buildProbeFixtures(queryOverride);
  await Bun.write(
    PROBE_FIXTURES_PATH,
    await format(JSON.stringify(fixtures, null, 2), { parser: "json", printWidth: 100 }),
  );
  console.log(
    `Wrote ${Object.keys(fixtures).length} probe fixtures to test/live/fixtures/probe-urls.json`,
  );
}

export async function loadProbeFixtures(): Promise<ProbeFixtures> {
  const file = Bun.file(PROBE_FIXTURES_PATH);
  if (!(await file.exists())) {
    throw new Error("probe fixtures missing: run bun run test -- --live --record-probes");
  }
  return (await file.json()) as ProbeFixtures;
}

/** Compare recorded fixtures against current heuristic output (pure, no I/O in compare). */
export function diffProbeFixtures(recorded: ProbeFixtures, current: ProbeFixtures): string[] {
  const drifts: string[] = [];
  for (const id of Object.keys(current).sort()) {
    const actual = current[id];
    if (!Object.hasOwn(recorded, id)) {
      drifts.push(`${id}: no recorded fixture (re-record probes)`);
      continue;
    }
    const expected = recorded[id];
    if (
      expected.query !== actual.query ||
      expected.siteUrl !== actual.siteUrl ||
      JSON.stringify(expected.urls) !== JSON.stringify(actual.urls)
    ) {
      drifts.push(
        `${id}: probe drift (query ${JSON.stringify(expected.query)} → ${JSON.stringify(actual.query)}, ` +
          `${expected.urls.length} → ${actual.urls.length} urls)`,
      );
    }
  }
  for (const id of Object.keys(recorded).sort()) {
    if (!Object.hasOwn(current, id)) {
      drifts.push(`${id}: fixture recorded for a plugin missing from the catalog`);
    }
  }
  return drifts;
}

/** Check current heuristic output against checked-in fixtures. */
export async function checkProbeFixtures(): Promise<string[]> {
  const [recorded, current] = await Promise.all([loadProbeFixtures(), buildProbeFixtures(null)]);
  return diffProbeFixtures(recorded, current);
}
