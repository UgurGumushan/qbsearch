/**
 * Define catalog paths, lifecycle states, and documentation conventions.
 * @file
 */
export const RAW_PLUGIN_BASE =
  "https://raw.githubusercontent.com/UgurGumushan/qbsearch/main/plugins/";

export const VALID_CATEGORIES = new Set([
  "adult",
  "anime",
  "books",
  "games",
  "general",
  "movies",
  "music",
  "software",
  "tv",
]);

export const VALID_STATUSES = new Set([
  "active",
  "intermittent",
  "unavailable",
  "requires-account",
  "retired",
]);
