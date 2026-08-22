import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { zipSync } from "fflate";
import { installableCatalogEntries, loadCatalog } from "../generate/catalog";
import { archivePath, manifestText } from "./archive";
import { archiveSources } from "./sources";
import { expandHome, parseArguments, usage } from "./arguments";
import { ROOT } from "./constants";

/** Build a self-contained release archive from the checked-in catalog. */
export async function buildRelease(rawArgs: string[]): Promise<number> {
  try {
    const args = parseArguments(rawArgs);
    if (args.help) {
      console.log(usage());
      return 0;
    }
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

    const output = resolve(ROOT, expandHome(args.output));
    await mkdir(dirname(output), { recursive: true });
    await Bun.write(output, zipSync(archiveContents, { level: 6 }));
    console.log(`Built ${output} with ${entries.length} plugins.`);
    return 0;
  } catch (error) {
    console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
    return 1;
  }
}
