#!/usr/bin/env bash
#
# One-command verifier: create a venv, install the pinned lock, run the
# test suite, then prove the suite needs no network.
#
#   bash scripts/verify.sh            # or: make verify
#
# Requires no environment variables. Optional: VERIFY_VENV=<path> to
# choose where the virtualenv lives (default: <repo>/.venv-verify).
set -euo pipefail

# ---------------------------------------------------------------------------
# Locate the repo root from this script's own path.
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

VENV_PATH="${VERIFY_VENV:-${REPO_ROOT}/.venv-verify}"
LOCK_FILE="${REPO_ROOT}/requirements.lock"

banner() {
  echo
  echo "============================================================"
  echo "$1"
  echo "============================================================"
}

fail() {
  banner "FAIL: $1"
  exit 1
}

trap 'banner "FAIL: verify.sh aborted (see the error above)"' ERR

banner "verify: ${REPO_ROOT}"

# ---------------------------------------------------------------------------
# Pick an interpreter. Prefer python3.10 to match .python-version.
# ---------------------------------------------------------------------------
WANTED_PY=""
if [[ -f "${REPO_ROOT}/.python-version" ]]; then
  WANTED_PY="$(tr -d '[:space:]' < "${REPO_ROOT}/.python-version")"
fi

PYTHON_BIN=""
if command -v python3.10 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.10)"
else
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    fail "no python3.10 and no python3 on PATH"
  fi
  HAVE_PY="$("${PYTHON_BIN}" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  echo "WARNING: python3.10 not found on PATH; falling back to python3 (${HAVE_PY})."
  echo "WARNING: this differs from .python-version (${WANTED_PY:-unknown})."
  echo "WARNING: CI installs the exact pinned interpreter; a local pass here is"
  echo "WARNING: strong evidence but not a byte-for-byte match with CI."
fi
echo "Using interpreter: ${PYTHON_BIN} ($("${PYTHON_BIN}" -c 'import sys; print(sys.version.split()[0])'))"

[[ -f "${LOCK_FILE}" ]] || fail "missing ${LOCK_FILE}"

# ---------------------------------------------------------------------------
# Create or reuse the virtualenv.
# ---------------------------------------------------------------------------
if [[ -x "${VENV_PATH}/bin/python" ]]; then
  echo "Reusing virtualenv: ${VENV_PATH}"
else
  echo "Creating virtualenv: ${VENV_PATH}"
  "${PYTHON_BIN}" -m venv "${VENV_PATH}" || fail "could not create virtualenv at ${VENV_PATH}"
fi

VENV_PY="${VENV_PATH}/bin/python"

# ---------------------------------------------------------------------------
# Install the pinned dependency set.
# ---------------------------------------------------------------------------
echo "Installing from requirements.lock ..."
PIP_USER=0 "${VENV_PY}" -m pip install --disable-pip-version-check -q -r "${LOCK_FILE}" \
  || fail "dependency install from requirements.lock failed"

# ---------------------------------------------------------------------------
# Tests, then the zero-network proof.
# ---------------------------------------------------------------------------
echo "Running test suite ..."
"${VENV_PY}" -m pytest -q tests || fail "test suite failed"

# The learning site has its own gate; CI runs it too, so `make verify` must not
# go green while CI would fail on it.
echo "Validating the learning site ..."
"${VENV_PY}" site/tools/validate_lessons.py || fail "learning-site gate failed"

echo "Running zero-network proof ..."
"${VENV_PY}" scripts/verify_offline.py || fail "offline (zero-network) run failed"

banner "PASS: tests and zero-network proof succeeded"
exit 0
