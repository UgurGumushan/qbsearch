# Installation

There are two ways to install these engines.

## Install one plugin

1. Open [`PLUGINS.md`](PLUGINS.md) and choose an engine.
2. Download its linked `.py` file.
3. In qBittorrent, open the Search plugins window and install or drag in the
   `.py` file.
4. If you want the icon, copy the matching `.ico` file from [`icons/`](icons/)
   into the same qBittorrent `nova3/engines` directory.

This path does not require Git, Python, or a checkout of the repository.

## Install the collection

Quit qBittorrent first. From a repository checkout or an extracted release:

### macOS and Linux

```sh
./install_plugins.sh
```

The historical macOS command remains available:

```sh
./scripts/install_macos.sh
```

### Windows PowerShell

```powershell
.\install_plugins.ps1
```

The installer uses Python 3.9 or newer and supports the same options on every
platform:

```sh
./install_plugins.sh --dry-run
./install_plugins.sh --plugin yts
./install_plugins.sh --plugin yts --destination /path/to/nova3/engines
```

If the automatic destination is not correct for a custom qBittorrent profile,
set it explicitly with `--destination` or the `QBITTORRENT_ENGINES_DIR`
environment variable.

Typical default destinations are:

| Platform | Default directory |
| --- | --- |
| macOS | `~/Library/Application Support/qBittorrent/nova3/engines` |
| Linux | `$XDG_DATA_HOME/qBittorrent/nova3/engines`, or `~/.local/share/qBittorrent/nova3/engines` |
| Windows | `%LOCALAPPDATA%\qBittorrent\nova3\engines` |

The installer copies `.py` files and matching icons. It copies repository
support JSON files only when no file with that name already exists, preserving
local settings such as proxy configuration.

## After installation

Launch qBittorrent and open the Search tab. If a plugin is missing:

- confirm the file is in the active profile's `nova3/engines` directory;
- check that qBittorrent was fully closed before installation;
- remove an older duplicate with the same filename;
- run `python3 test_engines.py plugins` from the checkout to validate all
  engines.

The live test command is not required for installation and does contact the
remote services. Use it only when you want to check current site behavior.
