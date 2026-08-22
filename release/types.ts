import type { InstallableCatalogEntry } from "../generate/catalog/types";

export type CatalogEntry = InstallableCatalogEntry;

export interface ParsedArguments {
  help: boolean;
  version: string;
  output: string;
}
