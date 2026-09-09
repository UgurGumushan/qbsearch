# qBittorrent plugin collection

qbsearch is a standalone, installable collection of qBittorrent nova3 search plugins
for Python 3.9+.

Each file in [`plugins/`](plugins/) is a complete plugin and can be used without any
repository runtime package.

## Install quickly

### One plugin

- Download a plugin file from [`documentation/PLUGINS.md`](documentation/PLUGINS.md).
- In qBittorrent, open **Search** → **Search plugins**, then add the `.py` file or drag it
  into the dialog.
- If available, a matching icon is installed from [`icons/`](icons/).

### Complete collection

- Download the latest archive from [GitHub Releases](https://github.com/UgurGumushan/qbsearch/releases/latest).
- Unzip it and quit qBittorrent.
- Run the installer for your platform:
  - `install/macos.sh`
  - `install/linux.sh`
  - `install/windows.ps1`
- Relaunch qBittorrent.

### From a clone

Run the same platform installer directly from a checkout:

```sh
./install/macos.sh
./install/linux.sh
./install/windows.ps1   # PowerShell
```

### Notes for installation

- Existing qBittorrent support files are preserved during install.
- qBittorrent must be closed during installation.
- See [`documentation/INSTALL.md`](documentation/INSTALL.md) for platform paths and
  troubleshooting.

## Browse and choose plugins

[`documentation/PLUGINS.md`](documentation/PLUGINS.md) is generated from
[`catalog/plugins.json`](catalog/plugins.json) and lists every plugin with:

- category
- repository status (`active`, `intermittent`, `unavailable`, `retired`)
- site URL and safe default test query
- source file link

A status reflects repository maintenance state, not live site uptime.

Adult-content engines are labeled `adult`. Review plugin suitability before installing
on shared systems.

## Need maintainer/developer instructions?

Use [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup, checks, live testing, release
procedures, and maintenance workflows.

## Troubleshooting

- If a plugin does not run, make sure you installed the `.py` file matching your qBittorrent
  build and restarted qBittorrent after install.
- If installation fails, use the relevant installer for your OS again and verify your
  network access and file permissions.

## Screenshot

![](images/screenshot.png)

## Attribution and license

This project includes engines from multiple upstream projects. See
[`documentation/ATTRIBUTIONS.md`](documentation/ATTRIBUTIONS.md) and [`LICENSE.md`](LICENSE.md)
for source and per-engine licensing.
