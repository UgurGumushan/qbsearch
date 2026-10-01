/** Conservative lexical analysis; unknown dataflow remains an advisory. */
export interface PythonCall {
  args: string;
  end: number;
  name: string;
  start: number;
}

export function maskPythonSource(source: string): string {
  const characters = source.split("");
  let quote: string | null = null;
  let triple = false;
  let comment = false;
  for (let index = 0; index < characters.length; index += 1) {
    const character = characters[index];
    if (comment) {
      if (character === "\n") {
        comment = false;
      } else {
        characters[index] = " ";
      }
      continue;
    }
    if (quote) {
      if (character === "\\") {
        if (characters[index + 1] !== "\n") {
          characters[index] = " ";
        }
        if (index + 1 < characters.length && characters[index + 1] !== "\n") {
          characters[index + 1] = " ";
        }
        index += 1;
      } else if (
        characters.slice(index, index + (triple ? 3 : 1)).join("") === quote.repeat(triple ? 3 : 1)
      ) {
        for (let offset = 0; offset < (triple ? 3 : 1); offset += 1) {
          characters[index + offset] = " ";
        }
        index += triple ? 2 : 0;
        quote = null;
        triple = false;
      } else if (character !== "\n") {
        characters[index] = " ";
      }
      continue;
    }
    if (character === "#") {
      characters[index] = " ";
      comment = true;
      continue;
    }
    if (character === "'" || character === '"') {
      quote = character;
      triple = characters.slice(index, index + 3).join("") === character.repeat(3);
      characters[index] = " ";
      if (triple) {
        characters[index + 1] = " ";
        characters[index + 2] = " ";
        index += 2;
      }
    }
  }
  return characters.join("");
}

function closingParen(source: string, openIndex: number): number {
  let depth = 0;
  for (let index = openIndex; index < source.length; index += 1) {
    if (source[index] === "(") {
      depth += 1;
    } else if (source[index] === ")") {
      depth -= 1;
      if (depth === 0) {
        return index;
      }
    }
  }
  return source.length;
}

export function scanPythonCalls(source: string): PythonCall[] {
  const masked = maskPythonSource(source);
  const calls: PythonCall[] = [];
  const pattern = /(?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*\s*\(/g;
  for (const match of masked.matchAll(pattern)) {
    const matchIndex = match.index;
    const name = match[0].replace(/\s*\($/, "").trim();
    const nameStart = matchIndex + match[0].indexOf(name);
    const prefix = masked.slice(Math.max(0, nameStart - 8), nameStart);
    if (/\bdef\s*$/.test(prefix)) {
      continue;
    }
    const openIndex = masked.indexOf("(", nameStart);
    const closeIndex = closingParen(masked, openIndex);
    calls.push({
      args: source.slice(openIndex + 1, closeIndex),
      end: Math.min(source.length, closeIndex + 1),
      name,
      start: nameStart,
    });
  }
  return calls;
}

/** Split arguments without treating commas inside calls as separators. */
export function pythonArguments(expression: string): string[] {
  const masked = maskPythonSource(expression);
  let depth = 0;
  let start = 0;
  const args: string[] = [];
  for (let index = 0; index < masked.length; index += 1) {
    const char = masked[index];
    if ("([{ ".includes(char) && char !== " ") depth += 1;
    if (")]}".includes(char)) depth -= 1;
    if (char === "," && depth === 0) {
      args.push(expression.slice(start, index).trim());
      start = index + 1;
    }
  }
  args.push(expression.slice(start).trim());
  return args.filter(Boolean);
}

function scopePrefix(source: string, position: number): string {
  const lines = maskPythonSource(source).slice(0, position).split("\n");
  const lineStart = source.lastIndexOf("\n", position - 1) + 1;
  const indent = /^ */.exec(source.slice(lineStart))?.[0].length ?? 0;
  for (let index = lines.length - 2; index >= 0; index -= 1) {
    const match = /^( *)(?:async +)?def +\w+\(/.exec(lines[index]);
    if (match && match[1].length < indent) {
      // Globals cannot inherit assignments from another function or class.
      const globals = lines.slice(0, index).filter((line) => /^\w+\s*(?::[^=]+)?=/.test(line));
      return [...globals, ...lines.slice(index)].join("\n");
    }
  }
  return lines.join("\n");
}

function assignments(prefix: string): Map<string, string> {
  const values = new Map<string, string>();
  for (const line of prefix.split("\n")) {
    const assignment = /^\s*([\w.]+)\s*(?::[^=]+)?([+*/%|&^-]?=)(?!=)\s*(.*)$/.exec(line);
    if (assignment) {
      const previous = values.get(assignment[1]);
      const step = /^\d+$/.test(assignment[3].trim());
      const declaration = /^( *)def\b/m.exec(prefix);
      const bodyIndent = declaration ? declaration[1].length + 4 : undefined;
      const straight =
        bodyIndent !== undefined && (/^ */.exec(line)?.[0].length ?? 0) === bodyIndent;
      values.set(
        assignment[1],
        assignment[2] === "="
          ? assignment[3].trim()
          : assignment[2] === "+=" && previous && step && straight
            ? `${previous} + ${assignment[3]}`
            : "?",
      );
    }
    const binding = /^\s*(?:for|def)\s+(\w+)\s+/.exec(line);
    if (binding) {
      const range = /^\s*for\s+\w+\s+in\s+range\((.*)\):/.exec(line);
      const args = range ? pythonArguments(range[1]) : [];
      values.set(
        binding[1],
        args.length > 0 && args.every((arg) => finiteExpression(arg, values))
          ? args[Math.min(1, args.length - 1)]
          : "?",
      );
    }
    const params = /^\s*def\s+\w+\(([^)]*)\)/.exec(line);
    if (params) {
      for (const param of pythonArguments(params[1])) {
        values.set(param.split(/[=:]/)[0].trim(), "?");
      }
    }
  }
  return values;
}

const BUDGETS = new Set([
  "MAX_PAGES",
  "MAX_DETAILS",
  "MAX_ATTEMPTS",
  "MAX_WORKERS",
  "MAX_RESPONSE_BYTES",
]);

function finiteExpression(
  expression: string,
  values: Map<string, string>,
  seen = new Set<string>(),
): boolean {
  const text = expression.trim();
  if (/^\d+(?:_\d+)*$/.test(text)) return Number.isSafeInteger(Number(text.replaceAll("_", "")));
  if (/^[\w.]+$/.test(text)) {
    if (seen.has(text)) return false;
    const assigned = values.get(text);
    if (assigned === undefined) return BUDGETS.has(text);
    return finiteExpression(assigned, values, new Set([...seen, text]));
  }
  const plus = /^(.*)\+\s*(\d+)$/.exec(text);
  if (plus) return finiteExpression(plus[1], values, seen);
  const conditional = /^(.*?)\s+if\s+.*?\s+else\s+(.*)$/.exec(text);
  if (conditional)
    return (
      finiteExpression(conditional[1], values, seen) &&
      finiteExpression(conditional[2], values, seen)
    );
  const call = /^(min|max|int)\s*\(/.exec(text);
  if (!call || closingParen(text, text.indexOf("(")) !== text.length - 1) return false;
  const args = pythonArguments(text.slice(text.indexOf("(") + 1, -1));
  if (call[1] === "min") return args.some((arg) => finiteExpression(arg, values, seen));
  return args.length > 0 && args.every((arg) => finiteExpression(arg, values, seen));
}

export function boundedPythonRange(source: string, call: PythonCall): boolean {
  const args = pythonArguments(maskPythonSource(call.args));
  const values = assignments(scopePrefix(source, call.start));
  if (args.length === 1) return finiteExpression(args[0], values);
  // A server-controlled start could be arbitrarily negative; require both bounds.
  if (args.length !== 2 && args.length !== 3) return false;
  return (
    finiteExpression(args[0], values) &&
    nonnegativeExpression(args[0], values) &&
    finiteExpression(args[1], values) &&
    (args.length < 3 || !args[2].startsWith("-") || nonnegativeExpression(args[1], values)) &&
    (args.length === 2 || /^-?[1-9]\d*$/.test(args[2]) || positiveExpression(args[2], values))
  );
}

function positiveExpression(
  expression: string,
  values: Map<string, string>,
  seen = new Set<string>(),
): boolean {
  const text = expression.trim();
  if (/^\d+$/.test(text)) return Number(text) > 0;
  if (seen.has(text)) return false;
  if (/^[\w.]+$/.test(text)) {
    const assigned = values.get(text);
    return assigned === undefined
      ? BUDGETS.has(text)
      : positiveExpression(assigned, values, new Set([...seen, text]));
  }
  const call = /^(min|max|int)\(/.exec(text);
  if (!call || closingParen(text, text.indexOf("(")) !== text.length - 1) return false;
  const args = pythonArguments(text.slice(text.indexOf("(") + 1, -1));
  return call[1] === "max"
    ? args.some((arg) => positiveExpression(arg, values, seen))
    : args.length > 0 && args.every((arg) => positiveExpression(arg, values, seen));
}

function nonnegativeExpression(
  expression: string,
  values: Map<string, string>,
  seen = new Set<string>(),
): boolean {
  const text = expression.trim();
  if (/^\d+(?:_\d+)*$/.test(text)) return true;
  if (seen.has(text)) return false;
  if (/^[\w.]+$/.test(text)) {
    const assigned = values.get(text);
    return assigned === undefined
      ? BUDGETS.has(text)
      : nonnegativeExpression(assigned, values, new Set([...seen, text]));
  }
  const plus = /^(.*)\+\s*\d+$/.exec(text);
  if (plus) return nonnegativeExpression(plus[1], values, seen);
  const conditional = /^(.*?)\s+if\s+.*?\s+else\s+(.*)$/.exec(text);
  if (conditional)
    return (
      nonnegativeExpression(conditional[1], values, seen) &&
      nonnegativeExpression(conditional[2], values, seen)
    );
  const call = /^(min|max|int)\(/.exec(text);
  if (!call || closingParen(text, text.indexOf("(")) !== text.length - 1) return false;
  const args = pythonArguments(text.slice(text.indexOf("(") + 1, -1));
  return call[1] === "max"
    ? args.some((arg) => nonnegativeExpression(arg, values, seen))
    : args.length > 0 && args.every((arg) => nonnegativeExpression(arg, values, seen));
}

export function boundedPythonWhile(source: string, position: number, block: string): boolean {
  const lines = maskPythonSource(block).split("\n");
  const condition = lines[0]
    .trim()
    .replace(/^while\s+/, "")
    .replace(/:$/, "");
  if (/\bor\b/.test(condition)) return false;
  const guard = /\b([\w.]+)\s*<=?\s*([^<>=]+)$/.exec(condition);
  const values = assignments(scopePrefix(source, position));
  if (
    !guard ||
    !finiteExpression(guard[2], values) ||
    !finiteExpression(guard[1], values) ||
    !nonnegativeExpression(guard[1], values)
  )
    return false;
  const indent = /^ */.exec(lines[0])?.[0].length ?? 0;
  const counter = guard[1].replaceAll(".", "\\.");
  const step = new RegExp(
    `^ {${indent + 4}}${counter}\\s*(?:\\+=\\s*[1-9]\\d*|=\\s*${counter}\\s*\\+\\s*[1-9]\\d*)\\s*$`,
  );
  const loops = [indent];
  let outerContinue = false;
  for (const line of lines.slice(1)) {
    if (!line.trim()) continue;
    const level = /^ */.exec(line)?.[0].length ?? 0;
    while (loops.length > 1 && level <= loops[loops.length - 1]) loops.pop();
    if (/^ *(?:for|while)\b/.test(line)) loops.push(level);
    if (/^ *continue\b/.test(line) && loops.length === 1) outerContinue = true;
    if (new RegExp(`^ *${counter}\\s*(?:[+*/%-]?=)(?!=)`).test(line) && !step.test(line))
      return false;
  }
  // Conditional increments and outer continue branches require manual review.
  return !outerContinue && lines.some((line) => step.test(line));
}

export function boundedPythonRead(source: string, call: PythonCall): boolean {
  const prefix = scopePrefix(source, call.start);
  const values = assignments(prefix);
  const argument = maskPythonSource(call.args)
    .replace(/^\s*size\s*=\s*/, "")
    .trim();
  if (argument && finiteExpression(argument, values) && nonnegativeExpression(argument, values))
    return true;
  const bounded = new Set<string>();
  for (const line of prefix.split("\n")) {
    const withAlias = /\bwith\s+_qbt_safe_urlopen\(.*\)\s+as\s+(\w+)\s*:/.exec(line);
    if (withAlias) bounded.add(withAlias[1]);
    const binding = /^\s*([\w.]+)\s*(?::[^=]+)?([+*/%|&^-]?=)(?!=)\s*(.*)$/.exec(line);
    if (binding) {
      const expression = binding[3].trim();
      const safeCall =
        expression.startsWith("_qbt_safe_urlopen(") &&
        closingParen(expression, expression.indexOf("(")) === expression.length - 1;
      if (binding[2] === "=" && (safeCall || bounded.has(expression))) bounded.add(binding[1]);
      else bounded.delete(binding[1]);
    }
    const loop = /^\s*for\s+(\w+)\s+in\b/.exec(line);
    if (loop) bounded.delete(loop[1]);
  }
  return bounded.has(call.name.slice(0, -".read".length));
}
