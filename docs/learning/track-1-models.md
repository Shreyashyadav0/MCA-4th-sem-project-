# Track 1 — models

## Prerequisite check

None. This is the first track; it assumes only that Pydantic v2 is installed
(`pydantic==2.14.3`, `requirements.txt`) and that you can run `python` from the repository
root. Every reference below was read from the tree at commit state of this checkout.

## What it does

`app/models.py` defines the only shape a review result may take: `Severity`,
`AnchorStatus`, the five-field `Finding`, `AnchoredFinding`, and `ReviewResult`.
It validates everything that arrives from outside at the boundary (`extra="forbid"`,
a regex-plus-ascending check on `line`, a two-value check on `mode`) and exposes three
module-level helpers - `severity_counts`, `sort_findings`, `verdict_for` - that every
other surface reuses. `ReviewResult.verdict` is a computed field, so serialising a
result emits the gate decision next to the findings that produced it.

## Why it exists

The rejected alternative is recorded in `docs/decisions/0001-strict-pydantic-v2.md`:
plain dictionaries with per-consumer key checks, or Pydantic with `extra="ignore"`.
Both were rejected for the same reason - a key the reviewer never asked for arrives
from an LLM and either crashes a renderer later or is silently dropped. The module
docstring states the intent at `app/models.py:6-7`: a stray key "fails at the boundary
instead of leaking into a PR comment". The second rejected design is one model with an
anchor field on it; the code instead wraps (`app/models.py:106`, `finding: Finding`), so
review metadata can grow without touching the five-field contract that
`app/github_client.py:253`, `app/main.py:360` and `app/cli.py:248` all read.

## Key references

- `app/models.py:36` — `_ORDER: tuple[str, ...] = ("LOW", "MEDIUM", "HIGH", "CRITICAL")`, the single source of severity order.
- `app/models.py:50` — `return _ORDER.index(self.value)`, the `rank` property used by every sort and filter.
- `app/models.py:64` — `model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)` on `Finding`.
- `app/models.py:86` — `if int(end) < int(start):`, the ascending-range half of the `line` validator.
- `app/models.py:106` — `finding: Finding`, the wrap that keeps anchoring out of the contract.
- `app/models.py:130` — `key=lambda f: (-f.severity.rank, int(f.line.split("-")[0]))`, CRITICAL first then by line start.
- `app/models.py:137` — `if tally["CRITICAL"] or tally["HIGH"]:`, the block gate inside `verdict_for`.
- `app/models.py:171` — `@computed_field  # type: ignore[prop-decorator]`, the decorator that puts `verdict` into JSON.

## The three hardest ideas

### 1. `extra="forbid"` plus `frozen=True`: a stray key must fail at the boundary

`Finding` accepts five keys and no others, and the instance cannot be mutated after
construction. The point is not tidiness. An LLM asked for JSON will volunteer keys -
`confidence`, `category`, `rationale` - and a tolerant model turns those into attributes
that nobody reads and nobody validates. Forbidding them makes the disagreement visible
at the moment it arrives, as a `ValidationError` with a location, instead of a `KeyError`
inside comment rendering three layers down. Freezing closes the other half: findings are
passed to matchers, renderers and posters, and none of them may rewrite one in place.

Worked example, run against the real class:

```python
from app.models import Finding
Finding(file="a.py", line="42", severity="HIGH", issue="x",
        suggested_fix="y", confidence=0.8)
# ValidationError: 1 validation error for Finding
# confidence
#   Extra inputs are not permitted [type=extra_forbidden, input_value=0.8]

f = Finding(file="a.py", line="42", severity="HIGH", issue="x", suggested_fix="y")
f.severity = Severity.LOW
# ValidationError: 1 validation error for Finding
# severity
#   Instance is frozen [type=frozen_instance]
```

`str_strip_whitespace=True` is the third setting on that line, and it is doing work
too: `Finding(file="  a.py  ", ...)` stores `'a.py'`. Note what it does *not* do -
coercion of the enum. `severity="low"` is rejected with `type=enum`; the four values
are case-sensitive. The wire layer therefore has its own model, `LLMFinding`
(`app/sarvam_provider.py:72`, `extra="forbid"` at `:79`) which is tolerant about
`line: str | int` and strict about everything else, and converts to `Finding` only
after the line guards pass.

The `line` validator (`app/models.py:78-88`) is the same idea applied to one field. It
matches `^\d+(?:-\d+)?$` (`app/models.py:82`) and then rejects descending ranges
(`app/models.py:86`):

```
'L42'     -> line must look like "42" or "42-45", got 'L42'
'4.2'     -> line must look like "42" or "42-45", got '4.2'
'42 - 45' -> line must look like "42" or "42-45", got '42 - 45'
'42-39'   -> line range must ascend, got '42-39'
'0'       -> accepted
```

That last line is a deliberate non-check: zero is syntactically a line number and the
model does not own the question of whether line 0 exists. `anchor_findings` decides
that, and it will call it `file_only`.

### 2. The five-field contract is a contract, not a schema

Every consumer of a finding reads exactly these five names and no others. Verified
`model_dump()` keys: `['file', 'line', 'severity', 'issue', 'suggested_fix']`;
`as_row()` (`app/models.py:90-98`) renames them for display as
`['File', 'Line', 'Severity', 'Issue', 'Suggested Fix']`. The consumers:

```
app/github_client.py:253   finding.severity.value,      (inline comment body)
app/main.py:360            f"... {finding.file}:{finding.line}"   (markdown summary)
app/cli.py:248             f"   Severity      : {finding.severity.value}"
```

So adding a sixth field is not a model change, it is a change to four renderers, two
providers, the CLI table, the API response model and the golden benchmark files - each
of which would keep working but quietly stop showing the new information. That is the
failure mode the contract forbids by construction: there is nothing to add a field to.
When the system genuinely needed a sixth piece of information (can this comment be
attached to the diff?), it did not add a field. It added `AnchoredFinding`
(`app/models.py:101-115`), whose own dump is
`['finding', 'status', 'hunk_header', 'detail']` and whose `as_row` is the five fields
plus `"Anchor"` (`app/models.py:115`). Anchoring is a property of the review surface,
not of the belief.

The contract is also asserted by test: `tests/test_rules.py:462`
(`test_finding_model_stays_five_fields`) checks `set(finding.model_dump())` against the
five names and checks that a sixth keyword raises. If you change the field list, that
test is the first thing that tells you.

### 3. `verdict` is a `computed_field`, not a method

A gate decision is a function of the findings: any HIGH or CRITICAL blocks, any MEDIUM
or LOW is "approve with comments", nothing is "approve" (`app/models.py:134-141`). The
rejected design is the obvious one - a `def verdict(self)` method, or a `verdict` field
filled in at construction. A stored field can disagree with the findings it came from,
which is exactly the bug a CI gate cannot afford; a method never reaches JSON at all,
because `model_dump_json` only serialises fields and computed fields.

Worked example:

```python
r = ReviewResult(mode="mock", target="a.py", findings=[f])   # f is HIGH
r.model_dump_json()
# {"mode":"mock","target":"a.py","findings":[{"file":"a.py","line":"42",
#  "severity":"HIGH","issue":"x","suggested_fix":"y"}],"notes":[],"verdict":"block"}

"verdict" in ReviewResult.model_fields          # False
sorted(ReviewResult.model_computed_fields)      # ['verdict']
r.verdict = "approve"
# AttributeError: property 'verdict' of 'ReviewResult' object has no setter
```

The consumer is CI: `app/main.py:206` types the response field as
`Literal["block", "approve with comments", "approve"]`, `app/main.py:535` passes
`review.verdict` into it, and `tests/test_api.py:112` asserts
`body["stats"]["verdict"] == "block"`. Because the value is derived on serialisation,
no code path can post a review whose verdict does not match its findings.

Two honest wrinkles. First, `ReviewResult` itself is *not* frozen - only
`extra="forbid"` (`app/models.py:147`); the immutability guarantee stops at `Finding`
and `AnchoredFinding`. Second, `verdict_for` has been reimplemented for the poster as
`_verdict(counts)` at `app/github_client.py:471`, which takes a severity tally rather
than a `ReviewResult`. Two implementations of one rule is a drift risk; the docstring
there says it matches `app.models.verdict_for`, and the only thing keeping them equal
is that claim.

## Rebuild exercise

Time: 1-3 hours. Fresh file: `track1_models.py`, created outside `app/` (for example
`/tmp/track1/track1_models.py`). Do not edit `app/models.py`, and do not copy from it
while writing.

Build, in this order, from the descriptions in this document only:

1. `Severity(str, Enum)` with `LOW/MEDIUM/HIGH/CRITICAL` and a `rank` property
   returning 0-3.
2. `AnchorStatus(str, Enum)` with `anchored`, `file_only`, `unanchored`.
3. `Finding` - Pydantic v2, `extra="forbid"`, `frozen=True`, `str_strip_whitespace=True`,
   five fields, `file`/`issue`/`suggested_fix` with `min_length=1`, a `line` validator
   enforcing `42` or ascending `42-45`, and `as_row()` returning the five display keys
   in contract order.
4. `AnchoredFinding` wrapping a `Finding` plus `status`, `hunk_header: str | None = None`,
   `detail: str = ""`, and `as_row()` returning the five keys plus `Anchor`.
5. `severity_counts`, `sort_findings` (CRITICAL first, then by the integer start of
   `line`), `verdict_for`.
6. `ReviewResult` with `mode` (validated to `live`/`mock`), `target`, `findings`,
   `notes`, `sorted_findings`, `counts()`, a computed `verdict`, and `to_json()`.

Test it against the real module, not against your memory:

- Same inputs, same `model_dump_json()` bytes. Feed both implementations the same three
  findings (one HIGH on line 10, one CRITICAL on `2-5`, one LOW on line 3) and diff the
  JSON.
- `severity="low"` must raise; `line="42-39"` must raise; `line="42 - 45"` must raise;
  an extra keyword `confidence=0.8` must raise with `type=extra_forbidden`.
- `severity_counts([])` must return all four keys at zero, and `verdict_for([])` must
  return `"approve"`.
- `ReviewResult(...).verdict = "approve"` must raise `AttributeError`.
- Run `python -m pytest tests/test_rules.py -k five_fields` against the real tree; it
  must still pass untouched.

## Self-test questions

1. `Finding` forbids extra keys and `LLMFinding` also forbids them, yet the wire model
   still exists. What does the second model buy that a single tolerant model would not?
2. `sort_findings` sorts on `-f.severity.rank` and then `int(f.line.split("-")[0])`.
   What ordering guarantee is missing from that key, and what input exposes it?
3. If `verdict` were a plain field set in `ReviewResult.__init__`, name the concrete
   code path in this repository that could then post a review whose verdict contradicts
   its findings.
4. The `line` validator accepts `"0"` but rejects `"42-39"`. Which of those two is a
   model concern and which belongs to `anchor_findings`, and why?
5. `AnchoredFinding.as_row()` returns six keys while `Finding.as_row()` returns five.
   What would break, concretely, if `status` were instead added as a sixth field on
   `Finding`?
