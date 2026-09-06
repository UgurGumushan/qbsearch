export const RAW_PLUGIN_BASE =
  "https://raw.githubusercontent.com/UgurGumushan/qbsearch/main/plugins/";

export const VALID_CATEGORIES = new Set([
  "adult",
  "anime",
  "books",
  "games",
  "general",
  "movies",
  "music",
  "software",
  "tv",
]);

export const VALID_STATUSES = new Set([
  "active",
  "intermittent",
  "unavailable",
  "requires-account",
  "retired",
]);

/** Hints used only when bootstrapping a new catalog. */
export const CATEGORY_HINTS: Record<string, Set<string>> = {
  adult: new Set(["mypornclub", "nyaa_phuong", "nyaapantsu", "sukebeisi", "xxxclubto"]),
  anime: new Set([
    "acgrip",
    "anidex",
    "animetosho",
    "dmhy",
    "mikan",
    "mikanani",
    "nekobt",
    "nyaasi",
    "subsplease",
    "tokyotoshokan",
  ]),
  books: new Set(["audiobookbay", "darklibria"]),
  games: new Set([
    "ali213",
    "dodi_repacks",
    "fitgirl_repacks",
    "goggames",
    "onlinefix",
    "smallgames",
  ]),
  movies: new Set([
    "apachetorrent",
    "calidadtorrent",
    "cpasbien",
    "divxtotal",
    "dontorrent",
    "elitetorrent",
    "esmeraldatorrent",
    "maxitorrent",
    "mejortorrent",
    "naranjatorrent",
    "pirateiro",
    "redetorrent",
    "therarbg",
    "tomadivx",
    "torrent9",
    "traht",
    "yts",
  ]),
  software: new Set(["academictorrents", "bt4gprx", "rockbox"]),
  tv: new Set(["eztvx"]),
};
