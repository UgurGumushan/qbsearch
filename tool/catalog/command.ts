/**
 * Coordinate catalog validation and generated catalog documentation.
 * @file
 */
import { relative } from "node:path";
import { DOCS_PATH, ROOT } from "../core/repo";
import { validateCatalog } from "../checks/catalog_validation";
import { catalogEntries, loadCatalog } from "./storage";
import { renderPluginDocs } from "./render_docs";
import type { GenerationOptions } from "../core/args";

/** Validate the catalog and render or audit its documentation. */
export async function generatePluginCatalog({
  mode,
  strict = false,
}: GenerationOptions): Promise<number> {
  try {
    const catalog = await loadCatalog();
    const { errors, warnings } = await validateCatalog(catalog);
    for (const error of errors) console.error("ERROR: " + error);
    for (const warning of warnings) console.warn("WARNING: " + warning);
    if (errors.length > 0 || (strict && warnings.length > 0)) return 1;
    const expected = renderPluginDocs(catalog);
    if (mode === "write") {
      await Bun.write(DOCS_PATH, expected);
      console.log("Wrote " + relative(ROOT, DOCS_PATH));
    } else if (
      !(await Bun.file(DOCS_PATH).exists()) ||
      (await Bun.file(DOCS_PATH).text()) !== expected
    ) {
      console.error(
        "ERROR: documentation/PLUGINS.md is out of date; run bun run gen -- --write --only catalog",
      );
      return 1;
    }
    console.log(`Catalog valid: ${catalogEntries(catalog).length} plugins.`);
    return 0;
  } catch (error) {
    console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
    return 1;
  }
}
