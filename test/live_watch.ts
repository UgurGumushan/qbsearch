/**
 * Watched live-test entrypoint.
 *
 * The coordinator reads the catalog and standalone Python engines at runtime.
 * Keep both inputs in Bun's module graph so `bun --watch` restarts this process
 * when either one changes.
 */
import "../catalog/plugins.json" with { type: "text" };
import "./plugin_sources";
import { checkCatalog } from "../check/catalog";
import { runLive } from "./live";

if (import.meta.main) {
  const catalogExit = await checkCatalog();
  process.exitCode = catalogExit === 0 ? await runLive(Bun.argv.slice(2)) : catalogExit;
}
