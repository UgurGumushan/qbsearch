import { relative } from "node:path";
import { CATALOG_PATH, DOCS_PATH, ROOT } from "../../scripts/repository";
import { validateCatalog } from "../../check/catalog_validation";
import {
  bootstrapCatalog,
  catalogEntries,
  loadCatalog,
  refreshCatalog,
  renderPluginDocs,
  writeCatalog,
} from "./index";
import type { Catalog } from "./types";

interface CatalogArguments {
  bootstrap: boolean;
  write: boolean;
  docs: boolean;
  refresh: boolean;
  check: boolean;
}

function usage(): string {
  return `Usage: bun run catalog -- [options]

Options:
  --bootstrap  Create a catalog from the existing plugins and query profile
  --write      Write the catalog when used with --bootstrap
  --docs       Write documentation/PLUGINS.md
  --refresh    Fill catalog license fields from LICENSE.md
  --check      Validate the catalog and generated index without changing files
`;
}

function parseArguments(args: string[]): CatalogArguments | null {
  const parsed: CatalogArguments = {
    bootstrap: false,
    write: false,
    docs: false,
    refresh: false,
    check: false,
  };
  for (const argument of args) {
    switch (argument) {
      case "--bootstrap":
        parsed.bootstrap = true;
        break;
      case "--write":
        parsed.write = true;
        break;
      case "--docs":
        parsed.docs = true;
        break;
      case "--refresh":
        parsed.refresh = true;
        break;
      case "--check":
        parsed.check = true;
        break;
      case "--help":
      case "-h":
        console.log(usage());
        return null;
      default:
        throw new Error(`unrecognized argument: ${argument}`);
    }
  }
  return parsed;
}

async function reportValidationErrors(catalog: Catalog): Promise<boolean> {
  const errors = await validateCatalog(catalog);
  for (const error of errors) {
    console.error("ERROR: " + error);
  }
  return errors.length > 0;
}

/** Execute catalog generation, refresh, documentation, and check modes. */
export async function generatePluginCatalog(rawArgs: string[]): Promise<number> {
  try {
    const args = parseArguments(rawArgs.length > 0 ? rawArgs : ["--docs"]);
    if (args === null) {
      return 0;
    }
    if (args.bootstrap && args.refresh) {
      throw new Error("choose only one of --bootstrap and --refresh");
    }

    let catalog: Catalog;
    if (args.bootstrap) {
      if (await Bun.file(CATALOG_PATH).exists()) {
        console.error(
          "ERROR: catalog already exists; edit it directly instead of bootstrapping again.",
        );
        return 1;
      }
      catalog = await bootstrapCatalog();
      if (await reportValidationErrors(catalog)) {
        return 1;
      }
      if (args.write) {
        await writeCatalog(catalog);
        console.log("Wrote " + relative(ROOT, CATALOG_PATH));
      }
    } else {
      try {
        catalog = await loadCatalog();
      } catch (error) {
        console.error("ERROR: " + (error instanceof Error ? error.message : String(error)));
        return 1;
      }
      if (args.refresh) {
        catalog = await refreshCatalog(catalog);
        await writeCatalog(catalog);
        console.log("Refreshed " + relative(ROOT, CATALOG_PATH));
      }
    }

    if (await reportValidationErrors(catalog)) {
      return 1;
    }

    if (args.docs) {
      await Bun.write(DOCS_PATH, renderPluginDocs(catalog));
      console.log("Wrote " + relative(ROOT, DOCS_PATH));
    } else if (args.check) {
      const expected = renderPluginDocs(catalog);
      if (
        !(await Bun.file(DOCS_PATH).exists()) ||
        (await Bun.file(DOCS_PATH).text()) !== expected
      ) {
        console.error("ERROR: documentation/PLUGINS.md is out of date; run with --docs");
        return 1;
      }
    }

    console.log(`Catalog valid: ${catalogEntries(catalog).length} plugins.`);
    return 0;
  } catch (error) {
    console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
    return 2;
  }
}
