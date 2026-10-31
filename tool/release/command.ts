/**
 * Validate and assemble installable release artifacts.
 * @file
 */
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { zipSync } from "fflate";
import { installableCatalogEntries, loadCatalog } from "../catalog/storage";
import { archivePath, manifestText } from "./archive";
import { archiveSources } from "./sources";
import { homedir } from "node:os";
import type { ReleaseOptions } from "./types";
import { ROOT } from "./constants";

/** Build a self-contained release archive from the checked-in catalog. */
export async function buildRelease(args: ReleaseOptions): Promise<number> {
  try {
    if (!args.version || /[\\/:*?"<>|]/u.test(args.version)) {
      throw new Error("--version contains invalid archive characters");
    }

    const entries = installableCatalogEntries(await loadCatalog());
    const prefix = `qbsearch-${args.version}`;
    const sources = await archiveSources(entries);
    const archiveContents: Record<string, Uint8Array> = {};
    for (const source of sources) {
      archiveContents[archivePath(prefix, source)] = await Bun.file(source).bytes();
    }
    archiveContents[`${prefix}/release-manifest.json`] = new TextEncoder().encode(
      manifestText(args.version, entries),
    );

    const output = resolve(ROOT, args.output.replace(/^~(?=$|[\\/])/, homedir()));
    await mkdir(dirname(output), { recursive: true });
    await Bun.write(output, zipSync(archiveContents, { level: 6 }));
    console.log(`Built ${output} with ${entries.length} plugins.`);
    return 0;
  } catch (error) {
    console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
    return 1;
  }
}
