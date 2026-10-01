# qbsearch maintenance log

Use this file to record evidence-backed plugin status transitions and operational notes.

| Date (UTC) | Plugin ID     | From         | To           | Evidence query     | Result  | Notes                                                                                                                                                                                                                                                                   |
| ---------- | ------------- | ------------ | ------------ | ------------------ | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-09-06 | pirateiro     | active       | unavailable  | ubuntu             | failed  | `pirateiro.io` reported NXDOMAIN; mirror unreachable.                                                                                                                                                                                                                   |
| 2026-09-09 | ali213        | unavailable  | unavailable  | maintenance-review | blocked | Catalog kept as `unavailable` while awaiting focused revalidation                                                                                                                                                                                                       |
| 2026-09-09 | bitsearch     | unavailable  | unavailable  | maintenance-review | blocked | Catalog kept as `unavailable` while awaiting focused revalidation                                                                                                                                                                                                       |
| 2026-09-09 | pirateiro     | unavailable  | unavailable  | maintenance-review | blocked | Catalog kept as `unavailable` while awaiting focused revalidation                                                                                                                                                                                                       |
| 2026-09-09 | solidtorrents | unavailable  | unavailable  | maintenance-review | blocked | Catalog kept as `unavailable` while awaiting focused revalidation                                                                                                                                                                                                       |
| 2026-09-09 | traht         | intermittent | intermittent | maintenance-review | blocked | Catalog kept as `intermittent` while awaiting focused revalidation                                                                                                                                                                                                      |
| 2026-10-01 | ali213        | unavailable  | unavailable  | minecraft          | ok      | Two remote probes returned HTTP 200, redirected to `so.ali213.net`, and found 3 markers; changed parser and download chain remain unverified.                                                                                                                           |
| 2026-10-01 | bitsearch     | unavailable  | unavailable  | inception          | ok      | Two remote probes redirected to `bitsearch.eu` and returned HTTP 200 with 80 markers; parser output remains unverified.                                                                                                                                                 |
| 2026-10-01 | pirateiro     | unavailable  | unavailable  | inception          | empty   | Two remote probes reached the search page with HTTP 200 and zero markers; earlier DNS failure no longer reproduced; parser output remains unverified.                                                                                                                   |
| 2026-10-01 | solidtorrents | unavailable  | unavailable  | ubuntu             | ok      | Two remote probes redirected to Bitsearch at `bitsearch.eu` and returned HTTP 200 with 81 markers; Solid Torrents parser remains unverified.                                                                                                                            |
| 2026-10-01 | traht         | intermittent | intermittent | inception          | empty   | Two remote probes returned HTTP 200 with an empty body and zero markers; usability remains unverified.                                                                                                                                                                  |
| 2026-10-01 | elitetorrent  | active       | active       | inception          | empty   | Focused marker-required probe of the refreshed URL fixture found zero result markers; parser functionality remains unverified; retain status pending follow-up triage.                                                                                                  |
| 2026-10-01 | elitetorrent  | active       | active       | inception, matrix  | ok      | Restored encoded `i` extraction with trailing `&st=et`; focused marker-required probes pass. Fresh Bun captures replayed through the actual Python engine emitted 1 and 5 usable magnet records respectively, with no unexpected requests; two-page/five-detail limits. |
| 2026-10-01 | bitsearch     | unavailable  | unavailable  | inception, ubuntu  | ok      | Functional pass 1 replayed fresh Bun captures: 40 usable magnet records per query from two pages, HTTP 200 redirects to bitsearch.eu, no unexpected requests.                                                                                                           |
| 2026-10-01 | bitsearch     | unavailable  | unavailable  | inception, ubuntu  | failed  | Functional pass 2 emitted 40 inception records but Ubuntu page 2 returned HTTP 429; the clean-run streak reset. Keep unavailable while gathering two consecutive clean passes.                                                                                          |
| 2026-10-01 | bitsearch     | unavailable  | unavailable  | inception, ubuntu  | ok      | After cooldown, functional pass 3 emitted 40 usable magnet records per query from two pages; every response returned HTTP 200 on one attempt. New recovery streak: 1.                                                                                                   |
| 2026-10-01 | bitsearch     | unavailable  | intermittent | inception, ubuntu  | ok      | Functional pass 4 emitted 40 usable magnet records per query from two pages, with HTTP 200 on every request and no retries. Passes 3 and 4 are consecutive clean runs after cooldown against the same engine source, satisfying initial recovery.                       |

## Log format

- Date: `YYYY-MM-DD`
- Plugin ID: catalog `id`
- From / To: plugin `status`
- Evidence query: query used during `bun run test -- --live --plugin <id>`
- Result: `ok`, `empty`, `failed`, or `blocked`
- Notes: concise explanation and links to follow-up actions

Remote probes inspect endpoint responses and generic result markers; they do not execute the Python search parser. An `ok` probe alone does not establish functional recovery or justify a status promotion.

## Maintenance branch review — 2026-10-01

Reviewed `5070272`, `a7bd076`, and `5927b73` against release baseline `fb7ace9`.
The review covered standalone Python 3.9 compatibility, result dictionaries,
parser boundaries and deduplication, HTTP budgets and rate limits, generated
preambles and response-context cleanup, and deterministic check failure propagation.

The review found that an interrupted HTTP 429 body triggered up to six requests
across the two recovery queries, while an oversized body allowed the second query
to proceed. Both paths lost the response status and retry-window evidence. Offline
regression tests reproduced these failures. The HTTP worker now retains status
and `Retry-After` when a 429 body cannot be read safely, makes only one request,
and stops subsequent queries. An unreadable body is stored as empty; ordinary
response byte limits continue to reject oversized responses.

This correction changes only test infrastructure. Bitsearch's source hash and
initial recovery evidence remain valid. Daily promotion checks are still pending;
the review and offline tests do not count as additional functional passes.

Verification passed on Python 3.9.6 and 3.11.15: full strict checks with 54 tests
on each interpreter, static checks, generated-file audits, and the website production
build. All 49 catalog IDs and plugin version values match the release baseline;
Bitsearch's source hash matches both qualifying initial-recovery reports. The
plugin quality audit still reports 40 existing advisory warnings and zero errors.

## Bitsearch promotion follow-up

Initial recovery completed on 2026-10-01. Bitsearch is `intermittent`; promotion to
`active` requires three additional clean functional passes on separated days.
The earlier HTTP 429 failure remains recorded above and did not count toward recovery.

| Date (Europe/Istanbul) | Check                                                   | Outcome |
| ---------------------- | ------------------------------------------------------- | ------- |
| 2026-10-02             | Fresh inception/ubuntu capture and actual-parser replay | Pending |
| 2026-10-03             | Fresh inception/ubuntu capture and actual-parser replay | Pending |
| 2026-10-04             | Fresh inception/ubuntu capture and actual-parser replay | Pending |

On each listed date, confirm the current source hash with
`shasum -a 256 plugins/bitsearch.py`, then run the internal helper documented in
[test/README.md](../test/README.md#functional-recovery-evidence) with Python 3.9.
It records timestamps, redirects, response limits, actual result dictionaries,
and failures in `working/recovery/`. These are manual follow-up dates, not an
installed background schedule. Each pass must report `clean: true`, produce
valid nonempty records for both queries without unexpected requests, and use
the same engine source:

```text
87cf63ef182f3e3caed0c19f88d55cf41fd19ee3cc9a243f2af5b0134810d9ab
```

Record each outcome here and in the evidence table, including UTC start/finish
timestamps, Istanbul date, source hash, result counts, capture paths, and any
failure or rate-limit evidence. Result counts may vary; both queries must have
usable records. Commit each pre-promotion day's evidence locally as
`Record Bitsearch recovery check for YYYY-MM-DD`; include the last qualifying
pass in the promotion commit. Full captures remain ignored working files.

Count at most one qualifying pass per Istanbul calendar day, with all three
dates later than 2026-10-01. A failed daily pass resets the clean-pass count;
move the remaining checks to later dates until three clean daily passes succeed.
A missed checkpoint earns no credit; reschedule it without treating absence
as a failed run. On HTTP 429, stop that checkpoint and respect `Retry-After`;
without a supplied retry window, defer further probing to the next daily checkpoint.
Engine changes invalidate prior evidence: establish two fresh consecutive clean
initial-recovery passes, then three additional clean passes on separate days.

After three qualifying daily passes, append the status-transition evidence before
editing the catalog, set Bitsearch to `active`, regenerate catalog documentation,
run the strict checks on Python 3.9 and 3.11 and the website build, and commit as
`Promote Bitsearch after separated functional checks`:

```sh
bun run gen -- --write --only catalog
QBSEARCH_PYTHON=/usr/bin/python3 bun run check -- --strict
QBSEARCH_PYTHON=/Users/ugurgumushan/.local/bin/python3.11 bun run check -- --strict
bun run gen -- --check
bun run --cwd packages/website build
git diff --check
```

Verify the promotion diff contains only the recovery evidence, Bitsearch status
and notes, and generated catalog listing. Preserve the qualifying engine source
and version declarations, pass the pre-commit hook, and finish with a clean tree.
Delivery remains local commits; publication and release preparation are later decisions.
