"""Exhaustive tests for the Phase 3 deterministic rule engine.

Coverage strategy: every registered rule has a sample line in
:data:`RULE_SAMPLES` and a parametrized test asserts it fires — so a rule that
silently stops matching (bad regex edit, renamed id) fails the suite instead of
quietly disappearing from the product. Negative cases pin the false positives
that would make the tool unusable: environment lookups, parameterised SQL,
``safe_load``, timeouts, context managers.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.models import Finding, Severity
from app.parser import anchor_findings, bundle_from_source, parse_diff, parse_diff_file
from app.rules import (
    RULES,
    RULES_BY_ID,
    RULE_COUNT,
    RuleCategory,
    review_diff,
    review_lines,
    rule_by_id,
    rule_ids,
    shannon_entropy,
)

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "sample.diff"

_AWS = "AKIA" + "IOSFODNN7EXAMPLE"
_GOOGLE = "AIza" + "A" * 35
_OPENAI = "sk-" + "a" * 32
_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.c2lnbmF0dXJl"
_ENTROPY = "Zx9Qw3Lp7Rt2Yb5Nc8Vf1Hj4Kd6Mg0Sa"

# rule id -> a single line that must make it fire.
RULE_SAMPLES: dict[str, str] = {
    # secrets
    "secret/hardcoded-credential": 'API_KEY = "abcd1234efgh5678"',
    "secret/aws-access-key": f'AWS_KEY = "{_AWS}"',
    "secret/aws-secret-key": 'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"',
    "secret/github-token": 'TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz1234"',
    "secret/gitlab-token": 'TOKEN = "glpat-abcdefghijklmnopqrst"',
    "secret/slack-token": 'TOKEN = "xoxb-123456789012-abcdefghij"',
    "secret/stripe-key": 'KEY = "sk_live_abcdefghijklmnop1234"',
    "secret/google-api-key": f'KEY = "{_GOOGLE}"',
    "secret/openai-key": f'KEY = "{_OPENAI}"',
    "secret/private-key-block": 'KEY = "-----BEGIN RSA PRIVATE KEY-----"',
    "secret/jwt-literal": f'TOKEN = "{_JWT}"',
    "secret/basic-auth-url": 'URL = "https://admin:hunter2@db.internal:5432/x"',
    "secret/connection-string-password": 'DSN = "host=db password=hunter2 user=app"',
    "secret/bearer-literal": 'headers = {"Authorization": "Bearer abcdefghijklmnopqrstuvwxyz"}',
    "secret/high-entropy-string": f'X = "{_ENTROPY}"',
    # injection
    "unsafe/sql-injection": 'query = f"SELECT * FROM users WHERE id = {uid}"',
    "unsafe/sql-injection-concat": 'query = "SELECT * FROM users WHERE id = " + uid',
    "unsafe/raw-sql": 'rows = User.objects.raw(f"SELECT * FROM t WHERE id = {uid}")',
    "unsafe/eval-exec": "result = eval(user_input)",
    "unsafe/compile-input": 'code = compile(source, "<string>", "exec")',
    "unsafe/command-injection": 'os.system(f"ping {host}")',
    "unsafe/shell-true": "subprocess.run(cmd, shell=True)",
    "unsafe/os-system": 'os.system("ls")',
    "unsafe/path-traversal": 'open(os.path.join(request.args["dir"], name))',
    "unsafe/ssrf": 'requests.get(request.args["url"])',
    "unsafe/open-redirect": 'return redirect(request.args["next"])',
    "unsafe/template-injection": "return render_template_string(user_template, name=name)",
    "unsafe/ldap-injection": 'ldap_conn.search(base, f"(uid={username})")',
    "unsafe/nosql-injection": 'User.find_one({"$where": payload})',
    # deserialisation
    "unsafe/pickle-load": "data = pickle.loads(blob)",
    "unsafe/yaml-load": "data = yaml.load(stream)",
    "unsafe/yaml-unsafe-load": "data = yaml.unsafe_load(stream)",
    "unsafe/xxe": "parser = etree.XMLParser(resolve_entities=True)",
    # crypto
    "crypto/weak-hash": "digest = hashlib.md5(payload).hexdigest()",
    "crypto/ecb-mode": "cipher = Cipher(algorithms.AES(key), modes.ECB())",
    "crypto/static-iv": 'iv = b"0123456789abcdef"',
    "crypto/insecure-random": "token = random.randint(100000, 999999)",
    "security/tls-verify-disabled": "resp = requests.get(url, verify=False)",
    "security/unverified-ssl-context": "ctx = ssl._create_unverified_context()",
    # auth
    "auth/assert-as-check": "assert user.is_admin",
    "auth/timing-unsafe-compare": "if password == provided:",
    "auth/verify-false-jwt": 'payload = jwt.decode(token, key, options={"verify_signature": False})',
    # config
    "config/debug-enabled": "DEBUG = True",
    "config/cors-wildcard": 'app.add_middleware(CORSMiddleware, allow_origins=["*"])',
    "config/cors-credentials-wildcard": "app.add_middleware(CORSMiddleware, allow_credentials=True)",
    "config/bind-all-interfaces": 'uvicorn.run(app, host="0.0.0.0", port=8000)',
    "config/world-writable-permissions": "os.chmod(path, 0o777)",
    "config/csrf-disabled": "@csrf_exempt",
    "config/allowed-hosts-wildcard": 'ALLOWED_HOSTS = ["*"]',
    # reliability
    "reliability/http-no-timeout": "return requests.get(url)",
    "reliability/subprocess-no-check": 'subprocess.run(["ls", "-l"])',
    "quality/open-without-context-manager": "handle = open(path)",
    # quality
    "quality/bare-except": "    except:",
    "quality/except-pass": "    except ValueError: pass",
    "quality/mutable-default-arg": "def add(item, bucket=[]):",
    "quality/missing-type-hints": "def handler(request):",
    # complexity
    "complexity/too-many-params": "def run(a: int, b: int, c: int, d: int, e: int, f: int) -> None:",
    "complexity/deep-nesting": "                    if value:",
    # style
    "style/long-line": 'value = "' + "x" * 130 + '"',
    "style/print-statement": "print(user)",
    "style/todo-comment": "# TODO: fix this later",
    "style/wildcard-import": "from os.path import *",
}

# Rules that need more than one line to be judged, covered by dedicated tests.
MULTI_LINE_RULES = {"complexity/branch-density"}


def _ids(findings: list[Finding]) -> set[str]:
    """Extract the rule id each finding came from."""
    return {
        finding.issue.rsplit("(rule: ", 1)[-1].rstrip(")")
        for finding in findings
        if "(rule: " in finding.issue
    }


# --------------------------------------------------------------------------- #
# Registry integrity
# --------------------------------------------------------------------------- #


def test_registry_shape() -> None:
    ids = rule_ids()
    assert len(ids) == RULE_COUNT == len(RULES) >= 60
    assert len(ids) == len(set(ids)), "rule ids must be unique"
    assert set(RULES_BY_ID) == set(ids)
    assert all(rule.title.strip() for rule in RULES)
    assert all(isinstance(rule.severity, Severity) for rule in RULES)
    assert all(isinstance(rule.category, RuleCategory) for rule in RULES)
    assert all(rule.owasp.startswith("A") for rule in RULES)


def test_registry_covers_every_category() -> None:
    present = {rule.category for rule in RULES}
    assert present == set(RuleCategory)


def test_severity_spread_is_sane() -> None:
    counts = {severity: sum(1 for rule in RULES if rule.severity is severity) for severity in Severity}
    assert counts[Severity.CRITICAL] >= 10
    assert counts[Severity.HIGH] >= 10
    assert counts[Severity.MEDIUM] >= 8
    assert counts[Severity.LOW] >= 5


def test_rule_by_id() -> None:
    rule = rule_by_id("unsafe/sql-injection")
    assert rule is not None
    assert rule.severity is Severity.CRITICAL
    assert rule.category is RuleCategory.INJECTION
    assert rule_by_id("no/such-rule") is None


def test_every_rule_has_a_sample() -> None:
    missing = set(rule_ids()) - set(RULE_SAMPLES) - MULTI_LINE_RULES
    assert not missing, f"rules without a firing sample: {sorted(missing)}"


def test_sample_map_has_no_stale_ids() -> None:
    stale = set(RULE_SAMPLES) - set(rule_ids())
    assert not stale, f"samples for rules that no longer exist: {sorted(stale)}"


# --------------------------------------------------------------------------- #
# Every rule fires on its sample
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("rule_id", "line"), sorted(RULE_SAMPLES.items()))
def test_each_rule_fires(rule_id: str, line: str) -> None:
    fired = _ids(review_lines("sample.py", [(1, line)]))
    assert rule_id in fired, f"{rule_id} did not fire on {line!r}; fired={sorted(fired)}"


@pytest.mark.parametrize(("rule_id", "line"), sorted(RULE_SAMPLES.items()))
def test_each_finding_has_all_five_fields(rule_id: str, line: str) -> None:
    for finding in review_lines("sample.py", [(1, line)]):
        row = finding.as_row()
        assert set(row) == {"File", "Line", "Severity", "Issue", "Suggested Fix"}
        assert all(value.strip() for value in row.values())
        assert finding.suggested_fix.lower() != "consider improving"


# --------------------------------------------------------------------------- #
# Multi-line rules
# --------------------------------------------------------------------------- #


def test_branch_density_rule() -> None:
    body = ["def tangled(value: int) -> str:"] + [
        f"    if value == {n} and value > 0:" for n in range(9)
    ] + ["        return 'x'"]
    findings = review_lines("tangled.py", list(enumerate(body, start=1)))
    assert "complexity/branch-density" in _ids(findings)


def test_branch_density_respects_function_end() -> None:
    body = [
        "def small(value: int) -> int:",
        "    if value:",
        "        return 1",
        "    return 0",
        "def other(value: int) -> int:",
        "    return value",
    ]
    findings = review_lines("small.py", list(enumerate(body, start=1)))
    assert "complexity/branch-density" not in _ids(findings)


def test_branch_density_needs_the_def_line_in_the_diff() -> None:
    body = ["    if a:", "    if b:", "    if c:"]
    findings = review_lines("partial.py", list(enumerate(body, start=1)))
    assert "complexity/branch-density" not in _ids(findings)


# --------------------------------------------------------------------------- #
# False positives that would make the tool unusable
# --------------------------------------------------------------------------- #

BENIGN: list[tuple[str, str]] = [
    ("API_KEY = os.environ[\"API_KEY\"]", "secret/hardcoded-credential"),
    ('password = "changeme"', "secret/hardcoded-credential"),
    ('token = settings.github_token', "secret/hardcoded-credential"),
    ('db.execute("SELECT * FROM users WHERE id = ?", (uid,))', "unsafe/sql-injection"),
    ('db.execute("SELECT * FROM users WHERE id = %s", (uid,))', "unsafe/sql-injection-concat"),
    ("requests.get(url, timeout=5)", "reliability/http-no-timeout"),
    ("data = yaml.safe_load(stream)", "unsafe/yaml-load"),
    ("with open(path) as handle:", "quality/open-without-context-manager"),
    ("digest = hashlib.sha256(payload).hexdigest()", "crypto/weak-hash"),
    ("cipher = AESGCM(key)", "crypto/ecb-mode"),
    ("nonce = os.urandom(12)", "crypto/static-iv"),
    ("if hmac.compare_digest(provided, expected):", "auth/timing-unsafe-compare"),
    ("subprocess.run(cmd, check=True, timeout=5)", "reliability/subprocess-no-check"),
    ("def add(a: int, b: int) -> int:", "quality/missing-type-hints"),
    ('allow_origins=["https://app.example.com"]', "config/cors-wildcard"),
    ("verify=ca_bundle_path", "security/tls-verify-disabled"),
    ("token = secrets.token_urlsafe(32)", "crypto/insecure-random"),
    ("data = json.loads(blob)", "unsafe/pickle-load"),
    ('url = "https://user:${PASSWORD}@db.internal/x"', "secret/basic-auth-url"),
    ("model.eval()", "unsafe/eval-exec"),
    ("await client.get(url, timeout=3.0)", "reliability/http-no-timeout"),
]


@pytest.mark.parametrize(("line", "rule_id"), BENIGN)
def test_benign_lines_do_not_fire(line: str, rule_id: str) -> None:
    assert rule_id not in _ids(review_lines("app/module.py", [(1, line)]))


def test_clean_module_has_no_findings() -> None:
    source = (
        "import logging\n"
        "\n"
        "logger = logging.getLogger(__name__)\n"
        "\n"
        "\n"
        "def add(left: int, right: int) -> int:\n"
        "    return left + right\n"
    )
    assert review_diff(bundle_from_source("clean.py", source)) == []


def test_test_files_are_exempt_from_noise_rules() -> None:
    findings = review_lines("tests/test_thing.py", [(1, "print(secret_value)")])
    assert "style/print-statement" not in _ids(findings)


# --------------------------------------------------------------------------- #
# Malicious inputs
# --------------------------------------------------------------------------- #

MALICIOUS: list[tuple[str, str, str]] = [
    (
        "classic tautology",
        'db.execute("SELECT * FROM users WHERE name = \'" + name + "\'")',
        "unsafe/sql-injection-concat",
    ),
    (
        "f-string union",
        'db.execute(f"SELECT * FROM users WHERE id = {uid} UNION SELECT password FROM users")',
        "unsafe/sql-injection",
    ),
    (
        "percent format",
        'db.execute("SELECT * FROM users WHERE name = \'%s\'" % name)',
        "unsafe/sql-injection",
    ),
    ("command separator", 'os.system(f"ping {host}; rm -rf /")', "unsafe/command-injection"),
    ("subshell", 'subprocess.run(f"ls {path}", shell=True)', "unsafe/command-injection"),
    ("pickle payload", "state = pickle.loads(base64.b64decode(blob))", "unsafe/pickle-load"),
    ("yaml tag bomb", 'yaml.load("!!python/object/apply:os.system [\'id\']")', "unsafe/yaml-load"),
    ("path escape", 'open(f"../../{name}")', "unsafe/path-traversal"),
    ("template ssti", "render_template_string(request.args['t'])", "unsafe/template-injection"),
    ("nosql operator", 'User.find_one({"email": email, "$ne": None})', "unsafe/nosql-injection"),
    ("jwt downgrade", 'jwt.decode(token, key, options={"verify_signature": False})', "auth/verify-false-jwt"),
    ("hardcoded aws", f'AWS_ACCESS_KEY = "{_AWS}"', "secret/aws-access-key"),
]


@pytest.mark.parametrize(("label", "line", "rule_id"), MALICIOUS)
def test_malicious_payloads_are_caught(label: str, line: str, rule_id: str) -> None:
    findings = review_lines("attack.py", [(1, line)])
    assert rule_id in _ids(findings), f"{label}: expected {rule_id}, got {sorted(_ids(findings))}"


def test_critical_payloads_are_critical() -> None:
    findings = review_lines("attack.py", [(1, 'os.system(f"ping {host}")')])
    assert any(finding.severity is Severity.CRITICAL for finding in findings)


# --------------------------------------------------------------------------- #
# Suppression
# --------------------------------------------------------------------------- #


def test_bare_noqa_suppresses_the_line() -> None:
    findings = review_lines("x.py", [(1, 'API_KEY = "abcd1234efgh5678"  # noqa')])
    assert findings == []


def test_targeted_noqa_suppresses_one_rule() -> None:
    line = 'TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz1234"  # noqa: secret/github-token'
    fired = _ids(review_lines("x.py", [(1, line)]))
    assert "secret/github-token" not in fired
    assert "secret/hardcoded-credential" in fired


def test_nosec_suppresses_the_line() -> None:
    assert review_lines("x.py", [(1, 'os.system("ls")  # nosec')]) == []


def test_noqa_does_not_leak_to_other_lines() -> None:
    findings = review_lines(
        "x.py",
        [(1, 'os.system("ls")  # noqa'), (2, 'os.system("rm -rf /")')],
    )
    assert [finding.line for finding in findings] == ["2"]


# --------------------------------------------------------------------------- #
# Filtering, ordering and determinism
# --------------------------------------------------------------------------- #


def test_min_severity_filter() -> None:
    bundle = parse_diff_file(SAMPLE)
    everything = review_diff(bundle)
    critical_only = review_diff(bundle, min_severity=Severity.CRITICAL)
    assert everything and critical_only
    assert all(finding.severity is Severity.CRITICAL for finding in critical_only)
    assert len(critical_only) < len(everything)


def test_category_filter() -> None:
    bundle = parse_diff_file(SAMPLE)
    secrets_only = review_diff(bundle, categories=[RuleCategory.SECRETS])
    assert secrets_only
    assert all("secret/" in finding.issue for finding in secrets_only)


def test_findings_are_sorted_critical_first() -> None:
    findings = review_diff(parse_diff_file(SAMPLE))
    ranks = [finding.severity.rank for finding in findings]
    assert ranks == sorted(ranks, reverse=True)


def test_engine_is_deterministic() -> None:
    first = [finding.model_dump() for finding in review_diff(parse_diff_file(SAMPLE))]
    second = [finding.model_dump() for finding in review_diff(parse_diff_file(SAMPLE))]
    assert first == second


def test_findings_only_on_added_lines() -> None:
    raw = (
        "diff --git a/m.py b/m.py\n"
        "--- a/m.py\n+++ b/m.py\n"
        "@@ -1,3 +1,3 @@\n"
        "-API_KEY = 'ghp_removedTokenValue1234567890'\n"
        "+value = 1\n"
        " context\n"
    )
    findings = review_diff(parse_diff(raw))
    assert "secret/github-token" not in _ids(findings)


def test_every_finding_on_the_fixture_is_anchorable() -> None:
    bundle = parse_diff_file(SAMPLE)
    findings = review_diff(bundle)
    anchors = anchor_findings(bundle, findings)
    assert len(anchors) == len(findings)
    assert all(anchor.status.value == "anchored" for anchor in anchors)
    assert all(anchor.hunk_header for anchor in anchors)


def test_empty_input_is_not_an_error() -> None:
    assert review_lines("x.py", []) == []
    assert review_diff(bundle_from_source("empty.py", "")) == []


# --------------------------------------------------------------------------- #
# Robustness: hostile and degenerate input
# --------------------------------------------------------------------------- #


def test_very_long_line_is_bounded_and_flagged() -> None:
    started = time.perf_counter()
    findings = review_lines("x.py", [(1, "value = " + "a" * 100_000)])
    elapsed = time.perf_counter() - started
    assert elapsed < 2.0
    assert "style/long-line" in _ids(findings)


def test_regex_flood_does_not_blow_up() -> None:
    hostile = "if " * 5_000 + "select " * 5_000
    started = time.perf_counter()
    review_lines("x.py", [(index, hostile) for index in range(1, 11)])
    assert time.perf_counter() - started < 5.0


def test_unicode_and_control_characters_are_handled() -> None:
    findings = review_lines(
        "x.py",
        [
            (1, "# 日本語のコメント 🚀"),
            (2, "\t\tdef naïve(führ):"),
            (3, "value = '\\x1b[31mred\\x1b[0m'"),
            (4, "\u200b zero width space"),
        ],
    )
    assert isinstance(findings, list)


def test_tabs_count_towards_nesting() -> None:
    findings = review_lines("x.py", [(1, "\t\t\t\t\t\tif value:")])
    assert "complexity/deep-nesting" in _ids(findings)


def test_entropy_helper_bounds() -> None:
    assert shannon_entropy("") == 0.0
    assert shannon_entropy("aaaaaaaa") == 0.0
    assert 3.0 < shannon_entropy(_ENTROPY) <= 5.0


def test_duplicate_findings_are_collapsed() -> None:
    findings = review_lines("x.py", [(1, 'os.system("ls")')])
    keys = [(finding.file, finding.line, finding.issue) for finding in findings]
    assert len(keys) == len(set(keys))


def test_finding_model_stays_five_fields() -> None:
    finding = review_lines("x.py", [(1, 'os.system("ls")')])[0]
    assert set(finding.model_dump()) == {"file", "line", "severity", "issue", "suggested_fix"}
    with pytest.raises(Exception):
        Finding(file="x.py", line="1", severity=Severity.LOW, issue="i", suggested_fix="f", extra=1)
