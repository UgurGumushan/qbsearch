/**
 * Verify deterministic probe URL inference and fixture drift diagnostics.
 * @file
 */
import { expect, test } from "bun:test";
import { checkProbeFixtures, diffProbeFixtures, type ProbeFixtures } from "./live/probe_fixtures";
import { buildProbeUrl, buildProbeUrls } from "./live/plugin_source";
import { withoutPythonDocumentation } from "../tool/core/python-analysis";

const RECORDED: ProbeFixtures = {
  yts: { query: "inception", siteUrl: "https://example.com", urls: ["https://example.com/?q=a"] },
};

test("probe inference ignores documentation instead of adding its text to request URLs", () => {
  const source = `
class fixture:
    url = "https://example.test"
    def request(self, url, searchTerm, category, page):
        request_url = url + "/page/" + str(page) + "/?s=" + searchTerm + "&cat=" + category
        return retrieve_url(request_url)
    def search(self, what, cat="all"):
        return self.request(self.url, what, cat, 1)
`;
  const expected = buildProbeUrls(source, "https://example.test", "the hobbit", "all");
  expect(expected[0]).toBe("https://example.test/page/1/?s=the%20hobbit");
  for (const docstring of [
    '"""Fetch one category-filtered audiobook search page."""',
    "'''Fetch a page.\nIgnore example URL https://invalid.test/search?q={what}.'''",
    'r"""Fetch a page using the URL helper."""',
    '"Fetch a page using the URL helper."',
    `"""${"Document the search URL. ".repeat(100)}"""`,
  ]) {
    const documented = source.replace(
      "        request_url =",
      `        ${docstring}\n        # Example: f"https://invalid.test/search?q={what}"\n        request_url =`,
    );
    expect(buildProbeUrls(documented, "https://example.test", "the hobbit", "all")).toEqual(
      expected,
    );
  }
  const commented = '# Example: f"https://invalid.test/search?q={what}"\n' + source;
  expect(buildProbeUrl(commented, "https://example.test", "the hobbit", "all")).toBe(expected[0]);
});

test("documentation stripping preserves assigned Python strings and URL fragments", () => {
  const source = `"""Module documentation."""
payload = """Keep multiline data.\n# This hash belongs to the data."""
url = "https://example.test/search?q={what}#results" # Ignore this comment.
escaped = 'A \\'quoted\\' value'
endpoint = (
    "https://example.test/search"
    f"?q={what}"
)
`;
  const stripped = withoutPythonDocumentation(source);
  expect(stripped).toContain(
    'payload = """Keep multiline data.\n# This hash belongs to the data."""',
  );
  expect(stripped).toContain('url = "https://example.test/search?q={what}#results"');
  expect(stripped).toContain("escaped = 'A \\'quoted\\' value'");
  expect(stripped).toContain('"https://example.test/search"');
  expect(stripped).toContain('f"?q={what}"');
  expect(stripped).not.toContain("Module documentation");
  expect(stripped).not.toContain("Ignore this comment");
});

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
