import type { InstallableCatalogEntry } from "../catalog/types";

export type CatalogEntry = InstallableCatalogEntry;

export interface ReleaseOptions {
  version: string;
  output: string;
}
