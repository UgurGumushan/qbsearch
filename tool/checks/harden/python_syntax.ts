/**
 * Check engine syntax using the configured Python interpreter.
 * @file
 */
import { runPythonCaptured } from "../../core/run";

/** Return a concise Python AST error for a plugin, or null when valid. */
export async function syntaxError(path: string): Promise<string | null> {
  const script =
    "import ast, pathlib, sys; ast.parse(pathlib.Path(sys.argv[1]).read_bytes(), filename=sys.argv[1])";
  const result = await runPythonCaptured(["-c", script, path]);
  if (result.code === 0) {
    return null;
  }
  const detail = result.output.trim().split("\n").at(-1) ?? "invalid Python syntax";
  return `syntax error: ${detail}`;
}
