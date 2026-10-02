/** Bounded functional evidence for release candidates; this is not an offline gate. */
import { createHash } from "node:crypto";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { ROOT } from "../tool/core/repo";
import { fetchTextWithRetry } from "./live/http";
import { CAPTURE_LIMITS, runFunctionalPass } from "./support/parser_capture";
import type { ParserPlugin } from "./support/parser_replay";

const output = resolve(ROOT, "working", "release-live");
await mkdir(output, { recursive: true });
const functional: { plugin: ParserPlugin; clean: boolean; path: string; error?: string }[] = [];
for (const plugin of [
  "elitetorrent",
  "darklibria",
  "uniondht",
  "dmhy",
  "audiobookbay",
  "torrentdownloads",
  "ali213",
  "pirateiro",
] as const) {
  try {
    const result = await runFunctionalPass(plugin, output);
    functional.push({ plugin, clean: result.report.clean, path: result.path });
    console.log(`${plugin}: ${result.report.clean ? "usable paired capture" : "unverified"}`);
    for (const item of result.report.cases)
      console.log(
        `  ${item.query}: ${item.error ?? `${item.replay?.records.length ?? 0} records`}`,
      );
  } catch (error) {
    functional.push({ plugin, clean: false, path: "", error: String(error) });
    console.error(`${plugin}: ${String(error)}`);
  }
}

const pagination: { query: string; hashes: string[]; counts: number[]; error?: string }[] = [];
let rateLimited = false;
for (const query of ["one piece", "naruto"]) {
  const observation: (typeof pagination)[number] = { query, hashes: [], counts: [] };
  const deadline = performance.now() + CAPTURE_LIMITS.deadlineMs;
  try {
    if (rateLimited) throw new Error("skipped after HTTP 429; respect the service retry window");
    for (let page = 0; page < 6; page += 1) {
      const url = `https://subsplease.org/api/?f=search&tz=UTC&s=${encodeURIComponent(query)}&p=${page}`;
      const response = await fetchTextWithRetry(url, { ...CAPTURE_LIMITS, deadline });
      await Bun.write(
        resolve(output, `subsplease-${encodeURIComponent(query)}-${page}.json`),
        JSON.stringify({ requestedUrl: url, ...response }, null, 2),
      );
      if (response.status === 429) rateLimited = true;
      if (response.status >= 400) throw new Error(`HTTP ${response.status}`);
      const value: unknown = JSON.parse(response.body);
      if (!value || typeof value !== "object" || Array.isArray(value))
        throw new Error("search response is not an object");
      const entries = Object.entries(value).sort(([a], [b]) => a.localeCompare(b));
      if (!entries.length) throw new Error("empty search cannot establish a pagination baseline");
      observation.counts.push(entries.length);
      observation.hashes.push(createHash("sha256").update(JSON.stringify(entries)).digest("hex"));
    }
  } catch (error) {
    observation.error = String(error);
    if (observation.error.includes("429")) rateLimited = true;
  }
  pagination.push(observation);
  console.log(
    `subsplease/${query}: ${observation.error ?? `${observation.counts.join("/")} rows`}`,
  );
}
await Bun.write(
  resolve(output, "report.json"),
  `${JSON.stringify({ createdAt: new Date().toISOString(), functional, pagination }, null, 2)}\n`,
);
