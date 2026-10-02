# License provenance audit

The nine original 2026-10-03 additions (`aniliberty`, `filemood`,
`internetarchive`, `knaben`, `linuxtracker`, `torlock`, `torrentclaw`,
`torrentfunk`, `uindex`) are new repository implementations under
GPL-3.0-or-later. Protocol references and verification limits are in
[NEW_PLUGINS.md](NEW_PLUGINS.md). No upstream implementation, tracker passkey
list or brand icon is incorporated. Historical engine licenses below are
unchanged.

Audit date: 2026-10-01 (UTC). This records the primary-source evidence for the
26 catalog entries previously marked `Unknown`. Catalog labels describe the
identified upstream license; they do not replace the notices in [LICENSE.md](../LICENSE.md)
or assign a collection-wide license.

The audit checked each catalog source URL and the upstream repository license,
README, and complete recursive tree where a license was found. No nested license
overrides were present in those six repositories. [LightDestory's README](https://github.com/LightDestory/qBittorrent-Search-Plugins#warning-license) explicitly
licenses repository content under GPL-3.0 except the qBittorrent nova scripts; the
six search engines are under `src/engines/`. The five MIT grants include the upstream
copyright notices and correspond to the credited engine authors. Exact upstream
texts are copied under [licenses/](licenses/) and included in release archives.
Existing original-header license notices remain intact.

Eleven catalog labels are now verified (six GPL-3.0, five MIT); fifteen remain
`Unknown`. The GPL-3.0 label follows the upstream README without inventing an
`-only` or `-or-later` grant. A bare root GPL-2.0 text in [Jose Lorenzo's third-party qBittorrent collection](https://github.com/joseeloren/search-plugins)
does not establish a specific Maxitorrent grant:
its source has no license statement, and the README identifies third-party plugins.
That entry remains unresolved pending a per-engine or author-wide grant.

| Plugin             | Audited source                                                                                                                                                 | Evidence and disposition                                                                                                                                                                                                 |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `academictorrents` | [source](https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/academictorrents.py) (HTTP 200)                          | GPL-3.0; [upstream grant](https://github.com/LightDestory/qBittorrent-Search-Plugins/blob/master/LICENSE) and [notice copy](licenses/LightDestory-GPL-3.0.txt). License blob `f288702d2fa16d3cdf0035b15a9fcbc552cd88e7`. |
| `ali213`           | [source](https://raw.githubusercontent.com/hannsen/qbittorrent_search_plugins/master/ali213.py) (HTTP 200)                                                     | Unknown; source HTTP 200 with no license statement; GitHub repository license API HTTP 404.                                                                                                                              |
| `apachetorrent`    | [source](https://gist.githubusercontent.com/bebetoh/3bb49cdf2b3718937b5446db1e4a4915/raw/1819e3ed75faa0da1571173a677081dc107054aa/apachetorrent.py) (HTTP 200) | Unknown; gist contains only the engine file with no license grant.                                                                                                                                                       |
| `bt4gprx`          | [source](https://raw.githubusercontent.com/TuckerWarlock/qbittorrent-search-plugins/main/bt4gprx.com/bt4gprx.py) (HTTP 200)                                    | Unknown; source HTTP 200 with no license statement; GitHub repository license API HTTP 404.                                                                                                                              |
| `darklibria`       | [source](https://raw.githubusercontent.com/bugsbringer/qbit-plugins/master/darklibria.py) (HTTP 200)                                                           | Unknown; source HTTP 200 with no license statement; GitHub repository license API HTTP 404.                                                                                                                              |
| `dodi_repacks`     | [source](https://raw.githubusercontent.com/Bioux1/qbtSearchPlugins/main/dodi_repacks.py) (HTTP 200)                                                            | Unknown; source HTTP 200 with no license statement; GitHub repository license API HTTP 404.                                                                                                                              |
| `elitetorrent`     | [source](https://raw.githubusercontent.com/iordic/qbittorrent-search-plugins/master/engines/elitetorrent.py) (HTTP 200)                                        | MIT; [upstream grant](https://github.com/iordic/qbittorrent-search-plugins/blob/master/LICENSE) and [notice copy](licenses/iordic-MIT.txt). License blob `b4759f9386c2e83dd4f8aab275848cb7c7db56b5`.                     |
| `eztvx`            | [source](https://raw.githubusercontent.com/DrPurp/eztvx-qbittorrent-plugin/main/eztvx.py) (HTTP 200)                                                           | Unknown; source HTTP 200 with no license statement; GitHub repository license API HTTP 404.                                                                                                                              |
| `fitgirl_repacks`  | [source](https://raw.githubusercontent.com/Bioux1/qbtSearchPlugins/main/fitgirl_repacks.py) (HTTP 200)                                                         | Unknown; source HTTP 200 with no license statement; GitHub repository license API HTTP 404.                                                                                                                              |
| `maxitorrent`      | [source](https://raw.githubusercontent.com/joseeloren/search-plugins/master/nova3/engines/maxitorrent.py) (HTTP 200)                                           | Unknown; root GPL-2.0 text exists, but applicability to this third-party engine is unconfirmed.                                                                                                                          |
| `mikan`            | [source](https://raw.githubusercontent.com/Cycloctane/qBittorrent-plugins/master/engines/mikan.py) (HTTP 200)                                                  | MIT; [upstream grant](https://github.com/Cycloctane/qBittorrent-plugins/blob/master/LICENSE) and [notice copy](licenses/Cycloctane-MIT.txt). License blob `a5a2f2004d8cf666346c96a900746c3801fbd348`.                    |
| `nekobt`           | [source](https://raw.githubusercontent.com/tolotp/qbittorrent-search-plugins-de-busqueda/refs/heads/main/Plugins/nekobt.py) (HTTP 200)                         | MIT; [upstream grant](https://github.com/tolotp/qbittorrent-search-plugins-de-busqueda/blob/main/LICENSE) and [notice copy](licenses/tolotp-MIT.txt). License blob `fdced37ca0b29ff2c9e560f179873a247d6afde0`.           |
| `nyaa_phuong`      | [source](https://raw.githubusercontent.com/phuongtailtranminh/qBittorrent-Nyaa-Search-Plugin-master/nyaa.py) (HTTP 404)                                        | Unknown; catalog source HTTP 404 and repository license API HTTP 404. No grant recovered.                                                                                                                                |
| `onlinefix`        | [source](https://raw.githubusercontent.com/caiocinel/onlinefix-qbittorrent-plugin/main/onlinefix.py) (HTTP 200)                                                | Unknown; source HTTP 200 with no license statement; GitHub repository license API HTTP 404.                                                                                                                              |
| `pirateiro`        | [source](https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/pirateiro.py) (HTTP 200)                                 | GPL-3.0; [upstream grant](https://github.com/LightDestory/qBittorrent-Search-Plugins/blob/master/LICENSE) and [notice copy](licenses/LightDestory-GPL-3.0.txt). License blob `f288702d2fa16d3cdf0035b15a9fcbc552cd88e7`. |
| `rutor`            | [source](https://raw.githubusercontent.com/imDMG/qBt_SE/master/engines/rutor.py) (HTTP 200)                                                                    | MIT; [upstream grant](https://github.com/imDMG/qBt_SE/blob/master/LICENSE) and [notice copy](licenses/imDMG-MIT.txt). License blob `bb49248afc103fc368b507eef7086fb7daf65e7d`.                                           |
| `sktorrent`        | [source](https://raw.githubusercontent.com/Ashalda/sktorrent-qbt/refs/heads/main/sktorrent.py) (HTTP 200)                                                      | Unknown; source HTTP 200 with no license statement; GitHub repository license API HTTP 404.                                                                                                                              |
| `smallgames`       | [source](https://raw.githubusercontent.com/hannsen/qbittorrent_search_plugins/master/smallgames.py) (HTTP 200)                                                 | Unknown; source HTTP 200 with no license statement; GitHub repository license API HTTP 404.                                                                                                                              |
| `snowfl`           | [source](https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/snowfl.py) (HTTP 200)                                    | GPL-3.0; [upstream grant](https://github.com/LightDestory/qBittorrent-Search-Plugins/blob/master/LICENSE) and [notice copy](licenses/LightDestory-GPL-3.0.txt). License blob `f288702d2fa16d3cdf0035b15a9fcbc552cd88e7`. |
| `subsplease`       | [source](https://raw.githubusercontent.com/kli885/qBittorent-SubsPlease-Search-Plugin/main/subsplease.py) (HTTP 200)                                           | Unknown; source HTTP 200 with no license statement; GitHub repository license API HTTP 404.                                                                                                                              |
| `thepiratebay`     | [source](https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/thepiratebay.py) (HTTP 200)                              | GPL-3.0; [upstream grant](https://github.com/LightDestory/qBittorrent-Search-Plugins/blob/master/LICENSE) and [notice copy](licenses/LightDestory-GPL-3.0.txt). License blob `f288702d2fa16d3cdf0035b15a9fcbc552cd88e7`. |
| `tokyotoshokan`    | [source](https://raw.githubusercontent.com/BrunoReX/qBittorrent-Search-Plugin-TokyoToshokan/master/tokyotoshokan.py) (HTTP 200)                                | MIT; [upstream grant](https://github.com/BrunoReX/qBittorrent-Search-Plugin-TokyoToshokan/blob/master/LICENSE) and [notice copy](licenses/Douman-MIT.txt). License blob `33d74f4d20b2b6b13eb024429ed061f77893b1a9`.      |
| `torrentdownload`  | [source](https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/torrentdownload.py) (HTTP 200)                           | GPL-3.0; [upstream grant](https://github.com/LightDestory/qBittorrent-Search-Plugins/blob/master/LICENSE) and [notice copy](licenses/LightDestory-GPL-3.0.txt). License blob `f288702d2fa16d3cdf0035b15a9fcbc552cd88e7`. |
| `uniondht`         | [source](https://raw.githubusercontent.com/msagca/qbittorrent-plugins/main/uniondht.py) (HTTP 404)                                                             | Unknown; catalog source HTTP 404 and repository license API HTTP 404. No grant recovered.                                                                                                                                |
| `yourbittorrent`   | [source](https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/yourbittorrent.py) (HTTP 200)                            | GPL-3.0; [upstream grant](https://github.com/LightDestory/qBittorrent-Search-Plugins/blob/master/LICENSE) and [notice copy](licenses/LightDestory-GPL-3.0.txt). License blob `f288702d2fa16d3cdf0035b15a9fcbc552cd88e7`. |
| `yts`              | [source](https://codeberg.org/lazulyra/qbit-plugins/raw/branch/main/yts/yts.py) (HTTP 200)                                                                     | Unknown; complete Codeberg repository tree contains no license file and source has no grant.                                                                                                                             |

## Captured evidence

The raw primary-source responses are ignored artifacts in `working/license-audit.json`
and `working/license-scope.json`. These source SHA-256 values let a later audit
identify the exact engine contents checked; unavailable URLs retain their HTTP
status rather than a fabricated source digest.

| Plugin             | Source SHA-256                                                     |
| ------------------ | ------------------------------------------------------------------ |
| `academictorrents` | `5a4e025814e1fc8ae97a6c267fb706e03976fef1b629cb63eeb9944ebd9b49d3` |
| `ali213`           | `ca6167e6717896f4034fa14b1ad773b3ab613a643a6bd435b664788ab5a8022b` |
| `apachetorrent`    | `528566aa9144ccfec70e862e0af9ebc51c794979f181ae7146b04bca9b5ec105` |
| `bt4gprx`          | `9c6cc2672592239c18f75d9c3c939d1f3e3b952a556fc196dc8fe3f8b18469ac` |
| `darklibria`       | `c2e2cd728b69e3a1ddb75374dc95a0010b6f85d037dc9f38eefb48c7f42b058f` |
| `dodi_repacks`     | `51b49a2c181088da532afa2fdd75b64e480d20f0d67c83076a1f85bc16bd8506` |
| `elitetorrent`     | `181186dbb86f5b3b817ac97d96169ea0c5b0d907a9ddb0cff204456a8014e994` |
| `eztvx`            | `07383109341fd035073f35ca3ddcd9095a407afcba8248b573419ae90759767a` |
| `fitgirl_repacks`  | `3285f800eac78beb6bec8ad0503d34966abcea36ecbf802048e87a46b6965bd2` |
| `maxitorrent`      | `7dfd624b206f74a4f65dbb47f430082dac580a75e8edb657ef6b90d576b485a0` |
| `mikan`            | `91d6a0a308443fbb8501a1238a07179630ee34d1b253a5248b8dbfbcc88a4907` |
| `nekobt`           | `29aba65332f19823208c1186d4366b5d909f0cab4043a6876f204e417819964a` |
| `nyaa_phuong`      | HTTP 404; source unavailable                                       |
| `onlinefix`        | `614fbe675d23bc60def90828aef3d8b4b2f2bf1ccdd58c395f0dc4e686f2f155` |
| `pirateiro`        | `eb71a8f5e9cd05b5e469193cc5960c2ba9c109fafc8498752c868e1dabe26f15` |
| `rutor`            | `1cf9c5c302ad8defbe6ddb90bcbdf56cc905b49517b9233618b0f5a252845913` |
| `sktorrent`        | `a917b482741a0b301f09ce0c1edbfe5d7b4663c2367ede1a1bcde2641d62e28c` |
| `smallgames`       | `7d1086be858e8b4f59fc8c8c201b612c740a1b22c98a75b27477a1f00f1ed233` |
| `snowfl`           | `04a1f767f03c18134ce193eabcda43f4c37c53d56ed06d67b4fc7627ca0eb710` |
| `subsplease`       | `3348ff9076b03c34ce87152597ffe0034ce1e192520d79b154952aa862bfc21c` |
| `thepiratebay`     | `0a8e83eeaf15aa65a714828d28ef9b6a99139c6e056298671d4a1d5c6a7437d5` |
| `tokyotoshokan`    | `e0cac329d5787d9a83a5bb7365af64fa939152dd5b9104daeaa1a37713c0dbe5` |
| `torrentdownload`  | `4f7f8b025c25d6a73d20a34befcc206421e7e74f6ff607a985bf2dc9bcef6aa7` |
| `uniondht`         | HTTP 404; source unavailable                                       |
| `yourbittorrent`   | `5aeccc1e6addce6e632d159b412cd43335c6dc8a31a55397655af1dd14938187` |
| `yts`              | `cb066319b5f6092621b21debc4303d937bacd2bdaef643f1740a516145cbfb9e` |

| Upstream repository                                                                                                     | Complete tree SHA                          | License notice                                                |
| ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------- |
| [LightDestory/qBittorrent-Search-Plugins](https://github.com/LightDestory/qBittorrent-Search-Plugins)                   | `0d3b18677c6f059031149abc7c2f46e994354298` | [LightDestory-GPL-3.0.txt](licenses/LightDestory-GPL-3.0.txt) |
| [iordic/qbittorrent-search-plugins](https://github.com/iordic/qbittorrent-search-plugins)                               | `1f15272ad0140b1545b8732c13926fd467aa8f8b` | [iordic-MIT.txt](licenses/iordic-MIT.txt)                     |
| [Cycloctane/qBittorrent-plugins](https://github.com/Cycloctane/qBittorrent-plugins)                                     | `c89a99b06d66293e6974c8ff42429fe0932facce` | [Cycloctane-MIT.txt](licenses/Cycloctane-MIT.txt)             |
| [tolotp/qbittorrent-search-plugins-de-busqueda](https://github.com/tolotp/qbittorrent-search-plugins-de-busqueda)       | `b70fafa9f6615d9ddb327eaeeaa5594dfcc97c35` | [tolotp-MIT.txt](licenses/tolotp-MIT.txt)                     |
| [imDMG/qBt_SE](https://github.com/imDMG/qBt_SE)                                                                         | `a53fe22e8810c65a45cde8ccf4b61fa2647bf7e2` | [imDMG-MIT.txt](licenses/imDMG-MIT.txt)                       |
| [BrunoReX/qBittorrent-Search-Plugin-TokyoToshokan](https://github.com/BrunoReX/qBittorrent-Search-Plugin-TokyoToshokan) | `000c96e9d08ce1c4f96c5f76b758875370d27e18` | [Douman-MIT.txt](licenses/Douman-MIT.txt)                     |
