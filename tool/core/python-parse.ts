/** Single Python-source parser for qBittorrent standalone engines. */
export interface ClassBody {
  lines: string[];
  indent: string;
}

export interface PluginMetadata {
  name: string;
  site_url: string;
}

const ASSIGNMENT =
  /^[ \t]*([A-Za-z_][A-Za-z0-9_]*)(?:[ \t]*:[^=]+)?[ \t]*=[ \t]*(?:"((?:\\.|[^"\\])*)"|'((?:\\.|[^'\\])*)'|([A-Za-z_][A-Za-z0-9_]*))[ \t]*(?:#.*)?$/;
const CLASS_DECLARATION = /^class[ \t]+([A-Za-z_][A-Za-z0-9_]*)\b/;
const CLASS_ATTRIBUTE =
  /^(name|url)(?:[ \t]*:[^=]+)?[ \t]*=[ \t]*(?:"((?:\\.|[^"\\])*)"|'((?:\\.|[^'\\])*)'|([A-Za-z_][A-Za-z0-9_]*))[ \t]*(?:#.*)?$/;
const VERSION_LINE = /^#\s*VERSION:\s*([0-9]+(?:\.[0-9]+)+)\s*$/m;
const SEARCH_METHOD = /^[ \t]+def\s+search\s*\(/m;

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

export function splitLines(source: string): string[] {
  return source.split(/\r?\n/);
}

/** Extract the qBittorrent engine class name, supporting `<id> = <Class>` aliases. */
export function engineClassName(lines: string[], stem: string): string {
  const classes = classBodies(lines);
  if (classes.has(stem)) {
    return stem;
  }
  for (const line of lines) {
    if (/^\s/.test(line)) {
      continue;
    }
    const alias = /^([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*$/.exec(
      line,
    );
    if (alias?.[1] === stem && alias[2] && classes.has(alias[2])) {
      return alias[2];
    }
  }
  throw new Error("could not find the qBittorrent engine class");
}

/** Read name/url metadata from source text (no filesystem access). */
export function metadataFromSource(source: string, stem: string): PluginMetadata {
  const lines = splitLines(source);
  const constants = topLevelConstants(lines);
  const classes = classBodies(lines);
  const className = engineClassName(lines, stem);
  const attributes: Record<string, string> = {};
  const classBody = classes.get(className);
  for (const line of classBody?.lines ?? []) {
    if (!classBody || !line.startsWith(classBody.indent)) {
      continue;
    }
    const unindented = line.slice(classBody.indent.length);
    if (/^[ \t]/.test(unindented)) {
      continue;
    }
    const match = CLASS_ATTRIBUTES.exec(unindented);
    if (!match || (match[1] !== "name" && match[1] !== "url")) {
      continue;
    }
    const value = assignmentValue(match, constants);
    if (value !== null) {
      attributes[match[1]] = value;
    }
  }
  const missing = ["name", "url"].filter((attribute) => !(attribute in attributes));
  if (missing.length > 0) {
    throw new Error("missing class attribute(s): " + missing.join(", "));
  }
  return { name: attributes.name, site_url: attributes.url };
}

export function versionFromSource(source: string): string | null {
  return VERSION_LINE.exec(source)?.[1] ?? null;
}

export function hasSearchMethod(source: string): boolean {
  return SEARCH_METHOD.test(source);
}
