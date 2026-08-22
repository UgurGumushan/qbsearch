export const REPOSITORY_URL = "https://github.com/UgurGumushan/qbsearch";
export const RELEASES_URL = `${REPOSITORY_URL}/releases`;

export type PluginCategory =
  "adult" | "anime" | "books" | "games" | "general" | "movies" | "software" | "tv";

export type PluginStatus = "active" | "intermittent" | "unavailable" | "retired";

export type Plugin = {
  id: string;
  name: string;
  site_url: string;
  category: PluginCategory;
  default_query: string;
  status: PluginStatus;
  icon: string;
  requires_auth: boolean;
  source_url: string | null;
  license: string;
  notes: string;
};

export function categoryLabel(category: PluginCategory): string {
  return category.charAt(0).toUpperCase() + category.slice(1);
}

export function pluginSourceUrl(plugin: Plugin): string {
  return `${REPOSITORY_URL}/blob/main/plugins/${plugin.id}.py`;
}
