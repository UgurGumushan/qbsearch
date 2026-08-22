# Installation

There are two ways to install these engines.

## Install one plugin

1. Open [`PLUGINS.md`](PLUGINS.md) and choose an engine.
2. Download its linked `.py` file.
3. In qBittorrent, open the Search plugins window and install or drag in the
   `.py` file.
4. If you want the icon, copy the matching `.ico` file from [`icons/`](../icons/)
   into the same qBittorrent `nova3/engines` directory.

This path does not require Git, Python, or a checkout of the repository.

## Install the collection

Quit qBittorrent first. From a repository checkout or an extracted release:

### macOS

```sh
./install/macos.sh
```

### Linux

```sh
./install/linux.sh
```

### Windows PowerShell

```powershell
.\install\windows.ps1
```

These installers are dependency-free and do not accept options: each one
installs the complete plugin collection into the platform default directory.

Typical default destinations are:

| Platform | Default directory                                                                         |
| -------- | ----------------------------------------------------------------------------------------- |
| macOS    | `~/Library/Application Support/qBittorrent/nova3/engines`                                 |
| Linux    | `$XDG_DATA_HOME/qBittorrent/nova3/engines`, or `~/.local/share/qBittorrent/nova3/engines` |
| Windows  | `%LOCALAPPDATA%\qBittorrent\nova3\engines`                                                |

The installer copies every `.py` file, its matching `.ico` file, and the
repository support JSON files. It only creates a support JSON file when no file
with that name already exists, preserving local settings such as proxy
configuration.

## After installation

Launch qBittorrent and open the Search tab. If a plugin is missing:

- confirm the file is in the active profile's `nova3/engines` directory;
- check that qBittorrent was fully closed before installation;
- remove an older duplicate with the same filename;
- run `bun run test:live -- --install-only --skip-safety` from the checkout to
  validate all engine metadata and search contracts without network requests.

The live test command is not required for installation and does contact the
remote services. Use it only when you want to check current site behavior.
