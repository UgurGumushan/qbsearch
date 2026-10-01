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

## Bitsearch promotion follow-up

Initial recovery completed on 2026-10-01. Bitsearch is `intermittent`; promotion to
`active` requires three additional clean functional passes on separated days.
The earlier HTTP 429 failure remains recorded above and did not count toward recovery.

| Date (Europe/Istanbul) | Check                                                   | Outcome |
| ---------------------- | ------------------------------------------------------- | ------- |
| 2026-10-02             | Fresh inception/ubuntu capture and actual-parser replay | Pending |
| 2026-10-03             | Fresh inception/ubuntu capture and actual-parser replay | Pending |
| 2026-10-04             | Fresh inception/ubuntu capture and actual-parser replay | Pending |

Run the internal helper documented in [test/README.md](../test/README.md#functional-recovery-evidence)
once on each listed date. It records timestamps, redirects, response limits, actual
result dictionaries, and failures in `working/recovery/`. These are follow-up dates,
not an installed background schedule. Each pass must produce usable records for both
queries, without unexpected requests, against the same engine source:

```text
87cf63ef182f3e3caed0c19f88d55cf41fd19ee3cc9a243f2af5b0134810d9ab
```

Record each outcome here and in the evidence table. Wait for a rate-limit retry window
before further requests. A failed daily pass resets the clean-pass count; move the
remaining checks to the following days until three separated clean passes succeed.
Engine changes invalidate prior evidence and require a new initial recovery streak.

After three qualifying daily passes, append the status-transition evidence before
editing the catalog, set Bitsearch to `active`, regenerate catalog documentation,
run the strict checks on Python 3.9 and 3.11 and the website build, and commit as
`Promote Bitsearch after separated functional checks`.
