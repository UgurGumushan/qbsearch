import { expect, test } from "bun:test";
import { audiobookCase, darklibriaCase, ytsCase, YTS_SEARCH_URL } from "./support/concurrent_cases";
import { assertUsableParserResults, replayParserFixture as replay } from "./support/parser_replay";

test("AudioBook Bay overlaps page and detail requests while preserving unique usable records", async () => {
  const report = await replay({ ...audiobookCase(), maxWorkers: 4 });
  assertUsableParserResults(report);
  expect(report.records).toHaveLength(32);
  expect(new Set(report.records.map((row) => row.name))).toEqual(
    new Set(Array.from({ length: 32 }, (_, id) => `Book ${id}`)),
  );
  expect(report.records.every((row) => row.size === "1 GB")).toBe(true);
  expect(report.requests).toHaveLength(41);
  expect(new Set(report.requests).size).toBe(report.requests.length);
  expect(report.peakConcurrentRequests).toBeGreaterThan(1);
  expect(report.peakConcurrentRequests).toBeLessThanOrEqual(16);
});

test("AudioBook Bay preserves the global detail cap across concurrent pagination", async () => {
  const report = await replay({ ...audiobookCase(), maxPages: 3, maxDetails: 5, maxWorkers: 4 });
  assertUsableParserResults(report);
  expect(new Set(report.records.map((row) => row.name))).toEqual(
    new Set(["Book 0", "Book 1", "Book 2", "Book 3", "Book 4"]),
  );
  expect(report.requests.filter((url) => url.includes("/page/"))).toHaveLength(3);
  expect(report.requests.filter((url) => url.includes("/book/"))).toHaveLength(5);
});

test("YTS overlaps known pages and keeps page order, fields, and cross-page deduplication", async () => {
  const report = await replay({ ...ytsCase(), maxWorkers: 4 });
  assertUsableParserResults(report, true);
  expect(report.records.map((row) => row.link)).toEqual(
    Array.from({ length: 16 }, (_, id) => `https://example.test/${id + 1}.torrent`),
  );
  expect(report.records.every((row) => row.size === "100 B" && row.seeds === 10)).toBe(true);
  expect(report.requests).toHaveLength(8);
  expect(report.peakConcurrentRequests).toBeGreaterThan(1);
  expect(report.peakConcurrentRequests).toBeLessThanOrEqual(16);
});

test("YTS bounds known pagination and retains later good pages after a malformed response", async () => {
  const fixture = ytsCase();
  fixture.maxPages = 3;
  fixture.maxWorkers = 4;
  fixture.responses[`${YTS_SEARCH_URL}&page=2`] = "malformed JSON";
  const report = await replay(fixture);
  assertUsableParserResults(report, true);
  expect(report.records.map((row) => row.link)).toEqual(
    [1, 2, 5, 6].map((id) => `https://example.test/${id}.torrent`),
  );
  expect(new Set(report.requests)).toEqual(
    new Set([YTS_SEARCH_URL, `${YTS_SEARCH_URL}&page=2`, `${YTS_SEARCH_URL}&page=3`]),
  );
  expect(report.output.some((line) => line.includes("Error parsing YTS response:"))).toBe(true);
});

test("Darklibria keeps detail requests concurrent when the search has only two pages", async () => {
  const report = await replay({ ...darklibriaCase(), maxWorkers: 4 });
  assertUsableParserResults(report);
  expect(report.records).toHaveLength(32);
  expect(new Set(report.records.map((row) => row.desc_link)).size).toBe(32);
  expect(report.records.every((row) => row.size === "1 GB" && row.seeds === 10)).toBe(true);
  expect(report.requests).toHaveLength(34);
  expect(new Set(report.requests).size).toBe(report.requests.length);
  expect(report.peakConcurrentRequests).toBeGreaterThan(2);
  expect(report.peakConcurrentRequests).toBeLessThanOrEqual(16);
  const laterDetails = report.requests.flatMap((url, index) =>
    /\/series\/(?:1[6-9]|2\d|3[01])$/.test(url) ? [report.requestConcurrency?.[index] ?? 0] : [],
  );
  expect(Math.max(...laterDetails)).toBeGreaterThan(2);
});
