import { ROOT } from "../../scripts/repository";
import { pythonCommand } from "../../scripts/process";

/** Return a concise Python AST error for a plugin, or null when valid. */
export async function syntaxError(path: string): Promise<string | null> {
  const script =
    "import ast, pathlib, sys; ast.parse(pathlib.Path(sys.argv[1]).read_text(), filename=sys.argv[1])";
  const child = Bun.spawn([...pythonCommand(), "-c", script, path], {
    cwd: ROOT,
    stdout: "pipe",
    stderr: "pipe",
  });
  const exitCode = await child.exited;
  if (exitCode === 0) {
    return null;
  }
  const stderr = await new Response(child.stderr).text();
  const detail = stderr.trim().split("\n").at(-1) ?? "invalid Python syntax";
  return `syntax error: ${detail}`;
}
