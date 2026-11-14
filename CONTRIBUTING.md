# Contributing

This is a coursework repository, but it is maintained like a normal project.

## Before you change anything

```bash
pip install -r requirements.lock
make verify                     # must be green before and after your change
```

## Ground rules

- **The suite must stay green and offline.** No test may reach the network, require a
  credential, or depend on execution order. `python scripts/verify_offline.py` is the gate.
- **Do not widen the finding contract.** `Finding` has exactly five fields; anchoring lives
  in `AnchoredFinding` because it is review metadata, not a claim about the code.
- **One mock implementation.** The degraded path calls `offline_diff_findings` directly.
  This is deliberate — see `docs/decisions/0004` — and must not be "fixed" back.
- **One warning per degraded run.** If you add a fallback, log once.
- **Never claim a result you have not measured.** Placeholders are `[FILL AFTER BENCHMARK: …]`.
- **Regenerate, do not hand-edit, the derived artefacts:** the report (`python docs/report/assemble.py`),
  the diagrams (`python docs/diagrams/make_diagrams.py`, `make_behavioural.py`).

## Commit messages

`type(scope): summary` — for example `fix(parser): stop a truncated hunk swallowing the next file`.
Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.
