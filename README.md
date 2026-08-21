# qBittorrent search plugins

Standalone qBittorrent search engines for Python 3.9+ and qBittorrent's nova3
search-plugin system. Every file in [`plugins/`](plugins/) can be installed on
its own; the repository does not require a shared runtime module.

## Install in under a minute

Choose one of these paths:

- **One plugin:** download a `.py` file from the [plugin catalog](PLUGINS.md),
  then install it from qBittorrent's Search plugins dialog or drag it into the
  dialog. The optional matching icon is in [`icons/`](icons/).
- **Everything:** download the latest archive from
  [GitHub Releases](https://github.com/UgurGumushan/qbsearch/releases/latest),
  unzip it, quit qBittorrent, and run the installer for your platform.
- **From a clone:** run `./install_plugins.sh` on macOS or Linux, or
  `./install_plugins.ps1` in PowerShell on Windows.

The installer copies engines, matching icons, and support JSON files. It keeps
an existing support file so local qBittorrent settings are not overwritten.
Use `--dry-run` to preview changes and `--plugin yts` to install only one
engine. qBittorrent should be closed before installation and relaunched after.
See [`INSTALL.md`](INSTALL.md) for destination paths and troubleshooting.

## Browse the plugins

[`PLUGINS.md`](PLUGINS.md) is generated from
[`catalog/plugins.json`](catalog/plugins.json) and lists each engine's
category, repository status, site, installable file, and safe default
live-test query. A status describes repository support; it is not a guarantee
that a remote site is online at the moment you search.

Adult-content engines are labeled `adult`. Review the catalog before installing
engines on shared or managed qBittorrent systems.

## Test the live services

The default test command makes real HTTP requests to every configured remote
site, using each plugin's catalog query and a thread pool sized to the machine:

```sh
./test_all_plugins.sh
```

Useful variants:

```sh
./test_all_plugins.sh --plugin yts
./test_all_plugins.sh --content-category anime
./test_all_plugins.sh --query ubuntu
./test_all_plugins.sh --require-results
```

Live tests run each plugin in an isolated subprocess, report individual
pass/fail status, and allow an empty result set by default because a site may
be reachable but have no matching records. `--require-results` makes empty
results fail. Use `--install-only` for an offline import and metadata check;
the deterministic safety suite is run automatically unless `--skip-safety` is
specified.

Do not use sensitive queries in live tests. The query is sent to the remote
service exactly as a normal qBittorrent search would send it.

## Maintainer checks

```sh
make dev-setup
make check
make test-live
make release VERSION=1.0.0
```

`make dev-setup` installs the pinned Ruff and BasedPyright versions and enables
the automatic pre-commit hook. `make check` is deterministic and does not
contact remote sites. Contributor workflow, catalog updates, release packaging,
and CI behavior are documented in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Attribution

This collection incorporates engines from multiple upstream projects. See
[`ATTRIBUTIONS.md`](ATTRIBUTIONS.md) and [`LICENSE.md`](LICENSE.md) for
provenance and per-engine licensing. Source and license fields in the catalog
should be completed or corrected when an engine is changed.
