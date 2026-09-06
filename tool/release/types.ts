import type { InstallableCatalogEntry } from "../catalog/types";

export type CatalogEntry = InstallableCatalogEntry;

export interface ParsedArguments {
  help: boolean;
  version: string;
  output: string;
}
