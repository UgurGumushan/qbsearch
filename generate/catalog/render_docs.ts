import { RAW_PLUGIN_BASE } from "./constants";
import { catalogEntries } from "./storage";
import type { Catalog } from "./types";

function increment(counter: Map<string, number>, value: string): void {
  counter.set(value, (counter.get(value) ?? 0) + 1);
}

function compareStrings(left: string, right: string): number {
  if (left < right) {
    return -1;
  }
  if (left > right) {
    return 1;
  }
  return 0;
}

function displayValue(value: unknown, fallback: string): string {
  if (typeof value === "string") {
    return value || fallback;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return value == null ? fallback : JSON.stringify(value);
}

/** Render the checked-in Markdown catalog from the JSON source of truth. */
export function renderPluginDocs(catalog: Catalog): string {
  const entries = catalogEntries(catalog);
  const categoryCounts = new Map<string, number>();
  const statusCounts = new Map<string, number>();
  for (const entry of entries) {
    increment(categoryCounts, entry.category);
    increment(statusCounts, entry.status);
  }
  const categories = [...categoryCounts.keys()]
    .sort(compareStrings)
    .map((category) => `${category} (${categoryCounts.get(category)})`)
    .join(", ");
  const statuses = [...statusCounts.keys()]
    .sort(compareStrings)
    .map((status) => `${status} (${statusCounts.get(status)})`)
    .join(", ");
  const lines = [
    "# Plugin catalog",
    "",
    "This file is generated from [`catalog/plugins.json`](../catalog/plugins.json).",
    "Edit the JSON catalog and run `bun run catalog`.",
    "",
    "The `status` field describes repository support, not a guarantee that a remote",
    "site is online at this moment. Live tests contact the sites listed below.",
    "",
    "- Categories: " + categories,
    "- Status: " + statuses,
    "",
    "| Plugin | Category | Status | License | Site | Default live query | Install |",
    "| --- | --- | --- | --- | --- | --- | --- |",
  ];

  const sortedEntries = [...entries].sort((left, right) => {
    const categoryOrder = compareStrings(left.category, right.category);
    return categoryOrder !== 0
      ? categoryOrder
      : compareStrings(left.name.toLowerCase(), right.name.toLowerCase());
  });
  for (const entry of sortedEntries) {
    const name = entry.name.replaceAll("|", "\\|");
    const siteUrl = entry.site_url;
    const site = siteUrl ? `[site](${siteUrl})` : "—";
    let query = entry.default_query.replaceAll("|", "\\|");
    const license = displayValue(entry.license, "—").replaceAll("|", "\\|");
    const notes = displayValue(entry.notes, "");
    if (notes) {
      query += " (" + notes.replaceAll("|", "\\|") + ")";
    }
    lines.push(
      `| [${name}](../plugins/${entry.id}.py) | ${entry.category} | ${entry.status} | ${license} | ${site} | \`${query}\` | [download](${RAW_PLUGIN_BASE}${entry.id}.py) |`,
    );
  }
  lines.push(
    "",
    "`default live query` is only a safe smoke-test value. It is not a",
    "recommendation for content or a promise that the site returns results.",
    "",
  );
  return lines.join("\n");
}
