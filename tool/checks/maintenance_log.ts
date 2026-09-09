import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { VALID_STATUSES } from "../catalog/constants";
import { loadCatalog } from "../catalog/index";
import { ROOT } from "../core/repo";

const MAINTENANCE_LOG_PATH = resolve(ROOT, "documentation", "MAINTENANCE_LOG.md");
const VALID_RESULTS = new Set(["ok", "empty", "failed", "blocked"]);

function splitRow(line: string): string[] {
  const trimmed = line.trim();
  if (!trimmed.startsWith("|") || !trimmed.endsWith("|")) {
    return [];
  }
  return trimmed
    .slice(1, -1)
    .split("|")
    .map((cell) => cell.trim());
}

function isSeparatorRow(cells: string[]): boolean {
  return cells.length > 0 && cells.every((cell) => /^-+$/.test(cell.replace(/\s/g, "")));
}

function isDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value);
}

/** Validate the evidence log format used to justify status changes. */
export async function validateMaintenanceLog(): Promise<string[]> {
  let raw: string;
  try {
    raw = await readFile(MAINTENANCE_LOG_PATH, "utf8");
  } catch {
    return ["maintenance log is missing: documentation/MAINTENANCE_LOG.md"];
  }

  const lines = raw.split(/\r?\n/);
  const catalog = await loadCatalog();
  const catalogIds = new Set(catalog.plugins.map((entry) => entry.id));

  const issues: string[] = [];
  let tableStarted = false;
  let sawHeader = false;

  for (const line of lines) {
    const cells = splitRow(line);
    if (cells.length < 7) {
      continue;
    }

    const header = cells[0].toLowerCase();
    if (
      header === "date (utc)" &&
      cells[1].toLowerCase() === "plugin id" &&
      cells[2].toLowerCase() === "from"
    ) {
      tableStarted = true;
      sawHeader = true;
      continue;
    }

    if (!tableStarted) {
      continue;
    }

    if (isSeparatorRow(cells)) {
      continue;
    }

    const [date, pluginId, fromStatus, toStatus, query, result, ...restNotes] = cells;
    const notes = restNotes.join(" | ").trim();

    if (!isDate(date)) {
      issues.push(`maintenance log row has invalid date: ${date}`);
    }
    if (!pluginId || !catalogIds.has(pluginId)) {
      issues.push(`maintenance log row has unknown plugin id: ${pluginId}`);
    }
    if (!VALID_STATUSES.has(fromStatus)) {
      issues.push(`maintenance log row has invalid from status: ${fromStatus}`);
    }
    if (!VALID_STATUSES.has(toStatus)) {
      issues.push(`maintenance log row has invalid to status: ${toStatus}`);
    }
    if (!query.trim()) {
      issues.push(`maintenance log row missing evidence query for ${pluginId}`);
    }
    if (!VALID_RESULTS.has(result)) {
      issues.push(`maintenance log row has invalid result for ${pluginId}: ${result}`);
    }
    if (!notes) {
      issues.push(`maintenance log row missing notes for ${pluginId} (${date})`);
    }
  }

  if (!sawHeader) {
    issues.push("maintenance log table header is missing");
  }

  return issues;
}
