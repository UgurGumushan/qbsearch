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

export interface Catalog {
  schema_version: number;
  plugins: CatalogEntry[];
  [key: string]: unknown;
}

export interface InstallableCatalogEntry {
  id: string;
  icon: string;
}

export interface PluginMetadata {
  name: string;
  site_url: string;
}

export interface ClassBody {
  lines: string[];
  indent: string;
}
