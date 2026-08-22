import { mkdir } from "node:fs/promises";
import { join, resolve } from "node:path";
import { UPSTREAM_DIR, UPSTREAM_URLS } from "./constants";
import { fetchSnapshot, pluginStem } from "./fetch_snapshot";

function usage(): string {
  return `Usage: bun run upstream

Downloads the configured public plugin snapshots into external/upstream/.
Set QBSEARCH_UPSTREAM_DIR to override the destination directory.
`;
}

function upstreamDirectory(): string {
  const configured = process.env.QBSEARCH_UPSTREAM_DIR;
  return configured ? resolve(configured) : UPSTREAM_DIR;
}

/** Import public upstream plugin snapshots into the isolated provenance tree. */
export async function importUpstreamPlugins(args: string[] = []): Promise<number> {
  if (args.includes("--help") || args.includes("-h")) {
    console.log(usage());
    return 0;
  }
  if (args.length > 0) {
    console.error(`ERROR: unrecognized argument: ${args[0]}`);
    return 2;
  }

  const upstream = upstreamDirectory();
  await mkdir(upstream, { recursive: true });
  console.log(`=== Downloading ${UPSTREAM_URLS.length} free plugins ===`);

  let ok = 0;
  let failed = 0;
  for (const url of UPSTREAM_URLS) {
    const outputPath = join(upstream, `${pluginStem(url)}.py`);
    if (await fetchSnapshot(url, outputPath)) {
      ok += 1;
    } else {
      failed += 1;
      console.log(`FAIL: ${url}`);
    }
  }

  console.log(`\n=== Result: ${ok} OK, ${failed} FAIL ===`);
  if (failed === 0) {
    console.log("All downloads succeeded.");
  }
  return failed === 0 ? 0 : 1;
}
