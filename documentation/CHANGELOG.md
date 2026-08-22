# Changelog

## Unreleased

## 0.1.4

- Added a catalog-driven user installation and plugin discovery workflow.
- Added cross-platform collection installers and release ZIP packaging.
- Replaced the Python collection installer with dependency-free native scripts
  under `install/` and removed the obsolete compatibility wrappers.
- Added generated plugin documentation and maintainer guidance.
- Moved live-test default queries out of the test runner and into the catalog.
- Replaced Make-based maintainer commands with a Bun command surface and Bun test runner.
- Migrated live plugin smoke tests and their helper suite to TypeScript/Bun;
  live checks no longer start Python processes.
- Consolidated shared process and catalog tooling, and corrected the public
  documentation directory name to `documentation/`.

## 0.1.3

- Hardened all plugin engines and support tooling for strict linting and type checking while preserving qBittorrent Python 3.9 compatibility.
- Added safer live-test adapters and runtime validation across the plugin collection.
- Fixed live testing for AnimeTosho feeds that omit peer counts.
