/**
 * Describe catalog records and release installation entries.
 * @file
 */
/** Catalog metadata for an engine, including lifecycle and licensing information. */
export interface CatalogEntry {
  id: string;
  name: string;
  site_url: string;
  category: string;
  default_query: string;
  status: string;
  icon: string;
  [key: string]: unknown;
}

/** Versioned catalog document and its plugin entries. */
export interface Catalog {
  schema_version: number;
  plugins: CatalogEntry[];
  [key: string]: unknown;
}

/** Engine and icon paths required to construct an installable release. */
export interface InstallableCatalogEntry {
  id: string;
  icon: string;
}
