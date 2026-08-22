export function printHelp(): void {
  console.log(`Usage: bun run <command> [-- arguments]

Commands:
  check         Run the full deterministic repository check suite
  static-check  Run TypeScript, ESLint, Prettier, and Python checks
  python:check  Run Ruff and BasedPyright checks
  setup         Install pinned Bun/Python checkers and enable the pre-commit hook
  catalog       Regenerate documentation/PLUGINS.md (or pass --check/other catalog flags)
  harden        Audit generated plugin safety helpers (or pass --write/--check)
  icons         Generate plugin icons using Bun and cross-image
  upstream      Import upstream plugin snapshots into external/upstream/
  test:live     Run live plugin tests (pass arguments after --)
  test:live:watch  Run live plugin tests and rerun them when sources change
  release       Build a release ZIP; pass a version or release arguments
`);
}
