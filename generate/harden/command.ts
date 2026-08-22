import { readdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { PLUGIN_DIR } from "../../scripts/repository";
import { auditPlugin } from "../../check/harden/audit_plugin";
import { renderPlugin } from "./render_plugin";

function usage(): string {
  return `Usage: bun run harden -- [--write|--check]

Options:
  --write  Render the safety preamble into plugins
  --check  Audit plugins without editing
`;
}

/** Render or audit every installable plugin. */
export async function hardenPlugins(rawArgs: string[]): Promise<number> {
  if (rawArgs.includes("--help") || rawArgs.includes("-h")) {
    console.log(usage());
    return 0;
  }
  let write = false;
  let check = false;
  for (const argument of rawArgs) {
    if (argument === "--write") {
      write = true;
    } else if (argument === "--check") {
      check = true;
    } else {
      console.error(`unrecognized argument: ${argument}`);
      return 2;
    }
  }
  if (!write && !check) {
    console.error("choose --write or --check");
    return 2;
  }

  const pluginNames = (await readdir(PLUGIN_DIR)).filter((name) => name.endsWith(".py")).sort();
  const failures: { name: string; error: string }[] = [];
  for (const name of pluginNames) {
    const path = resolve(PLUGIN_DIR, name);
    if (write) {
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
  console.log(`Audited ${pluginNames.length} plugins successfully.`);
  return 0;
}
