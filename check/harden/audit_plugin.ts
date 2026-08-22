import { readFile } from "node:fs/promises";
import { END_MARKER, START_MARKER } from "../../generate/harden/constants";
import { callText, functionBody, lineNumberAt, preambleLine } from "./audit_helpers";
import { syntaxError } from "./python_syntax";

/** Audit one standalone engine for generated helpers and bounded operations. */
export async function auditPlugin(path: string): Promise<string[]> {
  const source = await readFile(path, "utf8");
  const errors: string[] = [];
  if (!source.includes(START_MARKER) || !source.includes(END_MARKER)) {
    errors.push("missing generated safety preamble");
  }
  for (const constant of ["HTTP_TIMEOUT", "MAX_ATTEMPTS", "RETRY_DELAY", "MAX_WORKERS"]) {
    if (!new RegExp(`^\\s*${constant}\\s*=`, "m").test(source)) {
      errors.push(`missing ${constant}`);
    }
  }

  const syntax = await syntaxError(path);
  if (syntax) {
    return [...errors, syntax];
  }

  const preambleEndLine = preambleLine(source);
  const lines = source.split(/\r?\n/);
  const afterPreamble = (line: number) => line + 1 > preambleEndLine;

  for (const match of source.matchAll(/\b(?:urlopen|_qbt_urlopen)\s*\(/g)) {
    const line = lineNumberAt(source, match.index);
    if (
      afterPreamble(line) &&
      !/\btimeout\s*=/.test(callText(source, match.index + match[0].length - 1))
    ) {
      errors.push(`line ${line}: urlopen without timeout`);
    }
  }

  for (const match of source.matchAll(
    /\bThread\s*\(|\b(?:[A-Za-z_]\w*\.)?ThreadPoolExecutor\s*\(/g,
  )) {
    const line = lineNumberAt(source, match.index);
    if (!afterPreamble(line)) {
      continue;
    }
    const call = callText(source, match.index + match[0].length - 1);
    if (/\bThread\s*\(/.test(match[0])) {
      errors.push(`line ${line}: raw thread creation`);
    } else if (!/\bmax_workers\s*=/.test(call)) {
      errors.push(`line ${line}: executor without max_workers`);
    }
  }

  for (let index = 0; index < lines.length; index += 1) {
    const line = index + 1;
    if (!afterPreamble(line)) {
      continue;
    }
    if (/^\s*while\s+True\s*:/.test(lines[index])) {
      errors.push(`line ${line}: unbounded while True`);
    }
    const pagination = /^\s*while\b.*\b(?:page|pages|lastPage|total_results)\b/.test(lines[index]);
    if (pagination && !functionBody(lines, index).includes("MAX_PAGES")) {
      errors.push(`line ${line}: pagination loop lacks MAX_PAGES`);
    }
  }

  return [...new Set(errors)].sort();
}
