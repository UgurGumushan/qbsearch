import { HTML_PARSER_OVERRIDES } from "./constants";
import { hasFinalNewline, indentation, isCodeLine } from "./source_text";

interface ClassRange {
  start: number;
  end: number;
  indent: number;
  html: boolean;
}

function classRanges(lines: string[]): ClassRange[] {
  const classes: ClassRange[] = [];
  for (let start = 0; start < lines.length; start += 1) {
    const match = /^(\s*)class\s+\w+\b([^:]*)[:]/.exec(lines[start]);
    if (!match) {
      continue;
    }
    const classIndent = indentation(lines[start]);
    let end = lines.length;
    for (let index = start + 1; index < lines.length; index += 1) {
      if (isCodeLine(lines[index]) && indentation(lines[index]) <= classIndent) {
        end = index;
        break;
      }
    }
    classes.push({
      start,
      end,
      indent: classIndent,
      html: /\bHTMLParser\b/.test(match[2]),
    });
  }
  return classes;
}

/** Add compatibility override decorators to methods with known base methods. */
export function addOverrideDecorators(source: string): string {
  const trailingNewline = hasFinalNewline(source);
  const lines = source.split(/\r?\n/);
  if (trailingNewline) {
    lines.pop();
  }
  const insertions: { line: number; text: string }[] = [];

  for (const classRange of classRanges(lines)) {
    const methodIndent = classRange.indent + 4;
    for (let line = classRange.start + 1; line < classRange.end; line += 1) {
      if (indentation(lines[line]) !== methodIndent) {
        continue;
      }
      const method = /^\s*(?:async\s+)?def\s+(\w+)\s*\(/.exec(lines[line]);
      if (!method) {
        continue;
      }
      const methodName = method[1];
      if (
        methodName !== "__repr__" &&
        !(classRange.html && HTML_PARSER_OVERRIDES.has(methodName))
      ) {
        continue;
      }

      let firstDecorator = line;
      let hasOverride = false;
      for (let previous = line - 1; previous >= 0; previous -= 1) {
        if (lines[previous].trim() === "") {
          break;
        }
        if (
          indentation(lines[previous]) !== methodIndent ||
          !lines[previous].trim().startsWith("@")
        ) {
          break;
        }
        firstDecorator = previous;
        if (/^\s*@(?:_qbt_)?override\s*$/.test(lines[previous])) {
          hasOverride = true;
        }
      }
      if (!hasOverride) {
        insertions.push({
          line: firstDecorator,
          text: `${lines[line].slice(0, methodIndent)}@override`,
        });
      }
    }
  }

  for (const insertion of insertions.sort((left, right) => right.line - left.line)) {
    lines.splice(insertion.line, 0, insertion.text);
  }
  return lines.join("\n") + (trailingNewline ? "\n" : "");
}
