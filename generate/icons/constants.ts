import { ICON_DIR, PLUGIN_DIR } from "../../scripts/repository";

export { ICON_DIR, PLUGIN_DIR };
export const MANIFEST = "/tmp/icon_manifest.json";
export const USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36";
export const TIMEOUT_MS = 10_000;

export const RE_URL_ATTR = /^[ \t]+url[ \t]*=[ \t]*['"](https?:\/\/[^'"]+)['"]/m;
export const RE_URL_NAME = /^[ \t]+url[ \t]*=[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*$/m;
export const RE_CONST = /^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*['"](https?:\/\/[^'"]+)['"]/gm;

export const EXTRA_ICON_URLS: Record<string, string> = {
  darklibria: "https://raw.githubusercontent.com/bugsbringer/qbit-plugins/master/darklibria.png",
  magnetdl:
    "https://raw.githubusercontent.com/hannsen/qbittorrent_search_plugins/00e876a51f2cb45ee22071c56fc7ba52dc117721/magnetdl.png",
  nyaapantsu: "https://raw.githubusercontent.com/4chenz/pantsu-plugin/master/pantsu.png",
  rockbox: "https://raw.githubusercontent.com/Pireo/hello-world/master/rockbox.png",
  torrent9: "https://raw.githubusercontent.com/menegop/qbfrench/master/torrent9.png",
  uniondht: "https://raw.githubusercontent.com/msagca/qbittorrent-plugins/main/uniondht_icon.png",
};
