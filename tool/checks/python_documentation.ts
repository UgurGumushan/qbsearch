/**
 * Check handwritten plugin documentation without the generated export filter.
 * @file
 */
import { discoverPlugins } from "../core/plugins";
import { ROOT } from "../core/repo";
import type { CommandResult } from "../core/run";
import { START_MARKER, END_MARKER } from "../harden/constants";

/** Mask generated lines so Ruff sees engine APIs and reports original line numbers. */
export function documentationSource(source: string): string {
  const start = source.indexOf(START_MARKER);
  if (start < 0) return source;
  const end = source.indexOf(END_MARKER, start);
  if (end < 0) throw new Error("generated preamble start marker has no end marker");
  return (
    source.slice(0, start) +
    source.slice(start, end + END_MARKER.length).replace(/[^\r\n]/g, " ") +
    source.slice(end + END_MARKER.length)
  );
}

/** Check an engine body with the repository policy, even for temporary scaffolds. */
export async function lintPluginDocumentation(
  path: string,
  source: string,
): Promise<CommandResult> {
  // __all__ in the shared preamble exports helpers, which would otherwise hide
  // engine classes from Ruff's public-docstring rules. Do not change runtime exports.
  const child = Bun.spawn(
    [
      "ruff",
      "check",
      "--no-cache",
      "--config",
      `${ROOT}/pyproject.toml`,
      "--select",
      "D100,D101,D102,D103,D104,D105,D106,D107,D419",
      "--stdin-filename",
      path,
      "-",
    ],
    {
      cwd: ROOT,
      stdin: new TextEncoder().encode(documentationSource(source)),
      stdout: "pipe",
      stderr: "pipe",
    },
  );
  const [stdout, stderr, code] = await Promise.all([
    new Response(child.stdout).text(),
    new Response(child.stderr).text(),
    child.exited,
  ]);
  return { code, output: [stdout, stderr].filter(Boolean).join("\n").trim() };
}

/** Audit engine bodies; the normal Ruff gate still checks their complete source. */
export async function checkPythonDocumentation(): Promise<number> {
  let failed = false;
  for (const plugin of await discoverPlugins()) {
    const result = await lintPluginDocumentation(plugin, await Bun.file(plugin).text());
    if (result.code !== 0) {
      failed = true;
      console.error(result.output);
    }
  }
  return failed ? 1 : 0;
}

if (import.meta.main) process.exitCode = await checkPythonDocumentation();
