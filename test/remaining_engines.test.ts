import { expect, test } from "bun:test";
import { resolve } from "node:path";
import { FIXTURES_DIR } from "../tool/core/repo";
import { replayParserCase, replayParserFixture } from "./support/parser_replay";

test("Ali213's current resource buttons do not falsely qualify as downloadable results", async () => {
  const report = await replayParserCase(resolve(FIXTURES_DIR, "parsers", "ali213-current.json"));
  expect(report.code).toBe(0);
  expect(report.errors).toEqual([]);
  expect(report.requests).toHaveLength(2);
  expect(report.records).toEqual([]);
  expect(report.downloadRequests).toEqual([]);
});

test("Traht's captured empty browse response completes without inventing a result", async () => {
  const report = await replayParserFixture({
    plugin: "traht",
    query: "inception",
    responses: { "https://traht.org/browse.php?search=inception&page=1": "" },
  });
  expect(report.code).toBe(0);
  expect(report.errors).toEqual([]);
  expect(new Set(report.requests)).toEqual(
    new Set(["https://traht.org/browse.php?search=inception&page=1"]),
  );
  expect(report.records).toEqual([]);
});
