"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUpRightIcon, CodeIcon, GlobeIcon, SearchIcon, SlidersIcon } from "@/components/icons";
import {
  categoryLabel,
  pluginSourceUrl,
  type Plugin,
  type PluginCategory,
} from "@/lib/catalog-shared";

type PluginDirectoryProps = {
  plugins: Plugin[];
};

const statusLabels: Record<Plugin["status"], string> = {
  active: "Active",
  intermittent: "Intermittent",
  unavailable: "Unavailable",
  retired: "Retired",
};

function initials(name: string): string {
  const words = name
    .replace(/[^a-zA-Z0-9 ]/g, " ")
    .trim()
    .split(/\s+/u);
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return `${words[0][0]}${words[1][0]}`.toUpperCase();
}

export function PluginDirectory({ plugins }: PluginDirectoryProps) {
  const [query, setQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<PluginCategory | "all">("all");
  const searchInputRef = useRef<HTMLInputElement>(null);
  const categories = useMemo(
    () => Array.from(new Set(plugins.map((plugin) => plugin.category))).sort(),
    [plugins],
  );
  const filteredPlugins = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return plugins.filter((plugin) => {
      const matchesCategory = activeCategory === "all" || plugin.category === activeCategory;
      const matchesQuery =
        !normalizedQuery ||
        `${plugin.name} ${plugin.id} ${plugin.category}`.toLowerCase().includes(normalizedQuery);
      return matchesCategory && matchesQuery;
    });
  }, [activeCategory, plugins, query]);

  useEffect(() => {
    function focusSearch(event: KeyboardEvent) {
      const target = event.target;
      if (
        event.key !== "/" ||
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        (target instanceof HTMLElement && target.isContentEditable)
      ) {
        return;
      }
      event.preventDefault();
      searchInputRef.current?.focus();
    }

    window.addEventListener("keydown", focusSearch);
    return () => window.removeEventListener("keydown", focusSearch);
  }, []);

  return (
    <div className="directory-shell">
      <div className="directory-toolbar">
        <label className="search-field">
          <SearchIcon width={18} height={18} />
          <span className="sr-only">Search plugins</span>
          <input
            ref={searchInputRef}
            type="search"
            placeholder="Search by plugin or category"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <kbd>/</kbd>
        </label>
        <div className="directory-result-count" aria-live="polite">
          <SlidersIcon width={16} height={16} />
          <span>{filteredPlugins.length} engines</span>
        </div>
      </div>

      <div className="category-tabs" aria-label="Filter by category">
        <button
          className={activeCategory === "all" ? "category-tab is-active" : "category-tab"}
          type="button"
          onClick={() => setActiveCategory("all")}
        >
          All engines
        </button>
        {categories.map((category) => (
          <button
            className={activeCategory === category ? "category-tab is-active" : "category-tab"}
            type="button"
            key={category}
            onClick={() => setActiveCategory(category)}
          >
            {categoryLabel(category)}
          </button>
        ))}
      </div>

      {filteredPlugins.length > 0 ? (
        <div className="plugin-grid">
          {filteredPlugins.map((plugin) => (
            <article className="plugin-card" key={plugin.id}>
              <div className="plugin-card-topline">
                <div className="plugin-avatar" aria-hidden="true">
                  {initials(plugin.name)}
                </div>
                <span className={`status-dot status-${plugin.status}`}>
                  <span className="status-dot-mark" />
                  {statusLabels[plugin.status]}
                </span>
              </div>
              <div className="plugin-card-copy">
                <div className="plugin-name-row">
                  <h3>{plugin.name}</h3>
                  <span className="plugin-category">{categoryLabel(plugin.category)}</span>
                </div>
                <p>
                  Try <span className="query-chip">“{plugin.default_query}”</span>
                </p>
              </div>
              <div className="plugin-card-footer">
                <a href={plugin.site_url} target="_blank" rel="noreferrer">
                  <GlobeIcon width={14} height={14} />
                  Site
                  <ArrowUpRightIcon width={13} height={13} />
                </a>
                <a href={pluginSourceUrl(plugin)} target="_blank" rel="noreferrer">
                  <CodeIcon width={14} height={14} />
                  Source
                </a>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-directory">
          <SearchIcon width={22} height={22} />
          <h3>No engines match that search</h3>
          <p>Try a different name or clear the category filter.</p>
          <button
            type="button"
            onClick={() => {
              setQuery("");
              setActiveCategory("all");
            }}
          >
            Reset filters
          </button>
        </div>
      )}
    </div>
  );
}
