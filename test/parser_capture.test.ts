import { rejects } from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { expect, spyOn, test } from "bun:test";
import { FIXTURES_DIR } from "../tool/core/repo";
import { CAPTURE_LIMITS, captureParserCase, runFunctionalPass } from "./support/parser_capture";
import type { ParserCase } from "./support/parser_replay";

function mockFetch(handler: (input: Parameters<typeof globalThis.fetch>[0]) => Response) {
  const implementation = Object.assign(
    (input: Parameters<typeof globalThis.fetch>[0]) => Promise.resolve(handler(input)),
    { preconnect: globalThis.fetch.preconnect },
  );
  return spyOn(globalThis, "fetch").mockImplementation(implementation);
}

test("failed captures preserve partial responses and rate-limit evidence", async () => {
  const directory = await mkdtemp(resolve(tmpdir(), "qbsearch-capture-"));
  const fixture = (await Bun.file(
    resolve(FIXTURES_DIR, "parsers", "bitsearch.json"),
  ).json()) as ParserCase;
  let requests = 0;
  const fetch = mockFetch((input) => {
    const url = input instanceof Request ? input.url : input.toString();
    requests += 1;
    return url.endsWith("page=1")
      ? new Response(fixture.responses[url])
      : new Response("rate limited", { status: 429, headers: { "retry-after": "60" } });
  });
  try {
    await rejects(
      captureParserCase("bitsearch", "inception", directory),
      /HTTP 429.*Retry-After: 60/,
    );
    expect(requests).toBe(2);
    const saved = (await Bun.file(resolve(directory, "bitsearch-inception.json")).json()) as {
      responses: Record<string, string>;
      evidence: { status: number; attempts: number; retryAfter: string | null }[];
    };
    expect(Object.keys(saved.responses).length).toBe(2);
    expect(saved.evidence[1]).toMatchObject({ status: 429, attempts: 1, retryAfter: "60" });
  } finally {
    fetch.mockRestore();
    await rm(directory, { recursive: true, force: true });
  }
});

test("Solid Torrents captures its own URLs and bounds modern and legacy listings", async () => {
  for (const banner of ['Found <span class="font-semibold">999</span>', "<b>999</b>"]) {
    const directory = await mkdtemp(resolve(tmpdir(), "qbsearch-solid-capture-"));
    const requested: string[] = [];
    const fetch = mockFetch((input) => {
      const url = input instanceof Request ? input.url : input.toString();
      requested.push(url);
      return new Response(banner);
    });
    try {
      const capture = await captureParserCase("solidtorrents", "ubuntu", directory);
      expect(requested).toEqual([
        "https://solidtorrents.to/search?q=ubuntu&page=1",
        "https://solidtorrents.to/search?q=ubuntu&page=2",
      ]);
      const fixture = (await Bun.file(capture.path).json()) as ParserCase;
      expect(fixture.plugin).toBe("solidtorrents");
      expect(fixture.maxPages).toBe(2);
      expect(fixture.maxDetails).toBe(CAPTURE_LIMITS.maxResults);
      expect(Object.keys(fixture.responses)).toEqual(requested);
    } finally {
      fetch.mockRestore();
      await rm(directory, { recursive: true, force: true });
    }
  }
});

test("a rate-limited recovery pass stops subsequent queries and cannot qualify as clean", async () => {
  const directory = await mkdtemp(resolve(tmpdir(), "qbsearch-pass-"));
  let requests = 0;
  const fetch = mockFetch(() => {
    requests += 1;
    return new Response("rate limited", { status: 429, headers: { "retry-after": "60" } });
  });
  try {
    const { path, report } = await runFunctionalPass("bitsearch", directory);
    expect(requests).toBe(1);
    expect(report.clean).toBe(false);
    expect(report.cases[0].capture?.responses[0]).toMatchObject({ status: 429, retryAfter: "60" });
    expect(report.cases[0].error).toContain("HTTP 429");
    expect(report.cases[1].error).toContain("skipped after HTTP 429");
    expect(await Bun.file(path).exists()).toBe(true);
  } finally {
    fetch.mockRestore();
    await rm(directory, { recursive: true, force: true });
  }
});

for (const { description, body } of [
  {
    description: "interrupted",
    body: () =>
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.error(new Error("response body interrupted"));
        },
      }),
  },
  {
    description: "oversized",
    body: () => new Uint8Array(CAPTURE_LIMITS.maxResponseBytes + 1),
  },
]) {
  test(`an ${description} HTTP 429 body preserves the retry window and stops recovery`, async () => {
    const directory = await mkdtemp(resolve(tmpdir(), "qbsearch-rate-limit-"));
    let requests = 0;
    const fetch = mockFetch(() => {
      requests += 1;
      return new Response(body(), { status: 429, headers: { "retry-after": "60" } });
    });
    try {
      const { report } = await runFunctionalPass("bitsearch", directory);
      expect(requests).toBe(1);
      expect(report.clean).toBe(false);
      expect(report.cases[0].capture?.responses[0]).toMatchObject({
        status: 429,
        attempts: 1,
        bytes: 0,
        retryAfter: "60",
      });
      expect(report.cases[0].error).toContain("HTTP 429");
      expect(report.cases[1].error).toContain("skipped after HTTP 429");
      const path = report.cases[0].capture?.path;
      expect(path).toBeDefined();
      if (path) {
        const saved = (await Bun.file(path).json()) as ParserCase;
        expect(Object.values(saved.responses)).toEqual([""]);
      }
    } finally {
      fetch.mockRestore();
      await rm(directory, { recursive: true, force: true });
    }
  });
}
