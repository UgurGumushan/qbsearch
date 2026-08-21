# qBittorrent search plugins

The standalone qBittorrent Python engines are in [`plugins/`](plugins/). Their
optional icon sidecars are kept separately in [`icons/`](icons/) using the same
filename stem, for example `plugins/acgrip.py` and `icons/acgrip.ico`.

## macOS installation

Quit qBittorrent, then run:

```sh
./scripts/install_macos.sh
```

The installer copies the plugins, matching icons, and plugin support JSON files
into qBittorrent's `nova3/engines` directory. Launch qBittorrent afterward so
the Search Plugins window reloads the files and icons. Existing `rutor.json`
settings are preserved.

The qBittorrent drag-and-drop dialog installs only the selected `.py` file, so
using the installer is the reliable way to install the repository's bundled
icons as well.

Every plugin currently has a matching icon sidecar. When a site does not expose
a usable favicon, the icon generator creates a small fallback badge from the
site name so qBittorrent still has an icon to display.

## Testing

Run the complete live smoke suite from a terminal; it searches every plugin's
configured remote service in parallel and reports each plugin's result count:

```sh
./test_all_plugins.sh --query ubuntu
```

The live suite uses one isolated subprocess per plugin, a thread pool sized to
the machine's logical CPU count, a 120-second per-plugin deadline, and the
local deterministic safety tests. Empty result sets are allowed by default and
remain visible in the per-plugin output; `--require-results` makes them fail.
`--install-only` performs the original offline import/metadata check without
contacting remote services.

## Development checks

```sh
ruff check plugins
basedpyright plugins
python3 test_engines.py plugins
```
