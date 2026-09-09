import { readFileSync, readdirSync } from "node:fs";
import { basename, join } from "node:path";
import { ROOT } from "../core/repo";

const PLUGINS_DIR = join(ROOT, "plugins");
const PREAMBLE_END = "# END GENERATED QBITT SAFETY PREAMBLE";

export type PluginQualitySeverity = "error" | "warning";

export interface PluginQualityIssue {
  kind: string;
  line: number;
  message: string;
  severity: PluginQualitySeverity;
}

export interface PluginQualityMetrics {
  dynamicLoops: number;
  directTransportCalls: number;
  directTransportWithoutTimeouts: number;
  rawThreads: number;
  executors: number;
  unboundedExecutors: number;
  unboundedLoops: number;
  paginationLoops: number;
  unboundedPaginationLoops: number;
  detailLoops: number;
  unboundedDetailLoops: number;
  tlsBypasses: number;
  deadlineIgnoringSleeps: number;
  duplicateHelperAssignments: number;
  deadHelperAssignments: number;
  lines: number;
  networkCalls: number;
  responseReads: number;
  sleeps: number;
  warnings: number;
}

export interface PluginQualityReport {
  id: string;
  issues: PluginQualityIssue[];
  metrics: PluginQualityMetrics;
}

function withoutGeneratedPreamble(source: string): string {
  const marker = source.indexOf(PREAMBLE_END);
  if (marker < 0) {
    return source;
  }
  const bodyStart = source.indexOf("\n", marker);
  return bodyStart < 0 ? "" : source.slice(bodyStart + 1);
}

function lineNumber(source: string, index: number): number {
  return source.slice(0, Math.max(index, 0)).split("\n").length;
}

function addIssue(
  issues: PluginQualityIssue[],
  source: string,
  kind: string,
  severity: PluginQualitySeverity,
  message: string,
  index: number,
): void {
  const issue = { kind, line: lineNumber(source, index), message, severity };
  if (!issues.some((existing) => existing.kind === kind && existing.line === issue.line)) {
    issues.push(issue);
  }
}

function sourceIndex(source: string, body: string, bodyIndex: number): number {
  const bodyStart = source.indexOf(body);
  return bodyStart < 0 ? bodyIndex : bodyStart + bodyIndex;
}

function lineOffsets(source: string): number[] {
  const offsets = [0];
  for (let index = 0; index < source.length; index += 1) {
    if (source[index] === "\n") {
      offsets.push(index + 1);
    }
  }
  return offsets;
}

interface PythonCall {
  args: string;
  end: number;
  name: string;
  start: number;
}

interface ImportAliases {
  executorNames: Set<string>;
  executorRoots: Set<string>;
  networkCallNames: Set<string>;
  networkModules: Set<string>;
  networkRoots: Set<string>;
  sleepNames: Set<string>;
  sslRoots: Set<string>;
  threadNames: Set<string>;
  threadRoots: Set<string>;
  timeRoots: Set<string>;
  urlopenNames: Set<string>;
}

const NETWORK_HELPERS = new Set([
  "_qbt_retrieve_url",
  "_qbt_safe_urlopen",
  "_qbt_urlopen",
  "retrieve_url",
]);
const NETWORK_METHODS = new Set([
  "delete",
  "get",
  "head",
  "options",
  "patch",
  "post",
  "put",
  "request",
]);

function maskPythonSource(source: string): string {
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

function scanCalls(source: string): PythonCall[] {
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

function importAliases(source: string): ImportAliases {
  const aliases: ImportAliases = {
    executorNames: new Set(["ThreadPoolExecutor"]),
    executorRoots: new Set(["concurrent.futures"]),
    networkCallNames: new Set(),
    networkModules: new Set(["urllib.request", "request"]),
    networkRoots: new Set(["requests", "httpx"]),
    sleepNames: new Set(),
    sslRoots: new Set(["ssl"]),
    threadNames: new Set(["Thread"]),
    threadRoots: new Set(["threading"]),
    timeRoots: new Set(["time"]),
    urlopenNames: new Set(["urlopen"]),
  };

  for (const match of source.matchAll(
    /^\s*from\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s+import\s+([A-Za-z_]\w*)(?:\s+as\s+([A-Za-z_]\w*))?/gm,
  )) {
    const module = match[1];
    const imported = match[2];
    const bound = match[3] || imported;
    if (module === "urllib.request" && imported === "urlopen") {
      aliases.urlopenNames.add(bound);
    } else if (module === "urllib" && imported === "request") {
      aliases.networkModules.add(bound);
    } else if ((module === "requests" || module === "httpx") && NETWORK_METHODS.has(imported)) {
      aliases.networkCallNames.add(bound);
    } else if (module === "time" && imported === "sleep") {
      aliases.sleepNames.add(bound);
    } else if (module === "threading" && imported === "Thread") {
      aliases.threadNames.add(bound);
    } else if (module === "concurrent.futures" && imported === "ThreadPoolExecutor") {
      aliases.executorNames.add(bound);
    }
  }

  for (const match of source.matchAll(
    /^\s*import\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)(?:\s+as\s+([A-Za-z_]\w*))?/gm,
  )) {
    const module = match[1];
    const bound = match[2] || module.split(".")[0];
    if (module === "time") {
      aliases.timeRoots.add(bound);
    } else if (module === "ssl") {
      aliases.sslRoots.add(bound);
    } else if (module === "urllib") {
      aliases.networkModules.add(`${bound}.request`);
    } else if (module === "urllib.request") {
      aliases.networkModules.add(bound);
    } else if (module === "requests" || module === "httpx") {
      aliases.networkRoots.add(bound);
    } else if (module === "threading") {
      aliases.threadRoots.add(bound);
    } else if (module === "concurrent.futures") {
      aliases.executorRoots.add(bound);
    }
  }
  return aliases;
}

function leafName(name: string): string {
  return name.slice(name.lastIndexOf(".") + 1);
}

function isDirectTransport(name: string, aliases: ImportAliases): boolean {
  if (NETWORK_HELPERS.has(name)) {
    return false;
  }
  if (aliases.urlopenNames.has(name) || leafName(name) === "urlopen") {
    return true;
  }
  if (aliases.networkCallNames.has(name)) {
    return true;
  }
  const parts = name.split(".");
  const root = parts[0];
  const prefix = parts.slice(0, -1).join(".");
  return (
    (aliases.networkRoots.has(root) && NETWORK_METHODS.has(leafName(name))) ||
    (aliases.networkModules.has(prefix) && leafName(name) === "urlopen")
  );
}

function hasTimeout(call: PythonCall): boolean {
  if (/\btimeout\s*=\s*(?!None\b)/.test(call.args)) {
    return true;
  }
  return leafName(call.name) === "urlopen" && topLevelArgumentCount(call.args) >= 3;
}

function topLevelArgumentCount(argumentsText: string): number {
  if (!argumentsText.trim()) {
    return 0;
  }
  const masked = maskPythonSource(argumentsText);
  let depth = 0;
  let commas = 0;
  for (const character of masked) {
    if (["(", "[", "{"].includes(character)) {
      depth += 1;
    } else if ([")", "]", "}"].includes(character)) {
      depth -= 1;
    } else if (character === "," && depth === 0) {
      commas += 1;
    }
  }
  return commas + 1;
}

function isDeadlineAwareSleep(call: PythonCall): boolean {
  return /\b(?:_qbt_)?(?:deadline|remaining)\w*\b/i.test(call.args);
}

function functionBody(lines: string[], lineIndex: number): string {
  const loopIndent = /^\s*/.exec(lines[lineIndex])?.[0].length ?? 0;
  let functionIndex = -1;
  let functionIndent = Number.POSITIVE_INFINITY;
  for (let index = lineIndex; index >= 0; index -= 1) {
    const match = /^(\s*)(?:async\s+)?def\s+\w+\s*\(/.exec(lines[index]);
    const indent = match?.[1].length ?? Number.POSITIVE_INFINITY;
    if (match && indent < loopIndent) {
      functionIndex = index;
      functionIndent = indent;
      break;
    }
  }
  if (functionIndex < 0) {
    return "";
  }
  const start = functionIndex < 0 ? 0 : functionIndex;
  let end = lines.length;
  for (let index = start + 1; index < lines.length; index += 1) {
    const text = lines[index];
    if (text.trim() && !text.trimStart().startsWith("#")) {
      const indent = /^\s*/.exec(text)?.[0].length ?? 0;
      if (indent <= functionIndent) {
        end = index;
        break;
      }
    }
  }
  return lines.slice(start, end).join("\n");
}

function loopBlock(lines: string[], lineIndex: number): { end: number; text: string } {
  const baseIndent = /^\s*/.exec(lines[lineIndex])?.[0].length ?? 0;
  let end = lines.length;
  for (let index = lineIndex + 1; index < lines.length; index += 1) {
    const text = lines[index];
    if (text.trim() && !text.trimStart().startsWith("#")) {
      const indent = /^\s*/.exec(text)?.[0].length ?? 0;
      if (indent <= baseIndent) {
        end = index;
        break;
      }
    }
  }
  return { end, text: lines.slice(lineIndex, end).join("\n") };
}

function helperAssignmentMetrics(body: string): {
  dead: number;
  duplicate: number;
  firstIndex: number | null;
} {
  const assignments = [...body.matchAll(/^\s*(_qbt_helper_[A-Za-z_]\w*)\s*=.*$/gm)].map(
    (match) => ({
      index: match.index,
      name: match[1],
      text: match[0],
    }),
  );
  const counts = new Map<string, number>();
  let dead = 0;
  for (const assignment of assignments) {
    counts.set(assignment.name, (counts.get(assignment.name) ?? 0) + 1);
    const laterLines = body.slice(assignment.index + assignment.text.length).split(/\r?\n/);
    const assignmentPattern = new RegExp(`^\\s*${assignment.name}\\s*=`);
    const usedLater = laterLines.some(
      (line) => !assignmentPattern.test(line) && new RegExp(`\\b${assignment.name}\\b`).test(line),
    );
    if (!usedLater) {
      dead += 1;
    }
  }
  const duplicate = [...counts.values()].reduce(
    (total, count) => total + Math.max(0, count - 1),
    0,
  );
  return { dead, duplicate, firstIndex: assignments.length > 0 ? assignments[0].index : null };
}

export function auditPluginQuality(id: string, source: string): PluginQualityReport {
  const body = withoutGeneratedPreamble(source);
  const issues: PluginQualityIssue[] = [];
  const aliases = importAliases(body);
  const calls = scanCalls(body);
  const directTransportCalls = calls.filter((call) => isDirectTransport(call.name, aliases));
  const networkCalls = calls.filter(
    (call) => isDirectTransport(call.name, aliases) || NETWORK_HELPERS.has(call.name),
  );
  const lines = body.split(/\r?\n/);
  const offsets = lineOffsets(body);
  const maskedBody = maskPythonSource(body);
  const dynamicLoopPattern =
    /(?:for\s+[^\n]+\s+in\s+range\(\s*[A-Za-z_][\w.]*|while\s+(?!True\b)[^\n:]+)/g;

  for (const call of directTransportCalls) {
    if (hasTimeout(call)) {
      continue;
    }
    addIssue(
      issues,
      source,
      "direct-network",
      "error",
      "Direct transport calls must declare an explicit timeout; use _qbt_safe_urlopen or retrieve_url.",
      sourceIndex(source, body, call.start),
    );
  }

  const rawThreadCalls = calls.filter((call) => leafName(call.name) === "Thread");
  for (const call of rawThreadCalls) {
    addIssue(
      issues,
      source,
      "raw-thread",
      "error",
      "Use _qbt_run_parallel instead of creating raw threads.",
      sourceIndex(source, body, call.start),
    );
  }

  const executorCalls = calls.filter((call) => leafName(call.name) === "ThreadPoolExecutor");
  for (const call of executorCalls) {
    if (!/\bmax_workers\s*=\s*(?!None\b)/.test(call.args)) {
      addIssue(
        issues,
        source,
        "unbounded-executor",
        "error",
        "ThreadPoolExecutor must declare max_workers.",
        sourceIndex(source, body, call.start),
      );
    }
  }

  let unboundedLoops = 0;
  let paginationLoops = 0;
  let unboundedPaginationLoops = 0;
  let detailLoops = 0;
  let unboundedDetailLoops = 0;
  const paginationPattern =
    /\b(?:page|pages|page_num|page_number|lastPage|total_pages|total_results|offset|cursor|next_page)\b/i;
  const detailPattern =
    /\b(?:detail|details|detail_url|details_url|item|items|result|results|torrent|torrents|link|links|url|urls)\b/i;
  const networkLines = new Set(networkCalls.map((call) => lineNumber(body, call.start)));
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (!/^\s*(?:for|while)\b/.test(line)) {
      continue;
    }
    const block = loopBlock(lines, index);
    const blockLineNumbers = new Set(
      Array.from({ length: block.end - index }, (_, offset) => index + offset + 1),
    );
    const blockHasNetwork = [...networkLines].some((lineNumberValue) =>
      blockLineNumbers.has(lineNumberValue),
    );
    const scope = functionBody(lines, index) || block.text;
    if (paginationPattern.test(line)) {
      paginationLoops += 1;
      if (!/\bMAX_PAGES\b/.test(scope)) {
        unboundedPaginationLoops += 1;
        addIssue(
          issues,
          source,
          "unbounded-pagination",
          "error",
          "Pagination loops must be bounded by MAX_PAGES.",
          sourceIndex(source, body, offsets[index]),
        );
      }
    }
    if (detailPattern.test(line) && blockHasNetwork) {
      detailLoops += 1;
      if (!/\bMAX_DETAILS\b/.test(scope)) {
        unboundedDetailLoops += 1;
        addIssue(
          issues,
          source,
          "unbounded-detail",
          "error",
          "Detail-fetch loops must be bounded by MAX_DETAILS.",
          sourceIndex(source, body, offsets[index]),
        );
      }
    }
    if (/^\s*while\s+True\b/.test(line)) {
      unboundedLoops += 1;
      addIssue(
        issues,
        source,
        "unbounded-loop",
        "error",
        "Search loops must have an explicit termination condition.",
        sourceIndex(source, body, offsets[index]),
      );
    }
  }

  let tlsBypasses = 0;
  const tlsLines = new Set<number>();
  const addTlsIssue = (index: number, message: string): void => {
    const line = lineNumber(source, sourceIndex(source, body, index));
    if (tlsLines.has(line)) {
      return;
    }
    tlsLines.add(line);
    tlsBypasses += 1;
    addIssue(issues, source, "insecure-tls", "error", message, sourceIndex(source, body, index));
  };
  for (const match of maskedBody.matchAll(/\bCERT_NONE\b/g)) {
    addTlsIssue(match.index, "Do not disable TLS certificate verification.");
  }
  for (const match of maskedBody.matchAll(/\bcheck_hostname\s*=\s*False\b/g)) {
    addTlsIssue(match.index, "Do not disable TLS hostname verification.");
  }
  for (const call of calls) {
    if (call.name.endsWith("._create_unverified_context")) {
      addTlsIssue(call.start, "Do not create an unverified TLS context.");
    }
    if (isDirectTransport(call.name, aliases) && /\bverify\s*=\s*False\b/.test(call.args)) {
      addTlsIssue(call.start, "Do not disable TLS verification on network calls.");
    }
  }

  let sleeps = 0;
  let deadlineIgnoringSleeps = 0;
  for (const call of calls) {
    const sleepCall =
      aliases.sleepNames.has(call.name) ||
      (call.name.endsWith(".sleep") && aliases.timeRoots.has(call.name.slice(0, -6)));
    if (!sleepCall) {
      continue;
    }
    sleeps += 1;
    if (!isDeadlineAwareSleep(call)) {
      deadlineIgnoringSleeps += 1;
      addIssue(
        issues,
        source,
        "fixed-sleep",
        "error",
        "Sleep duration must be derived from the search deadline.",
        sourceIndex(source, body, call.start),
      );
    }
  }

  const helperMetrics = helperAssignmentMetrics(body);
  if (helperMetrics.dead > 0 && helperMetrics.firstIndex !== null) {
    addIssue(
      issues,
      source,
      "dead-helper-assignment",
      "warning",
      "Remove post-preamble helper sentinel assignments; the generated alias is already fixed.",
      sourceIndex(source, body, helperMetrics.firstIndex),
    );
  }

  for (const match of body.matchAll(/\.read\s*\(/g)) {
    addIssue(
      issues,
      source,
      "unbounded-read",
      "warning",
      "Prefer a bounded response-body read for direct HTTP responses.",
      sourceIndex(source, body, match.index),
    );
  }

  for (const match of body.matchAll(dynamicLoopPattern)) {
    addIssue(
      issues,
      source,
      "dynamic-loop",
      "warning",
      "Review dynamic pagination or result loops for MAX_PAGES/MAX_DETAILS bounds.",
      sourceIndex(source, body, match.index),
    );
  }

  const metrics: PluginQualityMetrics = {
    dynamicLoops: [...body.matchAll(dynamicLoopPattern)].length,
    directTransportCalls: directTransportCalls.length,
    directTransportWithoutTimeouts: directTransportCalls.filter((call) => !hasTimeout(call)).length,
    rawThreads: rawThreadCalls.length,
    executors: executorCalls.length,
    unboundedExecutors: executorCalls.filter(
      (call) => !/\bmax_workers\s*=\s*(?!None\b)/.test(call.args),
    ).length,
    unboundedLoops,
    paginationLoops,
    unboundedPaginationLoops,
    detailLoops,
    unboundedDetailLoops,
    tlsBypasses,
    deadlineIgnoringSleeps,
    duplicateHelperAssignments: helperMetrics.duplicate,
    deadHelperAssignments: helperMetrics.dead,
    lines: body.split("\n").length,
    networkCalls: networkCalls.length,
    responseReads: [...body.matchAll(/\.read\s*\(/g)].length,
    sleeps,
    warnings: issues.filter((issue) => issue.severity === "warning").length,
  };

  return { id, issues, metrics };
}

export function pluginQualityReports(): PluginQualityReport[] {
  return readdirSync(PLUGINS_DIR)
    .filter((entry) => entry.endsWith(".py"))
    .sort()
    .map((entry) => {
      const id = basename(entry, ".py");
      return auditPluginQuality(id, readFileSync(join(PLUGINS_DIR, entry), "utf8"));
    });
}

export function runPluginQualityCheck(): number {
  const reports = pluginQualityReports();
  let errors = 0;
  let warnings = 0;

  for (const report of reports) {
    for (const issue of report.issues) {
      const prefix = issue.severity === "error" ? "ERROR" : "WARN";
      console.error(`${prefix} ${report.id}:${issue.line} ${issue.kind}: ${issue.message}`);
      if (issue.severity === "error") {
        errors += 1;
      } else {
        warnings += 1;
      }
    }
  }

  const totals = reports.reduce(
    (result, report) => {
      result.networkCalls += report.metrics.networkCalls;
      result.dynamicLoops += report.metrics.dynamicLoops;
      result.responseReads += report.metrics.responseReads;
      result.sleeps += report.metrics.sleeps;
      result.directTransportCalls += report.metrics.directTransportCalls;
      result.directTransportWithoutTimeouts += report.metrics.directTransportWithoutTimeouts;
      result.unboundedExecutors += report.metrics.unboundedExecutors;
      result.unboundedLoops += report.metrics.unboundedLoops;
      result.unboundedPaginationLoops += report.metrics.unboundedPaginationLoops;
      result.unboundedDetailLoops += report.metrics.unboundedDetailLoops;
      result.tlsBypasses += report.metrics.tlsBypasses;
      result.deadlineIgnoringSleeps += report.metrics.deadlineIgnoringSleeps;
      result.duplicateHelperAssignments += report.metrics.duplicateHelperAssignments;
      result.deadHelperAssignments += report.metrics.deadHelperAssignments;
      return result;
    },
    {
      deadlineIgnoringSleeps: 0,
      deadHelperAssignments: 0,
      directTransportCalls: 0,
      directTransportWithoutTimeouts: 0,
      duplicateHelperAssignments: 0,
      dynamicLoops: 0,
      networkCalls: 0,
      responseReads: 0,
      sleeps: 0,
      tlsBypasses: 0,
      unboundedDetailLoops: 0,
      unboundedExecutors: 0,
      unboundedLoops: 0,
      unboundedPaginationLoops: 0,
    },
  );
  console.log(
    `Plugin quality: ${reports.length} engines, ${errors} errors, ${warnings} warnings, ` +
      `${totals.networkCalls} network calls, ${totals.dynamicLoops} dynamic loops, ` +
      `${totals.responseReads} response reads, ${totals.sleeps} sleeps, ` +
      `${totals.directTransportWithoutTimeouts}/${totals.directTransportCalls} direct transports without timeouts, ` +
      `${totals.unboundedExecutors} unbounded executors, ` +
      `${totals.unboundedPaginationLoops} unbounded pagination loops, ` +
      `${totals.unboundedDetailLoops} unbounded detail loops, ` +
      `${totals.tlsBypasses} TLS bypasses, ` +
      `${totals.deadlineIgnoringSleeps} deadline-ignoring sleeps, ` +
      `${totals.duplicateHelperAssignments} duplicate and ${totals.deadHelperAssignments} dead helper assignments`,
  );
  return errors === 0 ? 0 : 1;
}

if (import.meta.main) {
  process.exitCode = runPluginQualityCheck();
}
