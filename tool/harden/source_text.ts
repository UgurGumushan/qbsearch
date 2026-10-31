/**
 * Preserve Python source layout during preamble generation.
 * @file
 */
/** Test whether source ends with the newline preserved by generators. */
export function hasFinalNewline(source: string): boolean {
  return source.endsWith("\n");
}

/** Measure leading indentation with tabs treated as four spaces. */
export function indentation(line: string): number {
  const prefix = /^[ \t]*/.exec(line)?.[0] ?? "";
  return prefix.replaceAll("\t", "    ").length;
}

/** Distinguish executable lines from blank lines and comments. */
export function isCodeLine(line: string): boolean {
  const trimmed = line.trim();
  return trimmed.length > 0 && !trimmed.startsWith("#");
}

/** Count parentheses outside quoted Python strings. */
export function bracketDelta(line: string): number {
  let delta = 0;
  let quote: string | null = null;
  let escaped = false;
  for (const character of line) {
    if (escaped) {
      escaped = false;
      continue;
    }
    if (character === "\\" && quote) {
      escaped = true;
      continue;
    }
    if (quote) {
      if (character === quote) {
        quote = null;
      }
      continue;
    }
    if (character === '"' || character === "'") {
      quote = character;
    } else if (character === "(") {
      delta += 1;
    } else if (character === ")") {
      delta -= 1;
    }
  }
  return delta;
}
