import { readFile, writeFile } from "node:fs/promises";
import { basename } from "node:path";
import { auditPlugin } from "../checks/harden/audit_plugin";
import { renderPlugin } from "./render_plugin";

import { discoverPlugins } from "../core/plugins";
import type { GenerationOptions } from "../core/args";

/** Render or audit every installable plugin. */
export async function hardenPlugins({ mode }: GenerationOptions): Promise<number> {
  const failures: { name: string; error: string }[] = [];
  const paths = await discoverPlugins();
  for (const path of paths) {
    const name = basename(path);
    if (mode === "write") {
      await writeFile(path, renderPlugin(await readFile(path, "utf8")), "utf8");
    }
    for (const error of await auditPlugin(path)) {
      failures.push({ name, error });
    }
  }

  if (failures.length > 0) {
    for (const failure of failures) {
      console.error(`${failure.name}: ${failure.error}`);
    }
    return 1;
  }
  console.log(`Audited ${paths.length} plugins successfully.`);
  return 0;
}
