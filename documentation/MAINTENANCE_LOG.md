# qbsearch maintenance log

Use this file to record evidence-backed plugin status transitions and operational notes.

| Date (UTC) | Plugin ID     | From         | To           | Evidence query     | Result  | Notes                                                              |
| ---------- | ------------- | ------------ | ------------ | ------------------ | ------- | ------------------------------------------------------------------ |
| 2026-09-06 | pirateiro     | active       | unavailable  | ubuntu             | failed  | `pirateiro.io` reported NXDOMAIN; mirror unreachable.              |
| 2026-09-09 | ali213        | unavailable  | unavailable  | maintenance-review | blocked | Catalog kept as `unavailable` while awaiting focused revalidation  |
| 2026-09-09 | bitsearch     | unavailable  | unavailable  | maintenance-review | blocked | Catalog kept as `unavailable` while awaiting focused revalidation  |
| 2026-09-09 | pirateiro     | unavailable  | unavailable  | maintenance-review | blocked | Catalog kept as `unavailable` while awaiting focused revalidation  |
| 2026-09-09 | solidtorrents | unavailable  | unavailable  | maintenance-review | blocked | Catalog kept as `unavailable` while awaiting focused revalidation  |
| 2026-09-09 | traht         | intermittent | intermittent | maintenance-review | blocked | Catalog kept as `intermittent` while awaiting focused revalidation |

## Log format

- Date: `YYYY-MM-DD`
- Plugin ID: catalog `id`
- From / To: plugin `status`
- Evidence query: query used during `bun run test -- --live --plugin <id>`
- Result: `ok`, `empty`, `failed`, or `blocked`
- Notes: concise explanation and links to follow-up actions
