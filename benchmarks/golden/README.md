# benchmarks/golden — dataset format

**Labels in this directory must be written by a human.** A label produced by the
rule engine, by an LLM, or by copying the tool's own output makes the benchmark
measure nothing: it would score the tool against itself. `benchmarks/golden/`
therefore ships two **format examples only** — they demonstrate the file layout
and are excluded from every reported metric.

## Layout

```
benchmarks/golden/
├── manifest.json
├── README.md
└── <sample-id>/
    ├── change.diff     # a real unified diff (git format), the input
    └── expected.json   # what a human says SHOULD be reported
```

`expected.json`:

```json
{
  "note": "free text, optional",
  "findings": [
    {"file": "app/users.py", "line_start": 4, "line_end": 4,
     "category": "injection", "severity": "CRITICAL"}
  ]
}
```

- `file` — post-change path, exactly as it appears in the diff's `+++` line.
- `line_start` / `line_end` — new-side line numbers, inclusive; equal for one line.
- `category` — one of the rule categories in `app/rules.py`
  (secrets, injection, deserialisation, crypto, auth, config, reliability,
  quality, complexity, style) or `llm` for a finding only a model would catch.
- `severity` — LOW | MEDIUM | HIGH | CRITICAL.

An empty `"findings": []` is a legitimate label: it says "this change is clean",
which is how true negatives get measured.

## Adding a sample

1. `mkdir benchmarks/golden/<short-id>`
2. Save the patch as `change.diff` (one file per sample is simplest; several are allowed).
3. Read the diff yourself and write `expected.json` **by hand**.
4. Add `<short-id>` to `manifest.json` under `evaluation_samples`.
5. Run `python -m benchmarks.eval --modes rules --dataset benchmarks/golden`.

## Why the labels are the hard part

The harness can only measure what the labels assert. A missing label is a false
positive; a label nobody can reproduce from the diff is a false negative. Both
corrupt the numbers, and neither can be detected automatically — which is why
`collect_candidates.py` only ever writes an EMPTY `expected.json` template and
`label_helper.py` prompts a human.
