# Docker

The image is a two-stage build: wheels are built from `requirements.lock` in a
throwaway stage, then installed offline into a `python:3.12-slim` runtime that
runs as uid 10001 and serves the FastAPI app on port 8000.

Nothing here needs an API key. With no credentials present the app selects its
local rule engine, `mode` reports `mock`, and `/health` still answers `200`.

---

## 1. Build

From the repository root (the directory holding `Dockerfile`):

```bash
docker build -t ai-code-reviewer:local .
```

With Compose:

```bash
docker compose build
```

The first build downloads every pin in `requirements.lock` and needs network
access to PyPI. Subsequent builds reuse the cached wheel layer until
`requirements.lock` changes.

## 2. Run

```bash
docker run --rm -p 8000:8000 --name ai-code-reviewer ai-code-reviewer:local
```

Or, using the bundled Compose file (which also works with no `.env` present):

```bash
docker compose up --build        # foreground
docker compose up -d --build     # detached
docker compose down              # stop
```

## 3. Check it is healthy

```bash
curl -s http://127.0.0.1:8000/health | python -m json.tool
```

Expected shape on a keyless run:

```json
{
  "status": "ok",
  "mode": "mock",
  "rules": 63,
  "sarvam_key": "missing",
  "github_token": "missing",
  "webhook_secret": "missing",
  "provider": "mock"
}
```

(`rules` and `categories` grow as rules are added; the important part is
`status: ok` and `mode: mock`.)

The image's own health state is visible too:

```bash
docker inspect --format '{{.State.Health.Status}}' ai-code-reviewer   # -> healthy
docker compose ps                                                     # STATUS column
```

## 4. Try a review

`/test-review` reviews the bundled `samples/sample.diff` -- no credentials, no
outbound network, no model download:

```bash
curl -s "http://127.0.0.1:8000/test-review?provider=mock" | python -m json.tool
```

`provider=mock` guarantees the offline path even if a key happens to be set.
Other useful calls:

```bash
curl -s http://127.0.0.1:8000/                              # banner + mode
curl -s http://127.0.0.1:8000/rules | python -m json.tool    # rule catalogue
curl -s "http://127.0.0.1:8000/test-review?path=samples/sample.diff&min_severity=HIGH"
```

Interactive docs: <http://127.0.0.1:8000/docs>

The CLI also ships inside the image:

```bash
docker run --rm ai-code-reviewer:local python reviewer.py samples/sample.diff --offline
```

## 5. Point the container at LM Studio on the host

LM Studio runs on your machine; the container has its own `localhost`. Inside a
container `http://localhost:1234/v1` points at the container itself and will
fail. Use `host.docker.internal` instead.

### macOS / Windows (Docker Desktop)

Works as-is:

```bash
docker run --rm -p 8000:8000 \
  -e LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1 \
  ai-code-reviewer:local
```

### Linux (native Docker Engine)

`host.docker.internal` does not resolve unless you map it:

```bash
docker run --rm -p 8000:8000 \
  --add-host=host.docker.internal:host-gateway \
  -e LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1 \
  ai-code-reviewer:local
```

In `docker-compose.yml` uncomment the `extra_hosts:` block -- it already contains
`"host.docker.internal:host-gateway"` -- and set the same `LMSTUDIO_BASE_URL`.

On engines older than 20.10 the `host-gateway` alias is unavailable; bind LM
Studio to `0.0.0.0` and use the bridge gateway IP instead, typically
`http://172.17.0.1:1234/v1`.

Two host-side settings that bite people:

- In LM Studio, start the local server with **Serve on Local Network** enabled
  (or bind `0.0.0.0`). A server listening only on the host's `127.0.0.1` is
  unreachable from a container no matter which gateway you use.
- Load a model before sending requests; the endpoint returns an error when no
  model is loaded.

Optional companions to `LMSTUDIO_BASE_URL`: `LMSTUDIO_MODEL` (default
`qwen2.5-coder-7b-instruct`) and `LMSTUDIO_TIMEOUT` (default `120`). A local
model on a laptop is slow -- raise the timeout rather than assuming a hang.

## 6. Pass a GitHub token

The token is only needed for PR reads and comments. Pass it at runtime, never at
build time -- it would be baked into an image layer:

```bash
docker run --rm -p 8000:8000 -e GITHUB_TOKEN=ghp_xxx ai-code-reviewer:local
```

With Compose, prefer a `.env` file next to `docker-compose.yml` (it is
git-ignored and excluded from the build context):

```bash
cp .env.example .env
# edit .env -> GITHUB_TOKEN=ghp_xxx
docker compose up -d
```

`docker-compose.yml` marks `env_file: .env` as `required: false`, so `up` still
works when the file is absent. That needs Docker Compose **v2.24 or newer**;
on older versions, delete the `env_file:` block or create an empty `.env`.

Other supported keys: `SARVAM_API_KEY` (+ `SARVAM_MODEL`), `REVIEW_MODE`
(`auto` | `live` | `mock`), `GITHUB_WEBHOOK_SECRET`, `REQUEST_TIMEOUT_S`. See
`.env.example`. None of them is required.

## 7. Why the app runs with no keys

Configuration is read once at start-up and every field has a safe default; a
missing key is data, not an error. `REVIEW_MODE=auto` (the default) resolves to
the local rule engine when no Sarvam key and no local endpoint are configured, so
a fresh `docker run` with zero flags serves `/health` and `/test-review`
immediately. Only `mode=live` paths need credentials.

## 8. Image size

Roughly **200-250 MB** on disk: `python:3.12-slim` (~120 MB) plus about 82 MB of
installed dependencies measured from `requirements.lock` (the largest are
`openai`, `uvloop`, `pygments`, `pydantic_core`, `sarvamai`).

Why it is not smaller:

- `requirements.lock` is a full `pip freeze` of runtime **and** dev pins, so
  `pytest`, `iniconfig` and `pluggy` ride along. Splitting a runtime lock out of
  it would save a few MB -- a `requirements.lock` change, out of scope here.
- `uvicorn[standard]`'s extras (`uvloop`, `httptools`, `watchfiles`, `websockets`)
  are pinned, and `uvloop` alone is ~16 MB. They are used by the production
  server, so they stay.
- The wheelhouse (`/wheels`, ~16 MB) is deleted in the same `RUN` that installs
  from it, so it never reaches the final layer.

The builder stage does not affect the published image size at all.

## 9. If the build fails

**`pip wheel` cannot reach PyPI** -- the most common failure. Stage 1 downloads
every pin, so it needs working network egress to `pypi.org` /
`files.pythonhosted.org`. Behind a corporate proxy or an air-gapped CI runner you
will see `Could not find a version that satisfies the requirement ...` or
repeated `Retrying (Retry(total=..., connect=None))`. Fixes, in order of
preference:

1. Give the builder proxy settings at build time -- they are not inherited from
   the host shell automatically:
   `docker build --build-arg HTTPS_PROXY=$HTTPS_PROXY --build-arg HTTP_PROXY=$HTTP_PROXY .`
   (requires the corresponding `ARG` lines in the builder stage).
2. Pre-populate the wheelhouse on a networked machine
   (`pip wheel -r requirements.lock -w wheels`) and point the build at it with a
   `COPY wheels/ /wheels` in place of the `pip wheel` step.
3. Use a mirror: `pip wheel -i https://your.mirror/simple -r requirements.lock`.

**`No matching distribution found` for a single pin** -- the lock names a version
that does not exist on the index you can reach, or has no cp310 wheel and no
source distribution. Check the version on PyPI; the lock is generated by
`pip freeze` and must be regenerated, not hand-edited.

**`pip install --no-index` fails in stage 2 with "no matching distribution"** --
the two stages drifted apart. Both must be `python:3.12-slim`: wheels built on
one Python minor (cp310) cannot install on another. Also confirm the failing
package is in `requirements.lock`, since `--no-index` makes any unpinned import
an error rather than a download.

**`gcc: not found` / a compilation error in stage 1** -- a pin has no prebuilt
cp310 wheel, so it is compiling from source. `build-essential` is already
installed in the builder; a missing `-dev` system library (e.g. `libyaml-dev`,
`libffi-dev`) needs adding to that `apt-get install` line.

**Container exits immediately, logs show `ModuleNotFoundError: No module named
'app'`** -- the working directory or copied tree is wrong. `WORKDIR` is `/app`,
`PYTHONPATH=/app`, and `app/` is copied to `/app/app/`, so `app.main:app` must
resolve. Confirm with
`docker run --rm ai-code-reviewer:local python -c "import app.main; print('ok')"`.

**Health status `unhealthy` while the app works** -- the probe runs inside the
container against `127.0.0.1:8000`. If you changed the port in `CMD` or
`docker-compose.yml`, update the `HEALTHCHECK` line too. `start-period=10s`
gives a cold start room; a very slow host may need more.

**`permission denied` writing files** -- the process is uid 10001 and owns
`/app`. Anything the app must write needs a volume owned by `10001:10001` or a
world-writable path; the app is designed not to need one.

**`docker: command not found`** -- that is the host, not the image. Install
Docker Engine or Docker Desktop first.
