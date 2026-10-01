import { expect, test } from "bun:test";
import { rejects } from "node:assert/strict";
import { parseLiveArguments } from "./live/cli";
import { countResultMarkers, fetchTextWithRetry } from "./live/http";
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
    recordProbes: false,
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

test("Elitetorrent marker detection counts unique result cards and ignores unrelated links", () => {
  const context = { id: "elitetorrent", siteUrl: "https://www.elitetorrent.com" };
  const html = `<a href="/peliculas/sidebar/">sidebar</a>
<ul class="miniboxs miniboxs-ficha">
<li><a href="/peliculas/movie/">image</a><a href='/peliculas/movie/'>title</a></li>
<li><a href=/series/show/>show</a></li>
<li><a href="https://example.test/peliculas/ad/">ad</a></li>
<li><a href="/peliculas/">category</a><a href="http://[invalid">broken</a></li>
</ul>`;
  expect(countResultMarkers(html)).toBe(0);
  expect(countResultMarkers(html, "text/html", context)).toBe(2);
  expect(
    countResultMarkers(
      '<ul class=miniboxs-ficha></ul><article class="download">challenge</article>',
      "text/html",
      context,
    ),
  ).toBe(0);
  expect(
    countResultMarkers('<article class="download">generic</article>', "text/html", {
      id: "other",
      siteUrl: "https://example.test",
    }),
  ).toBe(1);
});

test("bounded response capture enforces bytes and preserves streamed UTF-8", async () => {
  let oversizedRequests = 0;
  const server = Bun.serve({
    port: 0,
    fetch(request) {
      if (new URL(request.url).pathname === "/oversized") {
        oversizedRequests += 1;
        return new Response("12345");
      }
      return new Response(
        new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(new Uint8Array([0xc3]));
            controller.enqueue(new Uint8Array([0xa9]));
            controller.close();
          },
        }),
      );
    },
  });
  try {
    const url = `http://127.0.0.1:${server.port}`;
    await rejects(
      fetchTextWithRetry(`${url}/oversized`, { maxResponseBytes: 4 }),
      /response exceeds 4 bytes/,
    );
    expect(oversizedRequests).toBe(1);
    expect((await fetchTextWithRetry(`${url}/utf8`, { maxResponseBytes: 2 })).body).toBe("é");
  } finally {
    await server.stop(true);
  }
});

test("capture deadline bounds retry delays and prevents further requests", async () => {
  let requests = 0;
  const server = Bun.serve({
    port: 0,
    fetch() {
      requests += 1;
      return new Response("retry", { status: 503 });
    },
  });
  try {
    const started = performance.now();
    await rejects(
      fetchTextWithRetry(`http://127.0.0.1:${server.port}`, {
        timeoutMs: 1_000,
        maxAttempts: 3,
        deadline: started + 50,
      }),
      /capture deadline exceeded/,
    );
    expect(requests).toBe(1);
    expect(performance.now() - started).toBeLessThan(200);
    await rejects(
      fetchTextWithRetry(`http://127.0.0.1:${server.port}`, { deadline: performance.now() - 1 }),
      /capture deadline exceeded/,
    );
    expect(requests).toBe(1);
  } finally {
    await server.stop(true);
  }
});

test("HTTP 429 stops retries and preserves the service's retry window", async () => {
  let requests = 0;
  const server = Bun.serve({
    port: 0,
    fetch() {
      requests += 1;
      return new Response("rate limited", { status: 429, headers: { "retry-after": "60" } });
    },
  });
  try {
    const response = await fetchTextWithRetry(`http://127.0.0.1:${server.port}`);
    expect(response.status).toBe(429);
    expect(response.attempts).toBe(1);
    expect(response.retryAfter).toBe("60");
    expect(requests).toBe(1);
  } finally {
    await server.stop(true);
  }
});
