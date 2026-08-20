#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
WORKING="$ROOT/working"
mkdir -p "$WORKING"

# All free/public plugin raw URLs from the wiki
URLS=(
"https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/academictorrents.py"
"https://raw.githubusercontent.com/Cc050511/qBit-search-plugins/main/acgrip.py"
"https://raw.githubusercontent.com/hannsen/qbittorrent_search_plugins/master/ali213.py"
"https://raw.githubusercontent.com/nindogo/qbtSearchScripts/master/anidex.py"
"https://raw.githubusercontent.com/AlaaBrahim/qBitTorrent-animetosho-search-plugin/main/animetosho.py"
"https://gist.githubusercontent.com/bebetoh/3bb49cdf2b3718937b5446db1e4a4915/raw/1819e3ed75faa0da1571173a677081dc107054aa/apachetorrent.py"
"https://raw.githubusercontent.com/nklido/qBittorrent_search_engines/master/engines/audiobookbay.py"
"https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/bitsearch.py"
"https://raw.githubusercontent.com/TuckerWarlock/qbittorrent-search-plugins/main/bt4gprx.com/bt4gprx.py"
"https://raw.githubusercontent.com/galaris/BTDigg-qBittorrent-plugin/main/btdig.py"
"https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/calidadtorrent.py"
"https://raw.githubusercontent.com/elazar/qbittorrent-search-plugins/refs/heads/add-cloudtorrents-plugin/nova3/engines/cloudtorrents.py"
"https://raw.githubusercontent.com/MarcBresson/cpasbien/master/src/cpasbien.py"
"https://raw.githubusercontent.com/bugsbringer/qbit-plugins/master/darklibria.py"
"https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/divxtotal.py"
"https://raw.githubusercontent.com/ZH1637/dmhy/main/dmhy.py"
"https://raw.githubusercontent.com/Bioux1/qbtSearchPlugins/main/dodi_repacks.py"
"https://raw.githubusercontent.com/dangar16/dontorrent-plugin/main/dontorrent.py"
"https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/dontorrent.py"
"https://raw.githubusercontent.com/iordic/qbittorrent-search-plugins/master/engines/elitetorrent.py"
"https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/esmeraldatorrent.py"
"https://raw.githubusercontent.com/DrPurp/eztvx-qbittorrent-plugin/main/eztvx.py"
"https://raw.githubusercontent.com/Bioux1/qbtSearchPlugins/main/fitgirl_repacks.py"
"https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/glotorrents.py"
"https://raw.githubusercontent.com/tolotp/qbittorrent-search-plugins-de-busqueda/refs/heads/main/Plugins/goggames.py"
"https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/kickasstorrents.py"
"https://raw.githubusercontent.com/MadeOfMagicAndWires/qBit-plugins/master/l/linuxtracker.py"
"https://raw.githubusercontent.com/nindogo/qbtSearchScripts/master/magnetdl.py"
"https://raw.githubusercontent.com/joseeloren/search-plugins/master/nova3/engines/maxitorrent.py"
"https://raw.githubusercontent.com/iordic/qbittorrent-search-plugins/master/engines/mejortorrent.py"
"https://raw.githubusercontent.com/Cycloctane/qBittorrent-plugins/master/engines/mikan.py"
"https://raw.githubusercontent.com/Cc050511/qBit-search-plugins/main/mikanani.py"
"https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/mypornclub.py"
"https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/naranjatorrent.py"
"https://raw.githubusercontent.com/tolotp/qbittorrent-search-plugins-de-busqueda/refs/heads/main/Plugins/nekobt.py"
"https://raw.githubusercontent.com/libellula/qbt-plugins/main/pantsu.py"
"https://raw.githubusercontent.com/MadeOfMagicAndWires/qBit-plugins/master/engines/nyaapantsu.py"
"https://raw.githubusercontent.com/MadeOfMagicAndWires/qBit-plugins/master/engines/nyaasi.py"
"https://raw.githubusercontent.com/caiocinel/onlinefix-qbittorrent-plugin/main/onlinefix.py"
"https://raw.githubusercontent.com/dangar16/pediatorent-plugin/refs/heads/main/pediatorent.py"
"https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/pediatorent.py"
"https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/pirateiro.py"
"https://gist.githubusercontent.com/bebetoh/b5e1f4731462de9b837f5026617b1d4a/raw/e71d0020078d56d3f7e9a903ca7b4d44774e10f7/redetorrent.py"
"https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/rockbox.py"
"https://raw.githubusercontent.com/imDMG/qBt_SE/master/engines/rutor.py"
"https://raw.githubusercontent.com/Ashalda/sktorrent-qbt/refs/heads/main/sktorrent.py"
"https://raw.githubusercontent.com/hannsen/qbittorrent_search_plugins/master/smallgames.py"
"https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/snowfl.py"
"https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/solidtorrents.py"
"https://raw.githubusercontent.com/kli885/qBittorent-SubsPlease-Search-Plugin/main/subsplease.py"
"https://raw.githubusercontent.com/vt-idiot/qBit-SukebeiNyaa-plugin/master/engines/sukebeisi.py"
"https://raw.githubusercontent.com/phuongtailtranminh/qBittorrent-Nyaa-Search-Plugin-master/nyaa.py"
"https://raw.githubusercontent.com/libellula/qbt-plugins/main/sukebei.py"
"https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/thepiratebay.py"
"https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/therarbg.py"
"https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/tomadivx.py"
"https://raw.githubusercontent.com/BrunoReX/qBittorrent-Search-Plugin-TokyoToshokan/master/tokyotoshokan.py"
"https://raw.githubusercontent.com/menegop/qbfrench/master/torrent9.py"
"https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/torrentdownload.py"
"https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/torrentdownloads.py"
"https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/torrenflix.py"
"https://raw.githubusercontent.com/nindogo/qbtSearchScripts/master/torrentgalaxy.py"
"https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/traht.py"
"https://raw.githubusercontent.com/tolotp/qbittorrent-search-plugins-de-busqueda/refs/heads/main/Plugins/uindex.py"
"https://raw.githubusercontent.com/msagca/qbittorrent-plugins/main/uniondht.py"
"https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/xxxclubto.py"
"https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/yourbittorrent.py"
"https://codeberg.org/lazulyra/qbit-plugins/raw/branch/main/yts/yts.py"
"https://raw.githubusercontent.com/YGGverse/qbittorrent-yggtracker-search-plugin/main/yggtracker.py"
)

OK=0; FAIL=0; ERR=""

fetch_one() {
    local url="$1" outfile="$2"
    curl -fsSL --connect-timeout 8 --max-time 25 -o "$outfile" "$url" 2>/dev/null && [ -s "$outfile" ]
}

echo "=== Downloading $(wc -l <<< "${URLS[@]}") free plugins ==="

for url in "${URLS[@]}"; do
    stem=$(basename "$url" .py)
    outfile="$WORKING/${stem}.py"
    
    if fetch_one "$url" "$outfile"; then
        ((OK++)) || true
    else
        echo "FAIL: $url"
        ERR="${ERR}\n$url"
        ((FAIL++)) || true
    fi
done

echo ""
echo "=== Result: $OK OK, $FAIL FAIL ==="
[ -z "$ERR" ] && echo "All downloads succeeded."