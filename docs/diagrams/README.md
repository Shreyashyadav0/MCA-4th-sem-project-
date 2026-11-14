# Analysis diagrams (MCSP-232)

Eleven figures for the project report, drawn with matplotlib — no graphviz, no
external images, no network access. Two deterministic generators produce them,
and `planning.md` (the PERT arithmetic) is emitted by the second one.

| File | Figure | What it is | Generator |
|---|---|---|---|
| `dfd-level-0.png` | Figure 1 | DFD level 0, the context diagram | `make_diagrams.py` |
| `dfd-level-1.png` | Figure 2 | DFD level 1, the seven processes | `make_diagrams.py` |
| `dfd-level-2.png` | Figure 3 | DFD level 2, processes 2.0 and 3.0 decomposed | `make_diagrams.py` |
| `er-diagram.png` | Figure 4 | ER diagram, the six-table schema | `make_diagrams.py` |
| `class-diagram.png` | Figure 5 | Class diagram, the dataclasses | `make_diagrams.py` |
| `use-case-diagram.png` | Figure 6 | Use cases, actors and the system boundary | `make_behavioural.py` |
| `activity-diagram.png` | Figure 7 | One review, from request to stored history and posted comment | `make_behavioural.py` |
| `sequence-diagram.png` | Figure 8 | CLI/HTTP → FastAPI → engine → adapter → GitHub | `make_behavioural.py` |
| `state-diagram.png` | Figure 9 | The pull-request posting state machine | `make_behavioural.py` |
| `pert-chart.png` | Figure 10 | PERT network and the critical path | `make_behavioural.py` |
| `gantt-chart.png` | Figure 11 | The 16-week schedule and its milestones | `make_behavioural.py` |
| `planning.md` | — | The PERT table, the arithmetic and the Gantt assumptions | `make_behavioural.py` |

## Regenerating

From the repository root:

```bash
python docs/diagrams/make_diagrams.py     # Figures 1-5
python docs/diagrams/make_behavioural.py  # Figures 6-11 and planning.md
```

Each script writes its PNGs next to itself, at 150 dpi. `make_diagrams.py` uses
one 13.0 × 7.35 in canvas (about 16:9) for all five figures. `make_behavioural.py`
sizes each figure to its own content — from 15 × 9.6 in for the Gantt chart to
16 × 24 in for the activity diagram, which carries the most nodes. Both scripts
are deterministic: the layout is fixed in the source, there is no randomness and
no timestamp is written into the PNG metadata, so two runs produce byte-identical
files.

Both scripts check their own output. `make_diagrams.py` measures every string
before drawing it and asserts that no string overflows its box, that no two boxes
overlap, that no label sits on top of a box, and that each saved PNG is larger
than 20 KB. `make_behavioural.py` re-measures every label after the figure is
drawn and shrinks any that spills, printing `0 overflowing` per figure. A broken
figure fails the run instead of shipping silently.

`make_diagrams.py` also crops the title strip it bakes into the top of each of
its five images (`Canvas._crop_title_band`, 8.5 % of the height): the report
supplies its own numbered caption, so an internal title would print a second,
unnumbered heading directly above it. `make_behavioural.py` does not crop — its
figures carry the title and a one-line subtitle inside the drawing area, as part
of the figure rather than as a caption.

## Drift warning

**These diagrams are drawn from the code, and they will drift if the code
changes.** The process decomposition in Figures 1-3 and the class list in
Figure 5 were transcribed by hand from `app/engine.py`, `app/parser.py`,
`app/rules.py`, `app/openai_compat_provider.py` and `app/github_client.py`; the
script does not introspect those modules. A renamed process, a new provider or a
new field on a dataclass will not update the drawing. Re-read the module named in
each caption before quoting a figure in a later chapter, and edit the generator
rather than the PNG.

The one exception is Figure 4, which is **not** transcribed: it is generated from
`app/db.py`'s `SCHEMA_SQL` at run time, and `tests/test_diagram_generator.py`
fails the build if the two ever disagree (see "Figure 4" below).

---

## Figure 1 — DFD level 0 (`dfd-level-0.png`)

**Figure 1: DFD level 0 (context diagram) of the Autonomous AI Code Reviewer &
PR Assistant.**

The system is shown as a single process, process 0, with the three external
entities it exchanges data with — the developer, GitHub, and the
OpenAI-compatible model endpoint (LM Studio locally, Sarvam hosted) — and the two
data stores it owns, D1 Review Store and D2 Users & Roles. Every flow carries the
name of the data that crosses it, in the direction it travels, so the diagram
fixes both the system boundary and the vocabulary used in the level-1
decomposition. Nothing inside the boundary is drawn here, and nothing outside it
is allowed to hold review logic.

## Figure 2 — DFD level 1 (`dfd-level-1.png`)

**Figure 2: DFD level 1, the seven processes of a single review.**

Process 0 is decomposed into 7.0 Authenticate & Authorise, 1.0 Parse Diff,
2.0 Apply Rule Engine, 3.0 Review with Provider, 4.0 Anchor Findings,
5.0 Publish to Pull Request and 6.0 Persist Review, with the data stores D1 and
D2 and the flows between them. The two review paths are visible as parallel
flows: 1.0 feeds both 2.0, which runs the deterministic rule engine, and 3.0,
which calls the model endpoint, and both feed 4.0, which decides whether each
finding can be attached to a changed line. GitHub is drawn twice — top right for
the incoming pull-request diff, bottom right for the outgoing comments — so that
the two flows do not cross the diagram; it is one external entity.

## Figure 3 — DFD level 2 (`dfd-level-2.png`)

**Figure 3: DFD level 2, process 2.0 and process 3.0 decomposed.**

The left panel decomposes 2.0 Apply Rule Engine into 2.1 Scan Added Lines,
2.2 Match Rule Patterns, 2.3 Apply Suppressions, 2.4 Assign Severity and
2.5 Emit Findings, a straight pipeline over the added lines of the diff. The
right panel decomposes 3.0 Review with Provider into 3.1 Build Prompt,
3.2 Call Endpoint, 3.3 Parse and Validate, 3.4 Repair Retry and 3.5 Fall Back to
Rules, showing the single repair retry as a return path from 3.3 to 3.4 and the
degradation path to 3.5 as a dashed flow. The dashed flow leaves 3.2, not 3.4:
a second parse failure does not fall back, it returns an empty live review.

## Figure 4 — ER diagram (`er-diagram.png`)

**Figure 4: ER diagram of the six-table schema, generated from `SCHEMA_SQL`.**

The figure is **read out of the code, not reconstructed from it**:
`make_diagrams.py::_er_columns()` parses `app/db.py`'s `SCHEMA_SQL` — the single
DDL string `Database.init_schema()` executes — and every box, column, type and
tag in the image comes from that parse. There is no second list to keep in step.

The schema has six tables — `roles`, `users`, `reviews`, `findings`, `pr_posts`
and `benchmark_runs` — with the primary key of each marked `PK`, the foreign keys
marked `FK`, and every relationship labelled with the foreign key that carries
it. Three relationships exist in the DDL, and the figure draws exactly those:
`users.role_id` → `roles.id`, `findings.review_id` → `reviews.id`, and
`pr_posts.review_id` → `reviews.id`. `pr_posts.review_id` is nullable and
`ON DELETE SET NULL`, so a posting attempt survives the deletion of the review it
refers to; `findings.review_id` is `ON DELETE CASCADE`. `reviews` carries no
`user_id` and no `benchmark_run_id`, so the figure draws no relationship to
`users` or `benchmark_runs` — the reviewer who triggered a review is not
recorded, which is a deliberate limit of the schema rather than a drawing
omission.

The column lists cannot show a constraint, so the figure marks the ones that
matter with a tag: `UNIQUE` on `roles.name`, `users.username`, `users.email` and
`users.api_key_hash`, and `CHECK` on `roles.name`, `reviews.mode`,
`reviews.verdict` and `findings.severity`.

### What keeps Figure 4 honest

`tests/test_diagram_generator.py` fails the build in three ways:

1. the column list `_er_columns()` returns must equal `PRAGMA table_info` on a
   database created by the real `Database.init_schema()` — this catches a parser
   that has stopped understanding the DDL (a wrapped definition, a lower-case
   type, a comma inside a `CHECK (... IN (...))`);
2. the exact text the figure will carry is pinned as a sha256 digest, so a schema
   edit that changes the drawing fails even if nobody regenerated the PNG;
3. the committed PNG must be at least as new as `app/db.py`, or must regenerate
   byte-for-byte identically.

So the ER figure cannot drift from `SCHEMA_SQL` without a red test.

## Figure 5 — Class diagram (`class-diagram.png`)

**Figure 5: class diagram of the reviewer's dataclasses.**

The seventeen classes the report prescribes are grouped by the module that owns
them: `Finding`, `AnchoredFinding`, `ReviewResult` and `ProviderOutcome` in
`app/models.py` and `app/sarvam_provider.py`; `DiffReviewResult`, `FileDiff`,
`Hunk` and `DiffLine` in `app/parser.py`; `Rule` and `LineContext` in
`app/rules.py`; `ProviderSelection` and `OpenAICompatConfig` in `app/engine.py`
and `app/openai_compat_provider.py`; and `InlineComment`, `ReviewPayload` and
`PostResult` in `app/github_client.py`. A filled diamond marks composition — the
whole holds the part, as `AnchoredFinding` holds a `Finding` and `FileDiff` holds
its `Hunk`s — and a dashed arrow marks a dependency, as `Rule.check` takes a
`LineContext`. `UserContext` and `Database` are drawn with a dashed outline
because they live outside those five modules (`app/auth.py` and `app/db.py`) and
the figure groups by module; both are implemented. There is no inheritance among
the seventeen classes.

## Figure 6 — Use case (`use-case-diagram.png`)

**Figure 6: use cases, actors and the system boundary.**

The nine named use cases of the report — Review Diff, Review Source File, Choose
Provider, View Review History, Run Benchmark, Post Review to PR, Receive Webhook,
Manage Users and Roles, and the three `<<include>>`/`<<extend>>` cases — with the
four actors: the developer (CLI or browser), the CI system, the administrator and
GitHub. `Review Diff` `<<include>>`s `Review with Provider` and
`Anchor Findings`; `Fall Back to Rules` `<<extend>>`s `Review with Provider`,
because the degradation only happens when the live call fails.

## Figure 7 — Activity (`activity-diagram.png`)

**Figure 7: one review, from request to stored history and posted comment.**

Two panels, because the flow has two halves that meet once. **Panel A** is the
review path: the body is validated by pydantic (422 on a bad `provider` literal or
a NUL byte in `code`), `X-Hub-Signature-256` is checked when
`GITHUB_WEBHOOK_SECRET` is set (401 on a mismatch), a non-`pull_request` event or
an action outside `opened`/`reopened`/`synchronize`/`ready_for_review`/`edited`
is acknowledged with `200 {"status": "ignored"}`, the diff source is chosen
(inline payload → GitHub API → bundled fixture), a body with neither `diff` nor
`code` is a 422, and an unparseable diff is a 422. `engine.review()` then selects
one provider (`sarvam` > `local` > `mock`) and the panel follows the live branch:
one attempt with `response_format = json_object`, a non-repairable failure
(auth, permission, connection, timeout, 429, 5xx) degrades to the rule engine,
an unparseable answer gets exactly one repair retry with the error appended and
`response_format` dropped, and a second failure ends the run as a **live review
with zero findings** — not as a fallback.

**Panel B** is where the review becomes a record: the response is built
(`anchor_findings`, `render_comment`, the stats and verdict), then **persisted**
(`Database.store_review()`), then — only for a publishable webhook — posted:
`build_payload()` caps the inline comments at 30 and overflows the rest into the
summary, an existing summary marker skips the whole post as a duplicate, a 422 on
a single inline comment demotes that comment into the summary, and the outcome is
stored by `Database.store_pr_post()`. Every failure in panel B is logged once at
WARNING and the status stays 200.

The repair retry appears in panel A, on the provider path, where the code puts it.
There is no "re-read the body as source code" step: the HTTP layer has exactly one
recovery from a parse failure, and it is the 422.

## Figure 8 — Sequence (`sequence-diagram.png`)

**Figure 8: the call sequence of one review.**

Nine lifelines: the CLI/HTTP client, FastAPI (`app/main.py`), the engine, the
OpenAI-compatible adapter, the provider endpoint (Sarvam or LM Studio), the rule
engine, the parser/anchorer, the review store (`app/db.py`, SQLite) and the
GitHub API. The `alt` block is the one real fork: the live path
(`review_with_fallback` → `POST /chat/completions` → a completion → findings) and
the degraded path (`offline_diff_findings` over the 63 deterministic rules). Both
rejoin at `anchor_findings`, whose three anchor statuses come back up the same
arrow, and the review is then persisted before the 200 is returned. The last two
arrows are the webhook's post and its per-comment retry followed by the summary
comment.

## Figure 9 — State (`state-diagram.png`)

**Figure 9: the posting state machine of `app/github_client.post_review`.**

`Idle` → `Checking Marker` → `Posting Inline` → `Posting Summary` → `Done`, with
`Skipped Duplicate` and `Failed` as the other terminals. The entry transition is
guarded by "token present, payload non-empty", which is why a demo with no
`GITHUB_TOKEN` never enters the machine at all. A summary marker already on the
pull request goes straight to `Skipped Duplicate` — the idempotency decision, not
an error. A 422 on the bulk inline review moves to `Demoting`: each comment is
retried on its own and a repeat 422 demotes that one comment into the summary. A
429 is retried exactly once after `Retry-After`; a second 429 demotes every
inline comment and posts the summary only, because a webhook delivery has a
deadline. 401/403, 404, 5xx and transport errors are terminal `Failed`, which
`app/main.py` reports in `posting` while still answering GitHub with 200.

## Figures 10 and 11 — PERT and Gantt (`pert-chart.png`, `gantt-chart.png`)

**Figure 10** is the PERT network over the ten activities of `planning.md`, with
the expected time on each node and the critical path `A - B - C - E - G - I - J`
in red. **Figure 11** is the 16-week Gantt of the same activities, with the six
milestones, the critical-path bars outlined in red, and the plan buffer shaded
from the critical-path finish to week 16. Every number in both comes from
`planning.md` §2, which `make_behavioural.py` computes from the three-point
estimates.

---

## Where the code and the diagrams disagree

Two of the three disagreements this section used to record have been closed by the
code, and the figures now describe the implementation rather than the
prescription:

* **Persistence is implemented.** `app/db.py` holds the DDL (`SCHEMA_SQL`), the
  `Database` class (`store_review`, `store_pr_post`, `store_benchmark_run`,
  `list_reviews`, `stats`) and `get_database()`. Process 6.0 Persist Review and
  data store D1 Review Store in Figure 2 are therefore real, and Figure 7 draws
  the two persist steps. A review is stored on the way out of `_build_response`
  and again — as a posting outcome — after a publish attempt. Storage is
  best-effort by design: `_persist_review` and `_persist_pr_post` swallow every
  failure, log once at WARNING on `reviewer.db`, and leave the response exactly as
  it would have been. A blank `DATABASE_PATH` switches history off entirely.
* **Users and roles are implemented.** `app/db.py` creates `roles` and `users`
  and stores only the SHA-256 of an API key; `app/auth.py` exposes
  `UserContext`, `require(level)` and `auth_enabled()`, which resolve to 401 for a
  missing or unknown key, 403 for a role that is too weak, and 503 when the user
  store is unreachable. Data store D2 Users & Roles and process 7.0 Authenticate &
  Authorise in Figure 2 are real. The guard is opt-in (`API_AUTH_ENABLED`, default
  false), and it is attached only to the history and user routes — the review
  surfaces stay open, because turning the flag on must not break the demo. The
  webhook's own authentication is the separate HMAC check on
  `X-Hub-Signature-256` that Figure 7 draws.

One disagreement remains, and it is deliberate:

**The rule engine checks suppressions before it matches patterns, and severity is
a property of the rule rather than a decision.** In `review_lines` (`app/rules.py`)
the `# noqa` / `# nosec` marker is parsed once per line and an all-suppressing
marker `continue`s before any rule runs; per-rule suppression is tested inside the
rule loop; and `severity` comes from the `Rule` row, with `min_severity` acting as
a floor rather than an assignment. Figure 3 keeps the textbook order 2.2 → 2.3 →
2.4 because the outcome is the same set of findings, but the executable order is
2.1 → 2.3 → 2.2 → 2.4.
