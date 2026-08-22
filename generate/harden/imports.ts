import { SAFETY_PREAMBLE, SAFETY_PREAMBLE_WITH_OVERRIDE } from "./safety_preamble";
import { END_MARKER, START_MARKER } from "./constants";
import { bracketDelta, hasFinalNewline, indentation } from "./source_text";

export function ensureFutureAnnotations(source: string): string {
  if (/^from\s+__future__\s+import\s+.*\bannotations\b/m.test(source)) {
    return source;
  }

  const trailingNewline = hasFinalNewline(source);
  const lines = source.split(/\r?\n/);
  if (trailingNewline) {
    lines.pop();
  }

  let insertLine = 0;
  while (
    insertLine < lines.length &&
    (lines[insertLine].startsWith("#!") || /^#.*coding[:=]/.test(lines[insertLine]))
  ) {
    insertLine += 1;
  }

  const firstBodyLine = lines[insertLine] ?? "";
  const docstringMatch = /^\s*(?:[rubfRUBF]{0,2})("""|''')/.exec(firstBodyLine);
  if (docstringMatch) {
    const delimiter = docstringMatch[1];
    let closingLine = insertLine;
    const firstRemainder = firstBodyLine.slice(docstringMatch.index + docstringMatch[0].length);
    if (!firstRemainder.includes(delimiter)) {
      while (closingLine + 1 < lines.length && !lines[closingLine + 1].includes(delimiter)) {
        closingLine += 1;
      }
      if (closingLine + 1 < lines.length) {
        closingLine += 1;
      }
    }
    insertLine = closingLine + 1;
  }

  const prefix = insertLine > 0 && lines[insertLine - 1]?.trim() ? [""] : [];
  const suffix = insertLine >= lines.length || !lines[insertLine]?.trim() ? [""] : [];
  lines.splice(insertLine, 0, ...prefix, "from __future__ import annotations", ...suffix);
  return lines.join("\n") + "\n";
}

export function aliasRetrieveImports(source: string): string {
  const trailingNewline = hasFinalNewline(source);
  const lines = source.split(/\r?\n/);
  if (trailingNewline) {
    lines.pop();
  }

  return (
    lines
      .map((originalLine) => {
        let line = originalLine;
        if (line.includes("retrieve_url as _qbt_retrieve_url")) {
          line = line.replace(
            "retrieve_url as _qbt_retrieve_url",
            "retrieve_url as _qbt_helper_retrieve_url",
          );
        } else if (
          line.startsWith("from helpers import ") &&
          line.includes("retrieve_url") &&
          !line.includes("retrieve_url as _qbt_helper_retrieve_url")
        ) {
          line = line.replace(/\bretrieve_url\b/, "retrieve_url as _qbt_helper_retrieve_url");
        }
        if (line.includes("retrieve_url as _qbt_helper_retrieve_url")) {
          line = line.replace("  # noqa: F401", "");
        }
        return line;
      })
      .join("\n") + (trailingNewline ? "\n" : "")
  );
}

export function lastTopLevelImportEnd(source: string): number {
  const lines = source.split(/\r?\n/);
  if (hasFinalNewline(source)) {
    lines.pop();
  }

  let lastEnd = 0;
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (indentation(line) !== 0 || !/^\s*(?:import\b|from\b.*\bimport\b)/.test(line)) {
      continue;
    }

    let depth = bracketDelta(line);
    let end = index;
    while (depth > 0 || lines[end].trimEnd().endsWith("\\")) {
      if (end + 1 >= lines.length) {
        break;
      }
      end += 1;
      depth += bracketDelta(lines[end]);
    }
    lastEnd = end + 1;
    index = end;
  }
  return lastEnd;
}

export function insertAfterImports(source: string, includeOverride: boolean): string {
  const lines = source.split(/\r?\n/);
  if (hasFinalNewline(source)) {
    lines.pop();
  }
  const helperFallback =
    source.includes("retrieve_url as _qbt_helper_retrieve_url") ||
    /_qbt_helper_retrieve_url\s*=\s*None/.test(source)
      ? []
      : ["_qbt_helper_retrieve_url = None"];
  const preamble = includeOverride ? SAFETY_PREAMBLE_WITH_OVERRIDE : SAFETY_PREAMBLE;
  let insertionLine = lastTopLevelImportEnd(source);
  let cursor = insertionLine;
  while (cursor < lines.length && lines[cursor].trim() === "") {
    cursor += 1;
  }
  if (/^_qbt_helper_retrieve_url\s*=\s*None\s*$/.test(lines[cursor] ?? "")) {
    while (
      cursor < lines.length &&
      /^_qbt_helper_retrieve_url\s*=\s*None\s*$/.test(lines[cursor])
    ) {
      cursor += 1;
      while (cursor < lines.length && lines[cursor].trim() === "") {
        cursor += 1;
      }
    }
    insertionLine = cursor;
  }
  lines.splice(insertionLine, 0, "", ...helperFallback, ...preamble.split("\n"), "");
  return lines.join("\n") + "\n";
}

export function replaceGeneratedPreamble(source: string, includeOverride: boolean): string {
  const preamble = includeOverride ? SAFETY_PREAMBLE_WITH_OVERRIDE : SAFETY_PREAMBLE;
  const startMarker = source.indexOf(START_MARKER);
  const endMarker = source.indexOf(END_MARKER, startMarker);
  if (startMarker < 0 || endMarker < 0) {
    throw new Error("generated preamble start marker has no end marker");
  }
  return source.slice(0, startMarker) + preamble + source.slice(endMarker + END_MARKER.length);
}
