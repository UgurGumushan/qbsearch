# Test layout

The executable test entry points stay in `scripts/` so they can be run from a
fresh checkout without a test framework. This directory is reserved for
maintainer-facing test assets:

- `fixtures/` will contain saved remote HTML/JSON responses for parser tests;
- `live/` will contain focused live-service cases that are not part of the
  deterministic pull-request suite;
- `offline/` will contain deterministic parser and safety tests as they grow.

Run the supported commands from the repository root:

```sh
make check
./test_all_plugins.sh --plugin <plugin-id>
```
