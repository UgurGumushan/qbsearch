import { existsSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { basename, join } from "node:path";
import { convertToIco } from "./image_converter";
import { ICON_DIR, EXTRA_ICON_URLS, MANIFEST } from "./constants";
import { loadCandidate } from "./candidate";
import { readPreviousManifest } from "./manifest";
import { discoverPlugins, extractUrl, hostName } from "./plugin_source";
import type { Manifest, ManifestEntry } from "./types";

function usage(): string {
  return `Usage: bun run icons

Fetches plugin favicons, converts them to ICO, and writes /tmp/icon_manifest.json.
`;
}

function newManifestEntry(stem: string): ManifestEntry {
  return {
    url: null,
    host: "",
    ico: `icons/${stem}.ico`,
    ok: false,
    error: null,
    source: null,
  };
}

async function findCandidate(stem: string, host: string, errors: string[]) {
  let candidate = await loadCandidate("direct", `https://${host}/favicon.ico`, errors);
  candidate ??= await loadCandidate(
    "google",
    `https://www.google.com/s2/favicons?domain=${host}&sz=64`,
    errors,
  );
  if (candidate === null && EXTRA_ICON_URLS[stem]) {
    candidate = await loadCandidate("wiki", EXTRA_ICON_URLS[stem], errors);
  }
  if (candidate === null) {
    const duck = await loadCandidate(
      "duckduckgo",
      `https://icons.duckduckgo.com/ip3/${host}.ico`,
      errors,
    );
    if (duck !== null) {
      if (duck.size.width < 4 || duck.size.height < 4) {
        errors.push("duckduckgo: placeholder/blank image");
      } else {
        candidate = duck;
      }
    }
  }
  if (candidate === null) {
    const horse = await loadCandidate("icon.horse", `https://icon.horse/icon/${host}`, errors);
    if (horse !== null) {
      if (horse.size.width < 4 || horse.size.height < 4) {
        errors.push("icon.horse: placeholder/blank image");
      } else {
        candidate = horse;
      }
    }
  }
  return candidate;
}

async function writeIcon(
  stem: string,
  entry: ManifestEntry,
  candidate: Awaited<ReturnType<typeof findCandidate>>,
): Promise<void> {
  if (candidate === null) {
    return;
  }
  try {
    const converted = await convertToIco(candidate.data);
    if (converted.byteLength === 0) {
      entry.error = "convert: converter returned an empty image";
      return;
    }
    await mkdir(ICON_DIR, { recursive: true });
    await writeFile(join(ICON_DIR, `${stem}.ico`), converted);
  } catch (error) {
    entry.error = `convert: ${error instanceof Error ? error.message : String(error)}`;
    return;
  }
  entry.ok = true;
  entry.source = candidate.source;
}

/** Fetch, convert, and cache all plugin icons. */
export async function makeIcons(args: string[] = []): Promise<number> {
  if (args.includes("--help") || args.includes("-h")) {
    console.log(usage());
    return 0;
  }
  if (args.length > 0) {
    console.error(`ERROR: unrecognized argument: ${args[0]}`);
    return 2;
  }

  const previous = await readPreviousManifest();
  const plugins = await discoverPlugins();
  const manifest: Manifest = {};

  for (const path of plugins) {
    const stem = basename(path, ".py");
    const icoPath = join(ICON_DIR, `${stem}.ico`);
    const previousEntry = previous[stem];
    if (existsSync(icoPath) && previousEntry?.ok && previousEntry.ico === `icons/${stem}.ico`) {
      manifest[stem] = previousEntry;
      continue;
    }

    const entry = newManifestEntry(stem);
    manifest[stem] = entry;
    const url = extractUrl(await readFile(path, "utf8"));
    if (url === null) {
      entry.error = "no url class attribute found";
      continue;
    }
    entry.url = url;
    const host = hostName(url);
    entry.host = host;
    const errors: string[] = [];
    const candidate = await findCandidate(stem, host, errors);
    if (candidate === null) {
      entry.error = errors.join("; ") || "no favicon";
      continue;
    }
    await writeIcon(stem, entry, candidate);
    if (!entry.ok && entry.error === null) {
      entry.error = errors.join("; ") || "no favicon";
    }
  }

  await writeFile(MANIFEST, JSON.stringify(manifest, null, 2) + "\n", "utf8");
  const ok = Object.values(manifest).filter((entry) => entry?.ok === true).length;
  console.log(`wrote ${ok}/${Object.keys(manifest).length} icons; manifest: ${MANIFEST}`);
  return 0;
}
