# Reproducibility

How the dependency set is pinned, how to rebuild it from nothing, how to verify a
fresh machine in one command, and what to do when something drifts.

Nothing here requires credentials or network access to a model endpoint. The
test suite is offline by construction, and `make verify` proves that.

---

## 1. Pinned direct dependencies

Two files declare what the project asks for. Neither is installed directly by
Docker or CI — both install `requirements.lock` (§2).

`requirements.txt` — runtime:

| Package | Pin |
| --- | --- |
| `pydantic` | `2.14.3` |
| `pydantic-settings` | `2.15.0` |
| `fastapi` | `0.162.5` |
| `uvicorn[standard]` | `0.54.0` |
| `httpx` | `0.28.1` |
| `sarvamai` | `0.1.46` |
| `openai` | `3.51.0` |
| `sqlalchemy` | `2.1.8` |

`requirements-dev.txt` — development:

| Package | Pin |
| --- | --- |
| `-r requirements.txt` | includes all of the above |
| `pytest` | `8.4.2` |

Every pin is exact (`==`), including the three that would otherwise float into
incompatible majors: `pydantic` 2.x, `openai` 3.x and `sqlalchemy` 2.x. There are no ranges, no
extras beyond `uvicorn[standard]`, and no VCS or local-path requirements.

There is no `pyproject.toml`, `setup.py` or `setup.cfg` in this repository: the
project is an application, not an installable distribution, and it is run from
the repository root (`python reviewer.py ...`, `uvicorn app.main:app`). That is
also why no `requires-python` metadata exists — the interpreter is pinned in
`.python-version` and in the Dockerfile, nowhere else.

---

## 2. The lock file

`requirements.lock` is the full resolved closure of runtime **and** dev pins: 37
distributions, one exact version each, alphabetical. It is what Docker and CI
install. Its first three lines state how it was produced and that it must not be
hand-edited.

Because it is a complete closure, `pytest`, `iniconfig`, `pluggy` and the
`uvicorn[standard]` extras (`uvloop`, `httptools`, `watchfiles`, `websockets`)
are in it too. `docs/DOCKER.md` §8 accounts for that weight in the image.

### Why Docker and CI install from the lock

- `requirements.txt` names eight packages; pip resolves their transitive
  dependencies at install time. Two installs a week apart can produce different
  trees from identical input files.
- The lock fixes the transitive closure, so a CI run and a Docker image built
  from the same commit install byte-identical version numbers.
- The Docker runtime stage installs with `--no-index --find-links=/wheels`, so an
  unpinned import is a build error rather than a silent download. That only
  works if the lock is complete.
- `.github/workflows/ci.yml` installs `-r requirements.lock` and caches on
  `requirements.lock`, so a lock change — and only a lock change — invalidates
  the dependency cache.

### How it was generated

```bash
python -m venv .venv-lock
PIP_USER=0 .venv-lock/bin/python -m pip install -r requirements-dev.txt
PIP_USER=0 .venv-lock/bin/python -m pip freeze --exclude-editable | sort -f > requirements.lock.tmp
```

Then prepend the three comment lines to `requirements.lock.tmp` by hand (a bare
`sort -f` would reorder them among themselves), and replace the file:

```bash
mv requirements.lock.tmp requirements.lock
```

Notes on the recipe:

- **A clean venv, not the developer's environment.** Anything already installed
  system-wide leaks into `pip freeze` and inflates the lock.
- **`--exclude-editable`** keeps a local `pip install -e .` path out of the lock;
  a lock line pointing at `./something` cannot install anywhere else.
- **`sort -f`** makes the file diffable: a re-lock that changes one version
  shows one changed line, not a reshuffled file.

### Regenerating it, exactly

Run this from the repository root when a pin in `requirements.txt` /
`requirements-dev.txt` changes, or when a transitive version must move:

```bash
rm -rf .venv-lock
python -m venv .venv-lock
PIP_USER=0 .venv-lock/bin/python -m pip install --upgrade pip
PIP_USER=0 .venv-lock/bin/python -m pip install -r requirements-dev.txt
PIP_USER=0 .venv-lock/bin/python -m pip freeze --exclude-editable | sort -f > requirements.lock.tmp
mv requirements.lock.tmp requirements.lock
git diff --stat requirements.lock
```

Review the diff before committing it. A re-lock that moves twenty lines because
of an unrelated pin change is a signal that a transitive dependency was pulled
forward — accept that deliberately or not at all. Then re-run `make verify` (§4)
and, if the image matters for this change, rebuild it.

Do not edit versions inside `requirements.lock` by hand. A hand-edited lock is a
version set nobody resolved, and `--no-index` will fail on a version that has no
wheel in the builder's wheelhouse.

---

## 3. The Python pin: 3.12.13

`.python-version` contains one line, `3.12.13`, and that line is the pin. It is
consumed by:

- `.github/workflows/ci.yml`, via `actions/setup-python@v5` with
  `python-version-file: .python-version` — so CI runs the pin, not a guess;
- `scripts/verify.sh`, which reads the file and prints the pin it expects,
  warning when the interpreter it found is not that version;
- by hand, when a developer matches the CI interpreter locally.

The `Dockerfile` does **not** read it: both stages are hardcoded
`FROM python:3.12-slim`, which tracks the same minor. The two places must be
changed together (see "Changing the Python version" below).

### Why 3.12

Two constraints decide it, and they agree:

- **The lock needs 3.11 or newer.** Two pins in `requirements.lock` carry that
  floor and drag the whole closure with them: `SQLAlchemy==2.1.8` and
  `starlette==1.10.0` both declare `Requires-Python: >=3.11` (check any of them
  with `python -m pip show <name>`). The rest of the set — `fastapi` 0.162.5,
  `pydantic` 2.14.3, `openai` 3.51.0, `uvicorn` 0.54.0 — still allows 3.10, but
  pip resolves the intersection, so 3.10 cannot install this lock. The floor for
  this project is 3.11, not 3.10.
- **3.12 is a supported, security-fix release until October 2028.** It is not
  end-of-life, and it is not the last of a dead branch: CPython 3.12 receives
  security fixes through **October 2028**, and 3.13 and later are also
  supported. (Python release schedule and PEP 693.)

So the pin is the current minor, chosen because it is the oldest interpreter that
satisfies the dependency floor while remaining in security support for the
foreseeable life of this submission. There is nothing to apologise for and no
urgency to move: a reader in 2027 or 2028 is still inside the 3.12 security
window.

The code itself is written to the 3.11 floor rather than to 3.12 specifically.
Nothing in `app/`, `reviewer.py` or `scripts/` uses syntax newer than 3.11: no
`tomllib`, no exception groups (`except*`), no `typing.Self` or `typing.override`,
no `StrEnum`, no `asyncio.TaskGroup`, no `datetime.UTC`, no `itertools.batched`
and no PEP 695 `type` aliases. Fourteen of the fifteen modules in `app/` open with
`from __future__ import annotations`, so the `X | None` annotations are strings at
runtime rather than objects the interpreter has to evaluate. It should therefore
run unchanged on 3.11, 3.12 and 3.13 — which is what makes the next move cheap.

### Empirical evidence

The full suite was run on CPython **3.12.13** with the pinned dependency versions
and reported `640 passed, 1 skipped` (§4). That is a data point from the machine
that prepared this document, not a CI guarantee — see the caveat in §4.

### Changing the Python version

When you do move (3.13 or later), in this order:

1. `.python-version` → the new version. CI follows automatically, because it
   reads this file.
2. `Dockerfile` → **both** stages. They must stay on the same minor: the runtime
   stage installs the builder's wheels with `--no-index`, so a wheel built for one
   interpreter ABI will not install under another. Change `builder` and `runtime`
   together.
3. Regenerate `requirements.lock` **on the new interpreter** (§2). Several pins
   ship per-minor wheels (`pydantic_core`, `uvloop`, `httptools`, `watchfiles`,
   `PyYAML`); the resolved versions may legitimately differ, and a lock resolved
   on 3.12 may name a version with no wheel for the new ABI.
4. Re-run `make verify` and confirm the pass and skip counts are unchanged. If a
   test that asserted a version-specific message or ordering now fails, that is a
   real finding, not a version nuisance.
5. Update this document and the `.python-version` mentions in `docs/DOCKER.md`.

---

## 4. Verifying a fresh machine in one command

```bash
make verify
```

`make verify` runs `bash scripts/verify.sh`. It needs no environment variables
and no credentials. In order, it:

1. **Locates the repository root** from the script's own path and `cd`s there, so
   it works from any directory.
2. **Picks an interpreter and reports it.** It reads `.python-version` and
   prints the pin it expects. If the interpreter it can find is not that version
   it prints a WARNING block saying so, and that a local pass is strong evidence
   but not a byte-for-byte match with CI. Install the pinned 3.12.13 (or point
   `VERIFY_VENV` at a venv built from it) when you want the local run to match CI
   exactly; the suite must pass on 3.12.13, because that is what CI runs.
3. **Requires `requirements.lock`** to exist, and fails if it does not.
4. **Creates or reuses a virtualenv** at `.venv-verify` (override with
   `VERIFY_VENV=<path>`). It is reused on later runs, so a second `make verify`
   is fast.
5. **Installs the pinned set** with
   `PIP_USER=0 <venv>/bin/python -m pip install -q -r requirements.lock`. This is
   the only step that needs the network — PyPI, once.
6. **Runs the suite**: `<venv>/bin/python -m pytest -q tests`.
7. **Proves the suite needs no network**:
   `<venv>/bin/python scripts/verify_offline.py`. That script blocks
   `socket.create_connection`, blocks `getaddrinfo` for every non-loopback
   hostname, and refuses to construct new `AF_INET`/`AF_INET6` sockets — then
   runs the whole suite in-process with `pytest.main`. `AF_UNIX` and loopback
   stay available because asyncio's event loop builds its self-pipe from a
   socketpair; blocking that breaks the loop rather than testing anything.
8. **Prints a PASS banner**, or FAIL plus the failing step, and exits non-zero.
   `set -euo pipefail` and an `ERR` trap mean a failure anywhere aborts the run.

`make clean` removes `.venv-verify`, `__pycache__` and `.pytest_cache`.

### What "640 passed, 1 skipped" means

`pytest -q tests` collects **641** cases. The result line is:

```
640 passed, 1 skipped in <n> s
```

- **640 passed** — every unit, integration and CLI test. No network, no API key,
  no model server. The live providers are exercised with test doubles shaped
  like the real SDK exceptions, so the adapter's error handling is real code
  under test rather than a mock of itself.
- **1 skipped** — exactly one test, and it is skipped by design:
  `tests/test_openai_compat_provider.py::test_live_smoke_review_against_a_real_endpoint`.
  Its module-level `@pytest.mark.skipif` fires when `LMSTUDIO_BASE_URL` is unset,
  which is the case in CI and on any machine without a local server. It is the
  only test that would construct a real client. Set `LMSTUDIO_BASE_URL` and it
  runs; it asserts only that the run completes and returns a `ProviderOutcome`,
  and accepts a `live` or `mock` outcome, because a configured-but-silent server
  is a legitimate degradation.

So "1 skipped" is not a gap in coverage of this code — it is the absence of a
local model server. **No live model run is recorded in this repository.**

The same numbers appear twice per `make verify`: once for step 6, once inside
step 7's network-blocked re-run. Both must pass.

Observed while preparing this document (2026-11-14, Linux x86_64): the suite was
run as `python -m pytest -q tests` on CPython **3.12.13** — the version
`.python-version` pins — with dependencies installed from `requirements.lock`,
and reported `640 passed, 1 skipped` in 22 s. That is the same interpreter CI
selects from the same file, so the numbers are directly comparable with a CI run.

### The individual pieces

```bash
make test    # $(PYTHON) -m pytest -q tests
make lint    # bash -n scripts/verify.sh + compileall on app/, reviewer.py, scripts/verify_offline.py
make run     # uvicorn app.main:app --reload --port 8000
```

`make test` uses `.venv-verify/bin/python` when it exists, else `python3`.
Override with `make test PYTHON=python3.12` — but note that 3.10 is below the
lock's floor (see §3), so a 3.10 interpreter will fail at the install step, not at
the tests.

---

## 5. If something drifts

### A version conflict, or "no matching distribution"

Symptom: `pip install` reports an unsatisfiable requirement, or a pin has no
wheel for the interpreter you are on.

Do: regenerate the lock (§2) — on the interpreter you intend to use. Never
hand-edit a version into `requirements.lock`. If the conflict is between two
*direct* pins (`requirements.txt` / `requirements-dev.txt`), fix the constraint
there first, then re-lock; the lock only records what pip resolved.

### Tests fail on a newer Python

Do: **check the pin first.** Confirm what you are actually running:

```bash
.venv-verify/bin/python -c 'import sys; print(sys.version)'
```

and compare it with `.python-version`. If they differ, you are testing a state
that was never pinned; re-run under the pinned interpreter before debugging
anything. If the pin matches and a test still fails, it is a real defect.

If you are deliberately moving to a newer interpreter, follow §3's five steps
and treat any failure as a genuine porting finding.

### PyPI is unavailable

The two Docker stages differ, and this matters:

- The **builder** stage runs `pip wheel -r requirements.lock`. It needs network
  access to `pypi.org` / `files.pythonhosted.org`. Behind a proxy or on an
  air-gapped runner this is where the build dies — with `Could not find a version
  that satisfies the requirement ...` or repeated `Retrying (...)`.
- The **runtime** stage runs `pip install --no-index --find-links=/wheels`, and
  needs no network at all. If stage 1 succeeded, stage 2 works offline.

Workarounds, in order of preference: pass `--build-arg HTTPS_PROXY=...` to the
build; pre-populate a wheelhouse elsewhere
(`pip wheel -r requirements.lock -w wheels`) and `COPY` it in; or point pip at a
mirror (`-i https://your.mirror/simple`). `docs/DOCKER.md` §9 has the full list.

For `make verify`, only step 5 (the lock install) needs the network. A machine
that already has `.venv-verify` populated can re-run steps 6–7 with no network
at all:

```bash
.venv-verify/bin/python -m pytest -q tests
.venv-verify/bin/python scripts/verify_offline.py
```

### CI passes and the local run does not (or the reverse)

Compare the interpreter first (§3), then the lock:

```bash
git diff requirements.lock
git status --short
```

CI installs `requirements.lock` and reads `.python-version`; it does not read
`requirements.txt`. A local venv installed from `requirements.txt` can therefore
hold different transitive versions from CI while every direct pin matches.

### The lock looks stale

Pins carry dates — `certifi==2026.10.23` is a CA-bundle snapshot. A lock that is
a year old pins a year-old trust store, and TLS failures against a rotated CA
follow. Re-lock periodically rather than only when a pin is bumped, and review
the diff.

### Changing the Python version, summarised

`.python-version` (one line) → `Dockerfile` (**both** stages) →
`requirements.lock` (regenerate on the new interpreter) → `make verify` →
`docs/DOCKER.md` and this document. Skipping the Dockerfile or the re-lock is the
usual way this goes wrong, and the failure shows up as a `--no-index` install
error in the runtime stage, not as a test failure.
