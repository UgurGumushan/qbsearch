import { PLUGIN_DIR, ROOT } from "../../scripts/repository";

export { PLUGIN_DIR, ROOT };

export const START_MARKER = "# BEGIN GENERATED QBITT SAFETY PREAMBLE";
export const END_MARKER = "# END GENERATED QBITT SAFETY PREAMBLE";

export const HTML_PARSER_OVERRIDES = new Set([
  "handle_comment",
  "handle_decl",
  "handle_data",
  "handle_endtag",
  "handle_entityref",
  "handle_startendtag",
  "handle_starttag",
]);
