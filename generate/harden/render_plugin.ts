import { END_MARKER, START_MARKER } from "./constants";
import { addOverrideDecorators } from "./overrides";
import {
  aliasRetrieveImports,
  ensureFutureAnnotations,
  insertAfterImports,
  replaceGeneratedPreamble,
} from "./imports";

/** Render one plugin with the canonical generated safety block. */
export function renderPlugin(source: string): string {
  const hadPreamble = source.includes(START_MARKER);
  let rendered = ensureFutureAnnotations(source);
  rendered = aliasRetrieveImports(rendered);
  rendered = addOverrideDecorators(rendered);
  const includeOverride = /^\s*@override\s*$/m.test(rendered);

  if (hadPreamble) {
    rendered = replaceGeneratedPreamble(rendered, includeOverride);
  } else {
    rendered = insertAfterImports(rendered, includeOverride);
  }

  const endMarker = rendered.indexOf(END_MARKER);
  const before = rendered.slice(0, endMarker + END_MARKER.length);
  const after = rendered.slice(endMarker + END_MARKER.length);
  return before + after.replace(/(?:_qbt_)*prettyPrinter\(/g, "_qbt_prettyPrinter(");
}
