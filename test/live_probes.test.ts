import { expect, test } from "bun:test";
import { checkProbeFixtures, diffProbeFixtures, type ProbeFixtures } from "./live/probe_fixtures";

const RECORDED: ProbeFixtures = {
  yts: { query: "inception", siteUrl: "https://example.com", urls: ["https://example.com/?q=a"] },
};

test("probe fixture comparator ignores identical fixtures", () => {
  expect(diffProbeFixtures(RECORDED, structuredClone(RECORDED))).toEqual([]);
});

test("probe fixture comparator reports url, query, and missing drift", () => {
  const changedUrls: ProbeFixtures = {
    yts: { query: "inception", siteUrl: "https://example.com", urls: ["https://example.com/?q=b"] },
  };
  expect(diffProbeFixtures(RECORDED, changedUrls)).toHaveLength(1);
  expect(diffProbeFixtures(RECORDED, changedUrls)[0]).toContain("yts");

  const changedQuery: ProbeFixtures = {
    yts: { query: "other", siteUrl: "https://example.com", urls: ["https://example.com/?q=a"] },
  };
  expect(diffProbeFixtures(RECORDED, changedQuery)).toHaveLength(1);

  expect(diffProbeFixtures(RECORDED, {})).toEqual([
    "yts: fixture recorded for a plugin missing from the catalog",
  ]);
  expect(diffProbeFixtures({}, RECORDED)).toEqual(["yts: no recorded fixture (re-record probes)"]);
});

test("checked-in probe fixtures match the current heuristic", async () => {
  const drifts = await checkProbeFixtures();
  expect(drifts).toEqual([]);
}, 120_000);
