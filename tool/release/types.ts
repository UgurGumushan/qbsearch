/**
 * Describe the inputs required to build a release archive.
 * @file
 */
import type { InstallableCatalogEntry } from "../catalog/types";

/** Validated catalog installation entry used by release assembly. */
export type CatalogEntry = InstallableCatalogEntry;

/** Release version, destination path, and archive root prefix. */
export interface ReleaseOptions {
  version: string;
  output: string;
}
