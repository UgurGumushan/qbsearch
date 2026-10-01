import { generatePluginCatalog } from "../catalog/command";
import { hardenPlugins } from "../harden/command";
import { validPluginIdentifier } from "../core/python-parse";
import { renderPluginTemplate } from "../generators/plugin-template";

/** Validate standalone plugins without editing (catalog + preamble audit). */
export async function validatePlugins(): Promise<number> {
  const catalogExit = await generatePluginCatalog(["--check"]);
  if (catalogExit !== 0) {
    return catalogExit;
  }
  return hardenPlugins(["--check"]);
}

/** plugin --validate audits; --new scaffolds a slim engine (preamble added by gen). */
export async function runPluginCommand(rawArgs: string[]): Promise<number> {
  if (rawArgs.includes("--help") || rawArgs.includes("-h") || rawArgs.length === 0) {
    console.log(`Usage: bun run plugin -- [--validate|--new <id> --kind json|html]

  --validate            Audit catalog parity + safety preambles (no edits)
  --new <id>            Scaffold plugins/<id>.py from the minimal template
    --kind json|html    Template flavor (default: json)
    --site URL          Override the default site URL
`);
    return 0;
  }
  if (rawArgs.length === 1 && rawArgs[0] === "--validate") {
    return validatePlugins();
  }
  try {
    const values = new Map<string, string>();
    for (let index = 0; index < rawArgs.length; index += 2) {
      const option = rawArgs[index];
      const value = rawArgs[index + 1];
      if (!["--new", "--kind", "--site"].includes(option) || values.has(option)) {
        throw new Error(`unrecognized or repeated plugin argument: ${option}`);
      }
      if (!value || value.startsWith("--")) {
        throw new Error(`${option} requires a value`);
      }
      values.set(option, value);
    }
    const id = values.get("--new");
    if (!id || !validPluginIdentifier(id)) {
      throw new Error(
        "--new requires a Python identifier (lowercase letters, digits, _; no keywords)",
      );
    }
    const kind = values.get("--kind") ?? "json";
    if (kind !== "json" && kind !== "html") {
      throw new Error(`unrecognized --kind: ${kind}`);
    }
    const site = values.get("--site") ?? "https://example.com";
    // Reject controls before URL parsing, which would otherwise discard some of them.
    for (const char of site) {
      if (char.charCodeAt(0) <= 32 || char.charCodeAt(0) === 127) {
        throw new Error("--site requires an HTTP(S) URL without whitespace or controls");
      }
    }
    const parsed = new URL(site);
    if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password) {
      throw new Error("--site requires an HTTP(S) URL without credentials");
    }
    const path = `plugins/${id}.py`;
    if (await Bun.file(path).exists()) {
      console.error(`${path} already exists`);
      return 1;
    }
    await Bun.write(path, renderPluginTemplate(kind, id, site));
    console.log(`Created ${path} (${kind} template). Next: bun run gen -- --write --only harden`);
    return 0;
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    return 2;
  }
}
