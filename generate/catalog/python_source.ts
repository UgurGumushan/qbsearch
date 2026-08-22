import type { ClassBody } from "./types";

const ASSIGNMENT =
  /^[ \t]*([A-Za-z_][A-Za-z0-9_]*)(?:[ \t]*:[^=]+)?[ \t]*=[ \t]*(?:"((?:\\.|[^"\\])*)"|'((?:\\.|[^'\\])*)'|([A-Za-z_][A-Za-z0-9_]*))[ \t]*(?:#.*)?$/;
const CLASS_DECLARATION = /^class[ \t]+([A-Za-z_][A-Za-z0-9_]*)\b/;
const CLASS_ATTRIBUTE =
  /^(name|url)(?:[ \t]*:[^=]+)?[ \t]*=[ \t]*(?:"((?:\\.|[^"\\])*)"|'((?:\\.|[^'\\])*)'|([A-Za-z_][A-Za-z0-9_]*))[ \t]*(?:#.*)?$/;

export const CLASS_ATTRIBUTES = CLASS_ATTRIBUTE;

function capture(match: RegExpMatchArray, index: number): string | undefined {
  return match[index];
}

export function decodePythonString(value: string): string {
  return value.replace(/\\([\\'"nrt])/g, (_match, character: string) => {
    switch (character) {
      case "n":
        return "\n";
      case "r":
        return "\r";
      case "t":
        return "\t";
      default:
        return character;
    }
  });
}

export function literalValue(match: RegExpMatchArray): string | null {
  const value = capture(match, 2) ?? capture(match, 3);
  return value === undefined ? null : decodePythonString(value);
}

export function assignmentValue(
  match: RegExpMatchArray,
  constants: Map<string, string>,
): string | null {
  const literal = literalValue(match);
  const constant = capture(match, 4);
  return literal ?? (constant === undefined ? null : (constants.get(constant) ?? null));
}

export function topLevelConstants(lines: string[]): Map<string, string> {
  const constants = new Map<string, string>();
  for (const line of lines) {
    if (/^\s/.test(line)) {
      continue;
    }
    const match = ASSIGNMENT.exec(line);
    if (!match) {
      continue;
    }
    const value = assignmentValue(match, constants);
    if (value !== null) {
      constants.set(match[1], value);
    }
  }
  return constants;
}

export function classBodies(lines: string[]): Map<string, ClassBody> {
  const classes = new Map<string, ClassBody>();
  for (let index = 0; index < lines.length; index += 1) {
    const match = CLASS_DECLARATION.exec(lines[index]);
    if (!match) {
      continue;
    }
    const body: string[] = [];
    let end = index + 1;
    for (; end < lines.length; end += 1) {
      const line = lines[end];
      if (line.length > 0 && !/^\s/.test(line) && !line.startsWith("#")) {
        break;
      }
      body.push(line);
    }
    const firstStatement = body.find((line) => line.trim() && !line.trim().startsWith("#"));
    const indent = firstStatement?.match(/^([ \t]+)/)?.[1] ?? "    ";
    classes.set(match[1], { lines: body, indent });
    index = end - 1;
  }
  return classes;
}
