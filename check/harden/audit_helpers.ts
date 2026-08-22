import { END_MARKER } from "../../generate/harden/constants";
import { indentation, isCodeLine } from "../../generate/harden/source_text";

export function lineNumberAt(source: string, offset: number): number {
  return source.slice(0, offset).split("\n").length;
}

export function callText(source: string, openOffset: number): string {
  let depth = 0;
  let quote: string | null = null;
  let escaped = false;
  for (let offset = openOffset; offset < source.length; offset += 1) {
    const character = source[offset];
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
      depth += 1;
    } else if (character === ")") {
      depth -= 1;
      if (depth === 0) {
        return source.slice(openOffset, offset + 1);
      }
    }
  }
  return source.slice(openOffset);
}

export function preambleLine(source: string): number {
  const endOffset = source.indexOf(END_MARKER);
  return endOffset < 0 ? 0 : lineNumberAt(source, endOffset);
}

export function functionBody(lines: string[], line: number): string {
  let functionLine = -1;
  let functionIndent = Number.POSITIVE_INFINITY;
  for (let index = line; index >= 0; index -= 1) {
    const match = /^(\s*)(?:async\s+)?def\s+\w+\s*\(/.exec(lines[index]);
    if (match && indentation(lines[index]) < indentation(lines[line])) {
      functionLine = index;
      functionIndent = indentation(lines[index]);
      break;
    }
  }
  if (functionLine < 0) {
    return "";
  }
  let end = lines.length;
  for (let index = functionLine + 1; index < lines.length; index += 1) {
    if (isCodeLine(lines[index]) && indentation(lines[index]) <= functionIndent) {
      end = index;
      break;
    }
  }
  return lines.slice(functionLine, end).join("\n");
}
