import { expect, test } from "bun:test";
import { parseLiveArguments } from "./live/cli";
import { countResultMarkers } from "./live/http";
import { buildProbeUrl } from "./live/plugin_source";
import { parseWorkerArguments } from "./live/worker";

test("live coordinator parser keeps repeated plugin filters and defaults", () => {
  expect(
    parseLiveArguments([
      "--timeout",
      "30",
      "--query=ubuntu linux",
      "--category",
      "all",
      "--plugin",
      "yts",
      "--plugin=nyaa",
      "--require-results",
    ]),
  ).toEqual({
    timeout: 30,
    skipSafety: false,
    installOnly: false,
    query: "ubuntu linux",
    category: "all",
    contentCategory: "all",
    pluginIds: ["yts", "nyaa"],
    allowEmpty: false,
    requireResults: true,
  });
});

test("live worker parser resolves a plugin path from the repository root", () => {
  const parsed = parseWorkerArguments(["plugins/yts.py", "--install-only"]);
  expect(parsed).toMatchObject({
    query: "ubuntu",
    category: "all",
    allowEmpty: false,
    installOnly: true,
  });
  expect(parsed?.plugin).toContain("/plugins/yts.py");
});

test("probe URL expansion handles query, category, and page placeholders", () => {
  const source = `
class fixture:
    url = "https://example.test"
    def search(self, what, cat="all"):
        endpoint = "https://example.test/api?q={what}&cat={cat}&page={page}"
`;
  expect(buildProbeUrl(source, "https://example.test", "ubuntu linux", "movies")).toBe(
    "https://example.test/api?q=ubuntu%20linux&cat=movies&page=1",
  );
});

test("probe URL extraction handles Python f-strings and concatenated queries", () => {
  const formatted = `
class fixture:
    url = "https://example.test"
    def search(self, what, cat="all"):
        endpoint = f"{self.url}/search/{what}?category={cat}&page={page}"
`;
  expect(buildProbeUrl(formatted, "https://example.test", "ubuntu linux", "movies")).toBe(
    "https://example.test/search/ubuntu%20linux?category=movies&page=1",
  );

  const concatenated = `
class fixture:
    def search(self, what, cat="all"):
        endpoint = "https://example.test/api?q=" + what
`;
  expect(buildProbeUrl(concatenated, "https://example.test", "ubuntu linux", "all")).toBe(
    "https://example.test/api?q=ubuntu%20linux",
  );
});

test("result marker scanner handles JSON and HTML response shapes", () => {
  expect(
    countResultMarkers(
      JSON.stringify({ torrents: [{ link: "magnet:?xt=urn:btih:one" }, { link: "two" }] }),
      "application/json",
    ),
  ).toBe(2);
  expect(countResultMarkers('<article class="search-result"></article>')).toBe(1);
});
