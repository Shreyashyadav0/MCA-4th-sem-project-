"""Deterministic local rule engine — OWASP-mapped, no network, no API key, no LLM.

Design contract
---------------
* **Deterministic.** Same diff in, byte-identical findings out. No clock, no
  randomness, no network, no model. A demo cannot flake.
* **Added lines only.** Rules never see removed lines or untouched context, so a
  finding can always be attached to a line the pull request actually changed.
* **Bounded.** Every pattern is linear (no nested quantifiers), and each line is
  truncated to :data:`_MAX_REGEX_LINE` characters before scanning, so a 10 MB
  minified line cannot turn a regex into a denial of service.
* **Suppressible.** ``# noqa`` on a line suppresses everything on it,
  ``# noqa: unsafe/sql-injection`` suppresses one rule. ``# nosec`` is accepted
  as a synonym because reviewers arrive with that habit already.
* **Enumerable.** Every rule lives in :data:`RULES` with an id, a title, a
  category and an OWASP mapping, so ``GET /rules`` can publish the whole policy
  and a test can assert there are no duplicate ids.

Severity rubric (project-wide): a committed secret, an injection sink or dynamic
code execution is CRITICAL; a missing timeout, disabled TLS check, ``shell=True``
or unsafe deserialisation is HIGH; a bare ``except``, mutable default, missing
type hints, weak crypto or debug flag is MEDIUM; style is LOW.

Nothing in this module imports ``httpx``, ``openai`` or ``sarvam``: the local
path is real logic, not a placeholder.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from enum import Enum

from app.models import Finding, Severity, sort_findings
from app.parser import DiffBundle

__all__ = [
    "Rule",
    "RuleHit",
    "RuleCategory",
    "LineContext",
    "RULES",
    "RULES_BY_ID",
    "RULE_COUNT",
    "review_diff",
    "review_lines",
    "rule_ids",
    "rule_by_id",
    "shannon_entropy",
]

# Longest slice of a single line that any regex is allowed to see.
_MAX_REGEX_LINE = 4000


class RuleCategory(str, Enum):
    """Coarse grouping used by the API and the report."""

    SECRETS = "secrets"
    INJECTION = "injection"
    DESERIALISATION = "deserialisation"
    CRYPTO = "crypto"
    AUTH = "auth"
    CONFIG = "config"
    RELIABILITY = "reliability"
    QUALITY = "quality"
    COMPLEXITY = "complexity"
    STYLE = "style"


@dataclass(frozen=True, slots=True)
class RuleHit:
    """What a rule returns when it fires: the prose and the concrete fix."""

    issue: str
    suggested_fix: str


@dataclass(frozen=True, slots=True)
class LineContext:
    """One added line, plus the sibling added lines a rule may need."""

    path: str
    lineno: int
    text: str
    added: tuple[tuple[int, str], ...]
    index: int

    @property
    def scan_text(self) -> str:
        """The line, truncated to the regex budget."""
        if len(self.text) <= _MAX_REGEX_LINE:
            return self.text
        return self.text[:_MAX_REGEX_LINE]

    @property
    def indent(self) -> int:
        """Leading whitespace width, with tabs expanded to four columns."""
        expanded = self.text.expandtabs(4)
        return len(expanded) - len(expanded.lstrip())

    @property
    def is_test_file(self) -> bool:
        """True for test paths, where prints, asserts and fake keys are legitimate."""
        lowered = self.path.lower()
        return "test" in lowered or lowered.endswith(("conftest.py", "tests.py"))


@dataclass(frozen=True, slots=True)
class Rule:
    """A named check with one fixed severity, category and OWASP mapping."""

    id: str
    title: str
    category: RuleCategory
    owasp: str
    severity: Severity
    check: Callable[[LineContext], RuleHit | None]


Checker = Callable[[LineContext], RuleHit | None]
RULES: list[Rule] = []


def _register(rule: Rule) -> None:
    """Append a rule to the registry."""
    RULES.append(rule)


def _rule(
    rule_id: str, severity: Severity, title: str, category: RuleCategory, owasp: str
) -> Callable[[Checker], Checker]:
    """Register a hand-written check under ``rule_id``."""

    def decorator(check: Checker) -> Checker:
        _register(Rule(rule_id, title, category, owasp, severity, check))
        return check

    return decorator


def _pattern_rule(
    *,
    rule_id: str,
    title: str,
    category: RuleCategory,
    owasp: str,
    severity: Severity,
    pattern: re.Pattern[str],
    issue: str,
    suggested_fix: str,
    exempt: re.Pattern[str] | None = None,
    skip_tests: bool = False,
) -> None:
    """Register a rule that fires when ``pattern`` matches and ``exempt`` does not."""

    def check(ctx: LineContext) -> RuleHit | None:
        if skip_tests and ctx.is_test_file:
            return None
        text = ctx.scan_text
        if pattern.search(text) is None:
            return None
        if exempt is not None and exempt.search(text) is not None:
            return None
        return RuleHit(issue=issue, suggested_fix=suggested_fix)

    _register(Rule(rule_id, title, category, owasp, severity, check))


def shannon_entropy(value: str) -> float:
    """Shannon entropy in bits per character, used for secret heuristics.

    Args:
        value: Candidate string.

    Returns:
        Entropy in ``[0, log2(len(set(value)))]``; ``0.0`` for an empty string.
    """
    if not value:
        return 0.0
    length = len(value)
    return -sum(
        (count / length) * math.log2(count / length) for count in Counter(value).values()
    )


# --------------------------------------------------------------------------- #
# Shared patterns
# --------------------------------------------------------------------------- #

_COMMENT_SPLIT_RE = re.compile(r"\s+#")


def _strip_trailing_comment(text: str) -> str:
    """Drop a trailing ``# comment`` so assignment rules see the value, not the note.

    Leaves the line untouched when a quote count is odd, which is the signal that
    the ``#`` sits inside an unterminated string literal.
    """
    match = _COMMENT_SPLIT_RE.search(text)
    if match is None:
        return text
    head = text[: match.start()]
    if head.count('"') % 2 == 1 or head.count("'") % 2 == 1:
        return text
    return head


_ASSIGN_RE = re.compile(
    r"^\s*(?:self\.)?(?P<name>[A-Za-z_][\w.]*)\s*(?::\s*[^=]+)?=\s*(?P<value>.+?)\s*$"
)
_STRING_LITERAL_RE = re.compile(
    r"""^[rbfuRBFU]{0,2}(?P<q>\"\"\"|'''|\"|')(?P<body>.*)(?P=q)$""", re.DOTALL
)
_SECRET_NAME_RE = re.compile(
    r"(?i)(api[_-]?key|apikey|secret|token|passwd|password|pwd|"
    r"private[_-]?key|access[_-]?key|client[_-]?secret|auth[_-]?key|"
    r"credential|bearer|session[_-]?key|signing[_-]?key|encryption[_-]?key)"
)
_ENV_LOOKUP_RE = re.compile(
    r"(?i)(os\.environ|getenv|settings\.|config\.|ENV\[|env\.|secrets\.|vault|keyring)"
)
_PLACEHOLDER_RE = re.compile(
    r"(?i)^(?:|none|null|changeme|change[_-]?me|your[_-]?\w*|x{3,}|\*{3,}|<[^>]*>|"
    r"\$\{[^}]*\}|\{\{[^}]*\}\}|placeholder|dummy|example[\w-]*|test[\w-]*|"
    r"todo|secret|password|token|redacted|sample[\w-]*)$"
)

_AWS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA)[0-9A-Z]{16}\b")
_AWS_SECRET_ASSIGN_RE = re.compile(
    r"(?i)aws_?secret_?access_?key\s*[:=]\s*[\"'][^\"']{20,}[\"']"
)
_GITHUB_TOKEN_RE = re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")
_GITLAB_TOKEN_RE = re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")
_SLACK_TOKEN_RE = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")
_STRIPE_KEY_RE = re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b")
_GOOGLE_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")
_OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")
_PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.")
_BASIC_AUTH_URL_RE = re.compile(r"[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s:@]{3,}@")
_CONN_PASSWORD_RE = re.compile(r"(?i)(password|passwd|pwd)\s*=\s*[^\s;&\"']{4,}")
_BEARER_LITERAL_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{16,}")
_HIGH_ENTROPY_RE = re.compile(r"[\"'](?P<body>[A-Za-z0-9+/=_\-]{32,})[\"']")
_ENTROPY_EXEMPT_RE = re.compile(
    r"(?i)(sha256|sha1|md5|hash|uuid|format|schema|content-type|http|https|url|"
    r"path|select |insert |update |delete |example|sample|dummy|placeholder|"
    r"\.png|\.jpg|\.jpeg|\.svg|\.gif|application/|text/)"
)

_SQL_KEYWORD_RE = re.compile(r"(?i)\b(?:select|insert|update|delete|drop|alter|create|truncate)\b")
_SQL_CALL_RE = re.compile(r"(?i)\b(?:execute|executemany|raw|read_sql|text|RawSQL)\s*\(")
_SQL_VAR_RE = re.compile(r"(?i)\b(?:query|sql|stmt|statement|clause|filter_sql)\b")
_INTERP_RE = re.compile(
    r"""(?:\bf\"|\bf'|\bF\"|\bF'|\.format\s*\(|["']\s*%\s*(?:\(|[A-Za-z_]))"""
)
_SQL_CONCAT_RE = re.compile(r"""(?:["']\s*\+\s*[A-Za-z_]|[A-Za-z_)\]]\s*\+\s*["'])""")

_SHELL_CALL_RE = re.compile(
    r"\b(?:os\.system|os\.popen|subprocess\.(?:run|call|check_call|check_output|Popen))"
    r"\s*\("
)
_CMD_INTERP_RE = re.compile(r"""(?:\bf\"|\bf'|\.format\s*\(|%\s*\(|["']\s*\+\s*[A-Za-z_])""")
_EVAL_RE = re.compile(r"(?<![\w.])(?:eval|exec)\s*\(\s*[^)\s]")
_COMPILE_RE = re.compile(r"(?<![\w.])compile\s*\(\s*(?![rbfuRBFU]*[\"'])")
_SHELL_TRUE_RE = re.compile(r"(?i)\bshell\s*=\s*True\b")
_OS_SYSTEM_RE = re.compile(r"\bos\.(?:system|popen)\s*\(")
_PICKLE_RE = re.compile(r"\b(?:pickle|dill|jsonpickle|marshal|cPickle)\.loads?\s*\(")
_YAML_LOAD_RE = re.compile(r"\byaml\.load\s*\(")
_YAML_UNSAFE_RE = re.compile(r"\byaml\.(?:unsafe_load|full_load)\s*\(")
_YAML_FULL_LOADER_RE = re.compile(r"\byaml\.(?:FullLoader|UnsafeLoader|Loader)\b")
_XXE_RE = re.compile(r"resolve_entities\s*=\s*True")
_PATH_TRAVERSAL_RE = re.compile(
    r"(?:\bopen\s*\(|\bos\.path\.join\s*\(|Path\s*\()\s*[^)]*"
    r"(?:\brequest\.|\binput\s*\(|\bsys\.argv|\.\./|f\"|\bf')"
)
_SSRF_RE = re.compile(
    r"\b(?:requests|httpx|urllib\.request|urlopen)\b[^#]*\("
    r"[^)]*(?:\brequest\.|\bparams\[|\binput\s*\(|user_url|target_url|redirect_url)"
)
_OPEN_REDIRECT_RE = re.compile(r"\bredirect\s*\(\s*(?:request\.|\bparams\[|\bnext\b)")
_TEMPLATE_INJECTION_RE = re.compile(r"\brender_template_string\s*\(")
_LDAP_INTERP_RE = re.compile(r"(?i)\bldap\w*\b[^#]*(?:\bf\"|\bf'|\.format\s*\(|%\s*\()")
_NOSQL_INJECT_RE = re.compile(r"\$(?:where|regex|ne|gt|lt)\b")

_WEAK_HASH_RE = re.compile(r"\bhashlib\.(?:md5|sha1)\s*\(")
_ECB_RE = re.compile(r"(?:\bMODE_ECB\b|\bmodes\.ECB\s*\()")
_INSECURE_RANDOM_RE = re.compile(r"\brandom\.(?:random|randint|randrange|choice|choices|sample)\s*\(")
_RANDOM_SECRET_CONTEXT_RE = re.compile(r"(?i)(token|secret|password|nonce|salt|otp|csrf|key)")
_STATIC_IV_RE = re.compile(r"(?i)\b(?:iv|nonce)\s*[:=]\s*b?[\"'][^\"']{8,}[\"']")
_VERIFY_FALSE_RE = re.compile(r"(?i)\bverify\s*=\s*False\b")
_UNVERIFIED_CTX_RE = re.compile(r"(?:_create_unverified_context|check_hostname\s*=\s*False|CERT_NONE)")

_ASSERT_AUTH_RE = re.compile(
    r"(?i)^\s*assert\s+[^#]*(?:is_admin|is_authenticated|has_perm|authoriz|permission|"
    r"is_staff|role\s*==|logged_in)"
)
_PASSWORD_COMPARE_RE = re.compile(
    r"(?i)\b(?:password|passwd|token|secret|api_key|otp)\w*\s*(?:==|!=)\s*\S"
)
_DEBUG_RE = re.compile(r"(?i)(?:\bDEBUG\s*=\s*True|\bdebug\s*=\s*True)")
_CORS_WILDCARD_RE = re.compile(r"allow_origins\s*=\s*\[\s*[\"']\*[\"']")
_CORS_CREDS_RE = re.compile(r"allow_credentials\s*=\s*True")
_BIND_ALL_RE = re.compile(r"[\"']0\.0\.0\.0[\"']")
_CHMOD_777_RE = re.compile(r"(?:\bchmod\s*\(?[^)\n]*0?o?777|chmod\s+777)")
_CSRF_OFF_RE = re.compile(r"(?:@csrf_exempt|WTF_CSRF_ENABLED\s*=\s*False|csrf\s*=\s*False)")
_ALLOWED_HOSTS_WILDCARD_RE = re.compile(r"ALLOWED_HOSTS\s*=\s*\[[^\]]*[\"']\*[\"']")

_HTTP_CALL_RE = re.compile(
    r"\b(?:requests|httpx|session|client)\.(?:get|post|put|patch|delete|head|request)\s*\("
)
_SUBPROCESS_NO_CHECK_RE = re.compile(r"\bsubprocess\.(?:run|call|check_output|check_call)\s*\(")
_OPEN_CALL_RE = re.compile(r"\bopen\s*\(")
_WITH_OPEN_RE = re.compile(r"\bwith\s+open\s*\(")

_BARE_EXCEPT_RE = re.compile(r"^\s*except\s*:")
_EXCEPT_PASS_RE = re.compile(r"^\s*except[^:]*:\s*pass\s*$")
_MUTABLE_DEFAULT_RE = re.compile(
    r"\bdef\s+\w+\s*\([^)]*=\s*(?:\[\s*\]|\{\s*\}|set\(\s*\)|dict\(\s*\)|list\(\s*\))"
)
_DEF_RE = re.compile(
    r"^\s*(?P<async>async\s+)?def\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)"
    r"\s*(?P<ret>->\s*[^:]+)?:"
)

_PRINT_RE = re.compile(r"(?<![\w.])print\s*\(")
_TODO_RE = re.compile(r"(?i)#\s*(?:todo|fixme|xxx|hack)\b")
_WILDCARD_IMPORT_RE = re.compile(r"^\s*from\s+[\w.]+\s+import\s+\*")
_BRANCH_RE = re.compile(r"\b(?:if|elif|for|while|except|and|or|case|when)\b")
_DEEP_BRANCH_RE = re.compile(r"\b(?:if|for|while|try|with|match)\b")
_NOQA_RE = re.compile(r"#\s*(?:noqa|nosec)(?P<ids>[:=][A-Za-z0-9_,\s/\-]+)?", re.IGNORECASE)

_LONG_LINE = 120
_BRANCH_BUDGET = 8
_MAX_PARAMS = 5
_DEEP_INDENT = 20
_ENTROPY_THRESHOLD = 4.2
_DUNDER_EXEMPT = {
    "__init__",
    "__str__",
    "__repr__",
    "__eq__",
    "__hash__",
    "__enter__",
    "__exit__",
    "__post_init__",
}

_OWASP_INJECTION = "A03:2021-Injection"
_OWASP_CRYPTO = "A02:2021-Cryptographic Failures"
_OWASP_CONFIG = "A05:2021-Security Misconfiguration"
_OWASP_AUTH = "A07:2021-Identification and Authentication Failures"
_OWASP_INTEGRITY = "A08:2021-Software and Data Integrity Failures"
_OWASP_ACCESS = "A01:2021-Broken Access Control"
_OWASP_SSRF = "A10:2021-Server-Side Request Forgery"
_OWASP_DESIGN = "A04:2021-Insecure Design"
_OWASP_LOGGING = "A09:2021-Security Logging and Monitoring Failures"


# --------------------------------------------------------------------------- #
# Secrets and credentials  (A02 / A07)
# --------------------------------------------------------------------------- #


@_rule(
    "secret/hardcoded-credential",
    Severity.CRITICAL,
    "Hardcoded credential",
    RuleCategory.SECRETS,
    _OWASP_CRYPTO,
)
def _check_hardcoded_secret(ctx: LineContext) -> RuleHit | None:
    """A credential-shaped name assigned a string literal that is not a placeholder."""
    match = _ASSIGN_RE.match(_strip_trailing_comment(ctx.scan_text))
    if match is None:
        return None
    name = match.group("name")
    value = match.group("value").rstrip(",;")
    if _SECRET_NAME_RE.search(name) is None:
        return None
    if _ENV_LOOKUP_RE.search(value) is not None:
        return None
    literal = _STRING_LITERAL_RE.match(value)
    if literal is None:
        return None
    body = literal.group("body")
    if len(body) < 8 or _PLACEHOLDER_RE.match(body.strip()) is not None:
        return None
    return RuleHit(
        issue=(
            f"`{name}` is assigned a literal credential, so the secret is committed to git "
            "history and stays readable to anyone with repo access even after it is rotated."
        ),
        suggested_fix=(
            f'{name} = os.environ["{re.sub(r"[^A-Z0-9]+", "_", name.upper())}"]  '
            "# load from the environment; fail loudly when it is unset"
        ),
    )


_pattern_rule(
    rule_id="secret/aws-access-key",
    title="AWS access key id",
    category=RuleCategory.SECRETS,
    owasp=_OWASP_CRYPTO,
    severity=Severity.CRITICAL,
    pattern=_AWS_KEY_RE,
    issue=(
        "An AWS access key id is embedded in source, exposing the account to anyone who can "
        "read the repository or its history."
    ),
    suggested_fix=(
        "Delete the key, rotate it in IAM, and let the SDK discover credentials from the "
        "environment or an instance role: `boto3.client('s3')` with no inline keys."
    ),
)

_pattern_rule(
    rule_id="secret/aws-secret-key",
    title="AWS secret access key",
    category=RuleCategory.SECRETS,
    owasp=_OWASP_CRYPTO,
    severity=Severity.CRITICAL,
    pattern=_AWS_SECRET_ASSIGN_RE,
    issue="An AWS secret access key is committed here, which is a full credential for the account.",
    suggested_fix=(
        'aws_secret_access_key = os.environ["AWS_SECRET_ACCESS_KEY"]  '
        "# rotate the exposed key first"
    ),
)

_pattern_rule(
    rule_id="secret/github-token",
    title="GitHub token",
    category=RuleCategory.SECRETS,
    owasp=_OWASP_CRYPTO,
    severity=Severity.CRITICAL,
    pattern=_GITHUB_TOKEN_RE,
    issue=(
        "A GitHub token literal is committed here, granting every scope the token holds to "
        "anyone who reads the repository."
    ),
    suggested_fix='Revoke the token, then read it at runtime: `token = os.environ["GITHUB_TOKEN"]`.',
)

_pattern_rule(
    rule_id="secret/gitlab-token",
    title="GitLab token",
    category=RuleCategory.SECRETS,
    owasp=_OWASP_CRYPTO,
    severity=Severity.CRITICAL,
    pattern=_GITLAB_TOKEN_RE,
    issue="A GitLab personal access token is committed here and can read or write the projects it scopes.",
    suggested_fix='Revoke it in GitLab and load it at runtime: `os.environ["GITLAB_TOKEN"]`.',
)

_pattern_rule(
    rule_id="secret/slack-token",
    title="Slack token",
    category=RuleCategory.SECRETS,
    owasp=_OWASP_CRYPTO,
    severity=Severity.CRITICAL,
    pattern=_SLACK_TOKEN_RE,
    issue="A Slack token is committed here, so anyone with repository access can post or read workspace data.",
    suggested_fix='Revoke the token and read it from the environment: `os.environ["SLACK_TOKEN"]`.',
)

_pattern_rule(
    rule_id="secret/stripe-key",
    title="Stripe secret key",
    category=RuleCategory.SECRETS,
    owasp=_OWASP_CRYPTO,
    severity=Severity.CRITICAL,
    pattern=_STRIPE_KEY_RE,
    issue="A Stripe secret key is committed here, allowing charges and refunds against the account.",
    suggested_fix='Rotate the key in the Stripe dashboard and read it at runtime: `os.environ["STRIPE_KEY"]`.',
)

_pattern_rule(
    rule_id="secret/google-api-key",
    title="Google API key",
    category=RuleCategory.SECRETS,
    owasp=_OWASP_CRYPTO,
    severity=Severity.CRITICAL,
    pattern=_GOOGLE_KEY_RE,
    issue="A Google API key is committed here and can be used to bill quota against the project.",
    suggested_fix='Restrict and rotate the key, then load it at runtime: `os.environ["GOOGLE_API_KEY"]`.',
)

_pattern_rule(
    rule_id="secret/openai-key",
    title="OpenAI-style secret key",
    category=RuleCategory.SECRETS,
    owasp=_OWASP_CRYPTO,
    severity=Severity.CRITICAL,
    pattern=_OPENAI_KEY_RE,
    issue="A provider secret key is committed here, so the account can be used at your cost.",
    suggested_fix='Revoke the key and read it from the environment: `os.environ["OPENAI_API_KEY"]`.',
)

_pattern_rule(
    rule_id="secret/private-key-block",
    title="Private key block",
    category=RuleCategory.SECRETS,
    owasp=_OWASP_CRYPTO,
    severity=Severity.CRITICAL,
    pattern=_PRIVATE_KEY_RE,
    issue="A private key block is stored in the repository, so every clone carries a usable credential.",
    suggested_fix=(
        "Delete the key material, rotate it, and load the key from outside the repo: "
        "`Path(os.environ['KEY_PATH']).read_bytes()`."
    ),
)

_pattern_rule(
    rule_id="secret/jwt-literal",
    title="JWT literal",
    category=RuleCategory.SECRETS,
    owasp=_OWASP_AUTH,
    severity=Severity.HIGH,
    pattern=_JWT_RE,
    issue="A signed JWT is hardcoded, so it can be replayed until expiry and leaks the claims inside it.",
    suggested_fix="Mint the token at runtime and keep it in memory: `token = client.issue_token()`.",
)

_pattern_rule(
    rule_id="secret/basic-auth-url",
    title="Credentials in URL",
    category=RuleCategory.SECRETS,
    owasp=_OWASP_CRYPTO,
    severity=Severity.HIGH,
    pattern=_BASIC_AUTH_URL_RE,
    exempt=re.compile(r"(?i)(\$\{|<[^>]*>|%\(|example|localhost|user:pass@)"),
    issue=(
        "A URL carries a username and password inline, so the credential lands in logs, shell "
        "history and the source file at once."
    ),
    suggested_fix=(
        "Pass credentials out of band: "
        '`httpx.get(url, auth=(os.environ["USER"], os.environ["PASS"]))`.'
    ),
)

_pattern_rule(
    rule_id="secret/connection-string-password",
    title="Password in connection string",
    category=RuleCategory.SECRETS,
    owasp=_OWASP_CRYPTO,
    severity=Severity.HIGH,
    pattern=_CONN_PASSWORD_RE,
    exempt=re.compile(r"(?i)(os\.environ|getenv|settings\.|\$\{|<[^>]*>|placeholder|example)"),
    issue="A database password is written inline in a connection string, so it is committed with the code.",
    suggested_fix=(
        "Build the DSN from the environment: "
        '`f"postgresql://{os.environ[\'DB_USER\']}:{os.environ[\'DB_PASS\']}@host/db"`.'
    ),
)

_pattern_rule(
    rule_id="secret/bearer-literal",
    title="Bearer token literal",
    category=RuleCategory.SECRETS,
    owasp=_OWASP_CRYPTO,
    severity=Severity.HIGH,
    pattern=_BEARER_LITERAL_RE,
    exempt=re.compile(r"(?i)(os\.environ|\$\{|f\"|f'|settings\.|<[^>]*>)"),
    issue="An Authorization header is built from a token literal, so the credential ships with the code.",
    suggested_fix=(
        'headers = {"Authorization": f"Bearer {os.environ[\'API_TOKEN\']}"}  '
        "# never inline the token"
    ),
)


@_rule(
    "secret/high-entropy-string",
    Severity.MEDIUM,
    "High-entropy string (possible secret)",
    RuleCategory.SECRETS,
    _OWASP_CRYPTO,
)
def _check_high_entropy(ctx: LineContext) -> RuleHit | None:
    """A long random-looking literal that no named secret pattern already caught.

    Deliberately MEDIUM: entropy is a heuristic, and a false CRITICAL on a hash
    constant would train the team to ignore the tool.
    """
    if ctx.is_test_file:
        return None
    match = _HIGH_ENTROPY_RE.search(ctx.scan_text)
    if match is None:
        return None
    if _ENTROPY_EXEMPT_RE.search(ctx.scan_text) is not None:
        return None
    body = match.group("body")
    if shannon_entropy(body) < _ENTROPY_THRESHOLD:
        return None
    return RuleHit(
        issue=(
            f"A {len(body)}-character literal with {shannon_entropy(body):.1f} bits/char of entropy "
            "looks like a generated secret rather than text, and it is committed to the repository."
        ),
        suggested_fix=(
            "If it is a credential, move it to the environment and rotate it; if it is a constant, "
            "name it (e.g. `PUBLIC_AVATAR_HASH`) so the next reader does not have to guess."
        ),
    )


# --------------------------------------------------------------------------- #
# Injection  (A03)
# --------------------------------------------------------------------------- #


@_rule(
    "unsafe/sql-injection",
    Severity.CRITICAL,
    "SQL injection",
    RuleCategory.INJECTION,
    _OWASP_INJECTION,
)
def _check_sql_injection(ctx: LineContext) -> RuleHit | None:
    """Interpolated SQL, whether executed inline or built into a query variable."""
    text = ctx.scan_text
    if _SQL_KEYWORD_RE.search(text) is None or _INTERP_RE.search(text) is None:
        return None
    if _SQL_CALL_RE.search(text) is None and _SQL_VAR_RE.search(text) is None:
        return None
    return RuleHit(
        issue=(
            "SQL is assembled by string interpolation, so any value reaching this line can change "
            "the statement and read, alter or drop the table."
        ),
        suggested_fix=(
            'Pass parameters instead: `db.execute("SELECT * FROM users WHERE id = ?", (uid,))` — '
            "the driver quotes them, interpolation does not."
        ),
    )


@_rule(
    "unsafe/sql-injection-concat",
    Severity.CRITICAL,
    "SQL injection by concatenation",
    RuleCategory.INJECTION,
    _OWASP_INJECTION,
)
def _check_sql_concat(ctx: LineContext) -> RuleHit | None:
    """SQL built with ``+`` against a variable."""
    text = ctx.scan_text
    if _SQL_KEYWORD_RE.search(text) is None or _SQL_CONCAT_RE.search(text) is None:
        return None
    if _SQL_CALL_RE.search(text) is None and _SQL_VAR_RE.search(text) is None:
        return None
    return RuleHit(
        issue=(
            "The SQL string is concatenated with a variable, so the value can terminate the "
            "clause and append its own statement."
        ),
        suggested_fix=(
            'Use a placeholder: `db.execute("SELECT * FROM users WHERE name = ?", (name,))`.'
        ),
    )


@_rule(
    "unsafe/raw-sql",
    Severity.HIGH,
    "Raw SQL execution",
    RuleCategory.INJECTION,
    _OWASP_INJECTION,
)
def _check_raw_sql(ctx: LineContext) -> RuleHit | None:
    """Django ``.raw()`` / ``RawSQL`` with any interpolation."""
    text = ctx.scan_text
    if re.search(r"(?i)(\.raw\s*\(|RawSQL\s*\()", text) is None:
        return None
    if _INTERP_RE.search(text) is None and _SQL_CONCAT_RE.search(text) is None:
        return None
    return RuleHit(
        issue=(
            "A raw SQL escape hatch is fed an interpolated string, which bypasses the ORM's "
            "parameter binding entirely."
        ),
        suggested_fix=(
            'Keep the escape hatch but parameterise it: '
            '`Model.objects.raw("SELECT * FROM t WHERE id = %s", [model_id])`.'
        ),
    )


@_rule(
    "unsafe/eval-exec",
    Severity.CRITICAL,
    "Dynamic code execution",
    RuleCategory.INJECTION,
    _OWASP_INJECTION,
)
def _check_eval(ctx: LineContext) -> RuleHit | None:
    """``eval``/``exec`` on a non-empty argument."""
    if _EVAL_RE.search(ctx.scan_text) is None:
        return None
    return RuleHit(
        issue=(
            "`eval`/`exec` runs whatever string reaches it, so untrusted input becomes arbitrary "
            "code execution inside your process."
        ),
        suggested_fix=(
            "Parse the data instead of executing it: `json.loads(payload)` for JSON, "
            "`ast.literal_eval(raw)` for Python literals."
        ),
    )


@_rule(
    "unsafe/compile-input",
    Severity.HIGH,
    "Dynamic compilation",
    RuleCategory.INJECTION,
    _OWASP_INJECTION,
)
def _check_compile(ctx: LineContext) -> RuleHit | None:
    """``compile`` on a non-literal argument."""
    if _COMPILE_RE.search(ctx.scan_text) is None:
        return None
    return RuleHit(
        issue=(
            "`compile` turns a runtime string into bytecode, so untrusted input becomes code that "
            "can be executed with `exec`."
        ),
        suggested_fix=(
            "Keep configuration in data, not code: `config = json.loads(raw)` and read keys from it."
        ),
    )


@_rule(
    "unsafe/command-injection",
    Severity.CRITICAL,
    "Command injection",
    RuleCategory.INJECTION,
    _OWASP_INJECTION,
)
def _check_command_injection(ctx: LineContext) -> RuleHit | None:
    """A shell or subprocess call fed an interpolated string."""
    text = ctx.scan_text
    if _SHELL_CALL_RE.search(text) is None or _CMD_INTERP_RE.search(text) is None:
        return None
    return RuleHit(
        issue=(
            "A command string is built by interpolation, so a value containing `;`, `&&` or `$()` "
            "runs whatever it likes on the host."
        ),
        suggested_fix=(
            'Pass an argument list and no shell: `subprocess.run(["ping", "-c", "1", host], '
            "check=True, timeout=5)`."
        ),
    )


_pattern_rule(
    rule_id="unsafe/shell-true",
    title="Shell injection risk",
    category=RuleCategory.INJECTION,
    owasp=_OWASP_INJECTION,
    severity=Severity.HIGH,
    pattern=_SHELL_TRUE_RE,
    issue=(
        "`shell=True` hands the command line to a shell, so any interpolated value can append "
        "extra commands."
    ),
    suggested_fix=(
        'Drop the shell and pass a list: `subprocess.run(["ls", "-l", path], check=True, timeout=10)`.'
    ),
)

_pattern_rule(
    rule_id="unsafe/os-system",
    title="os.system call",
    category=RuleCategory.INJECTION,
    owasp=_OWASP_INJECTION,
    severity=Severity.HIGH,
    pattern=_OS_SYSTEM_RE,
    issue=(
        "`os.system` cannot pass arguments safely, ignores the exit status and has no timeout, so "
        "it is both an injection surface and a silent-failure source."
    ),
    suggested_fix='Use the subprocess API: `subprocess.run(["git", "status"], check=True, timeout=10)`.',
)

_pattern_rule(
    rule_id="unsafe/path-traversal",
    title="Path traversal",
    category=RuleCategory.INJECTION,
    owasp=_OWASP_ACCESS,
    severity=Severity.HIGH,
    pattern=_PATH_TRAVERSAL_RE,
    issue=(
        "A filesystem path is built from a request value or an interpolated string, so `../` in the "
        "input escapes the directory you meant to serve."
    ),
    suggested_fix=(
        "Resolve and confine the path: "
        '`target = (base / name).resolve(); target.relative_to(base)` and raise on escape.'
    ),
)

_pattern_rule(
    rule_id="unsafe/ssrf",
    title="Server-side request forgery",
    category=RuleCategory.INJECTION,
    owasp=_OWASP_SSRF,
    severity=Severity.HIGH,
    pattern=_SSRF_RE,
    issue=(
        "An outbound request is made to a user-controlled URL, so the server can be pointed at "
        "internal services or cloud metadata endpoints."
    ),
    suggested_fix=(
        "Allow-list the hosts and resolve before dialling: reject non-HTTPS, reject private "
        "address ranges, and pin the resolved IP."
    ),
)

_pattern_rule(
    rule_id="unsafe/open-redirect",
    title="Open redirect",
    category=RuleCategory.INJECTION,
    owasp=_OWASP_ACCESS,
    severity=Severity.MEDIUM,
    pattern=_OPEN_REDIRECT_RE,
    issue="A redirect target comes straight from the request, so the app can be used to bounce users to any site.",
    suggested_fix=(
        "Redirect only to known paths: `target = next_path if next_path.startswith('/') else '/'`."
    ),
)

_pattern_rule(
    rule_id="unsafe/template-injection",
    title="Server-side template injection",
    category=RuleCategory.INJECTION,
    owasp=_OWASP_INJECTION,
    severity=Severity.CRITICAL,
    pattern=_TEMPLATE_INJECTION_RE,
    issue=(
        "`render_template_string` compiles a template from a string, so any user value in it can "
        "execute expressions in the template engine."
    ),
    suggested_fix="Render a fixed template file with variables passed as context: `render_template('page.html', name=name)`.",
)

_pattern_rule(
    rule_id="unsafe/ldap-injection",
    title="LDAP injection",
    category=RuleCategory.INJECTION,
    owasp=_OWASP_INJECTION,
    severity=Severity.HIGH,
    pattern=_LDAP_INTERP_RE,
    issue=(
        "An LDAP filter is built by interpolation, so input containing `*` or `)(` can widen the "
        "search to every entry."
    ),
    suggested_fix="Escape the value with `ldap.filter.escape_filter_chars(user_input)` before building the filter.",
)

_pattern_rule(
    rule_id="unsafe/nosql-injection",
    title="NoSQL operator injection",
    category=RuleCategory.INJECTION,
    owasp=_OWASP_INJECTION,
    severity=Severity.HIGH,
    pattern=_NOSQL_INJECT_RE,
    issue=(
        "A MongoDB query operator is passed straight through, so a request body can inject "
        "`$where` or `$ne` and bypass the filter."
    ),
    suggested_fix=(
        "Accept only scalar fields: `User.find_one({'email': str(payload['email'])})` and reject "
        "keys starting with `$`."
    ),
)

# --------------------------------------------------------------------------- #
# Deserialisation  (A08)
# --------------------------------------------------------------------------- #


_pattern_rule(
    rule_id="unsafe/pickle-load",
    title="Unsafe deserialisation (pickle)",
    category=RuleCategory.DESERIALISATION,
    owasp=_OWASP_INTEGRITY,
    severity=Severity.HIGH,
    pattern=_PICKLE_RE,
    issue=(
        "`pickle`/`marshal` execute code carried inside the payload, so loading untrusted bytes is "
        "remote code execution."
    ),
    suggested_fix="Use a data format: `json.loads(blob)`, or sign the payload and verify the HMAC before unpickling.",
)

_pattern_rule(
    rule_id="unsafe/yaml-load",
    title="Unsafe YAML load",
    category=RuleCategory.DESERIALISATION,
    owasp=_OWASP_INTEGRITY,
    severity=Severity.HIGH,
    pattern=_YAML_LOAD_RE,
    exempt=_YAML_FULL_LOADER_RE,
    issue="`yaml.load` without a safe loader can construct arbitrary Python objects from the document.",
    suggested_fix="Use the safe loader: `yaml.safe_load(stream)`.",
)

_pattern_rule(
    rule_id="unsafe/yaml-unsafe-load",
    title="YAML unsafe_load",
    category=RuleCategory.DESERIALISATION,
    owasp=_OWASP_INTEGRITY,
    severity=Severity.CRITICAL,
    pattern=_YAML_UNSAFE_RE,
    issue="`yaml.unsafe_load`/`full_load` deliberately constructs Python objects from the document, which is code execution.",
    suggested_fix="Switch to `yaml.safe_load(stream)` and keep the document to plain data.",
)

_pattern_rule(
    rule_id="unsafe/xxe",
    title="XML external entity expansion",
    category=RuleCategory.DESERIALISATION,
    owasp=_OWASP_INTEGRITY,
    severity=Severity.HIGH,
    pattern=_XXE_RE,
    issue=(
        "Entity resolution is switched on for XML parsing, so a document can read local files or "
        "reach internal URLs."
    ),
    suggested_fix="Keep entities off: `etree.XMLParser(resolve_entities=False, no_network=True)`.",
)

# --------------------------------------------------------------------------- #
# Crypto and transport  (A02)
# --------------------------------------------------------------------------- #


_pattern_rule(
    rule_id="crypto/weak-hash",
    title="Weak hash algorithm",
    category=RuleCategory.CRYPTO,
    owasp=_OWASP_CRYPTO,
    severity=Severity.MEDIUM,
    pattern=_WEAK_HASH_RE,
    issue=(
        "MD5 and SHA-1 are broken for security use, so a password or signature derived from them "
        "can be forged cheaply."
    ),
    suggested_fix=(
        "For passwords use a KDF: `bcrypt.hashpw(password, bcrypt.gensalt())`. For integrity use "
        "`hashlib.sha256(data)`, and for signatures use `hmac.new(key, msg, 'sha256')`."
    ),
)

_pattern_rule(
    rule_id="crypto/ecb-mode",
    title="ECB block mode",
    category=RuleCategory.CRYPTO,
    owasp=_OWASP_CRYPTO,
    severity=Severity.HIGH,
    pattern=_ECB_RE,
    issue=(
        "ECB encrypts identical blocks to identical ciphertext, so patterns in the plaintext leak "
        "through the ciphertext."
    ),
    suggested_fix="Use an authenticated mode with a random nonce: `AESGCM(key)` or `Cipher(algorithms.AES(key), modes.GCM(nonce))`.",
)

_pattern_rule(
    rule_id="crypto/static-iv",
    title="Static IV or nonce",
    category=RuleCategory.CRYPTO,
    owasp=_OWASP_CRYPTO,
    severity=Severity.MEDIUM,
    pattern=_STATIC_IV_RE,
    exempt=re.compile(r"(?i)(os\.urandom|secrets\.|token_bytes|\$\{)"),
    issue=(
        "The IV/nonce is a fixed literal, so every encryption with this key produces related "
        "ciphertext and reuses the keystream."
    ),
    suggested_fix="Generate it per message: `nonce = os.urandom(12)` and store it beside the ciphertext.",
)


@_rule(
    "crypto/insecure-random",
    Severity.HIGH,
    "Non-cryptographic randomness for a secret",
    RuleCategory.CRYPTO,
    _OWASP_CRYPTO,
)
def _check_insecure_random(ctx: LineContext) -> RuleHit | None:
    """``random`` used to build a token, password, nonce or salt."""
    text = ctx.scan_text
    if _INSECURE_RANDOM_RE.search(text) is None:
        return None
    if _RANDOM_SECRET_CONTEXT_RE.search(text) is None:
        return None
    return RuleHit(
        issue=(
            "`random` is a Mersenne Twister, so a token or salt built from it is predictable once "
            "an attacker sees a few outputs."
        ),
        suggested_fix='Use the OS entropy source: `secrets.token_urlsafe(32)` or `os.urandom(32)`.',
    )


_pattern_rule(
    rule_id="security/tls-verify-disabled",
    title="TLS verification disabled",
    category=RuleCategory.CRYPTO,
    owasp=_OWASP_CRYPTO,
    severity=Severity.HIGH,
    pattern=_VERIFY_FALSE_RE,
    issue="`verify=False` disables certificate checks, so the connection can be intercepted without any error.",
    suggested_fix="Drop the flag and point at the right CA bundle: `requests.get(url, timeout=10, verify=ca_bundle_path)`.",
)

_pattern_rule(
    rule_id="security/unverified-ssl-context",
    title="Unverified SSL context",
    category=RuleCategory.CRYPTO,
    owasp=_OWASP_CRYPTO,
    severity=Severity.HIGH,
    pattern=_UNVERIFIED_CTX_RE,
    issue="An SSL context with verification and hostname checks disabled accepts any certificate presented to it.",
    suggested_fix="Use the default context: `ssl.create_default_context()` and load your CA with `load_verify_locations`.",
)

# --------------------------------------------------------------------------- #
# Authentication and authorisation  (A01 / A07)
# --------------------------------------------------------------------------- #


_pattern_rule(
    rule_id="auth/assert-as-check",
    title="assert used for authorisation",
    category=RuleCategory.AUTH,
    owasp=_OWASP_ACCESS,
    severity=Severity.HIGH,
    pattern=_ASSERT_AUTH_RE,
    issue=(
        "An authorisation check is written as `assert`, which disappears entirely under `python -O`, "
        "silently opening the endpoint."
    ),
    suggested_fix=(
        "Raise instead: `if not user.is_admin:\n    raise HTTPException(status_code=403, detail='forbidden')`."
    ),
)

_pattern_rule(
    rule_id="auth/timing-unsafe-compare",
    title="Non-constant-time secret comparison",
    category=RuleCategory.AUTH,
    owasp=_OWASP_AUTH,
    severity=Severity.MEDIUM,
    pattern=_PASSWORD_COMPARE_RE,
    exempt=re.compile(r"(?i)(compare_digest|hashlib|bcrypt|argon2|check_password)"),
    issue=(
        "A secret is compared with `==`, which returns early on the first differing byte and leaks "
        "the correct prefix through timing."
    ),
    suggested_fix='Compare in constant time: `hmac.compare_digest(provided, expected)`.',
)

_pattern_rule(
    rule_id="auth/verify-false-jwt",
    title="JWT signature verification disabled",
    category=RuleCategory.AUTH,
    owasp=_OWASP_AUTH,
    severity=Severity.CRITICAL,
    pattern=re.compile(r"(?i)verify_signature\s*[:=]\s*False|options\s*=\s*\{\s*[\"']verify_signature[\"']\s*:\s*False"),
    issue="JWT signature verification is switched off, so any caller can mint a token for any user.",
    suggested_fix='Verify with the algorithm pinned: `jwt.decode(token, key, algorithms=["RS256"])`.',
)

# --------------------------------------------------------------------------- #
# Misconfiguration  (A05)
# --------------------------------------------------------------------------- #

_pattern_rule(
    rule_id="config/debug-enabled",
    title="Debug mode enabled",
    category=RuleCategory.CONFIG,
    owasp=_OWASP_CONFIG,
    severity=Severity.HIGH,
    pattern=_DEBUG_RE,
    issue=(
        "Debug mode is enabled in code, so a production deploy ships interactive tracebacks, the "
        "Werkzeug console and configuration details to the internet."
    ),
    suggested_fix='Read it from the environment: `DEBUG = os.environ.get("DEBUG", "0") == "1"`.',
)

_pattern_rule(
    rule_id="config/cors-wildcard",
    title="Wildcard CORS origin",
    category=RuleCategory.CONFIG,
    owasp=_OWASP_CONFIG,
    severity=Severity.MEDIUM,
    pattern=_CORS_WILDCARD_RE,
    issue="`allow_origins=['*']` lets any site call this API with the browser's cookies attached.",
    suggested_fix='List the origins you serve: `allow_origins=["https://app.example.com"]`.',
)

_pattern_rule(
    rule_id="config/cors-credentials-wildcard",
    title="Wildcard CORS with credentials",
    category=RuleCategory.CONFIG,
    owasp=_OWASP_CONFIG,
    severity=Severity.HIGH,
    pattern=_CORS_CREDS_RE,
    exempt=re.compile(r"allow_origins\s*=\s*\[\s*[\"'][^*]"),
    issue="Credentials are allowed on a CORS policy, so a wildcard origin would hand every site the user's session.",
    suggested_fix="Pair `allow_credentials=True` with an explicit origin list, never `'*'`.",
)

_pattern_rule(
    rule_id="config/bind-all-interfaces",
    title="Service bound to all interfaces",
    category=RuleCategory.CONFIG,
    owasp=_OWASP_CONFIG,
    severity=Severity.LOW,
    pattern=_BIND_ALL_RE,
    issue="The service listens on every interface, so it is reachable from any network the host is attached to.",
    suggested_fix='Bind loopback for local tools: `host="127.0.0.1"`, and put a proxy in front for public traffic.',
)

_pattern_rule(
    rule_id="config/world-writable-permissions",
    title="World-writable permissions",
    category=RuleCategory.CONFIG,
    owasp=_OWASP_CONFIG,
    severity=Severity.MEDIUM,
    pattern=_CHMOD_777_RE,
    issue="`777` makes the path writable by every user on the host, so any process can replace the file.",
    suggested_fix="Grant the minimum: `os.chmod(path, 0o600)` for files, `0o700` for directories.",
)

_pattern_rule(
    rule_id="config/csrf-disabled",
    title="CSRF protection disabled",
    category=RuleCategory.CONFIG,
    owasp=_OWASP_CONFIG,
    severity=Severity.MEDIUM,
    pattern=_CSRF_OFF_RE,
    issue="CSRF protection is switched off for this view or app, so a third-party page can submit requests as the logged-in user.",
    suggested_fix="Keep CSRF on and exempt only token-authenticated API views with a documented reason.",
)

_pattern_rule(
    rule_id="config/allowed-hosts-wildcard",
    title="Wildcard allowed hosts",
    category=RuleCategory.CONFIG,
    owasp=_OWASP_CONFIG,
    severity=Severity.MEDIUM,
    pattern=_ALLOWED_HOSTS_WILDCARD_RE,
    issue="`ALLOWED_HOSTS = ['*']` disables host-header validation, which enables cache poisoning and password-reset link poisoning.",
    suggested_fix='List the hostnames you serve: `ALLOWED_HOSTS = ["app.example.com"]`.',
)

# --------------------------------------------------------------------------- #
# Reliability
# --------------------------------------------------------------------------- #


@_rule(
    "reliability/http-no-timeout",
    Severity.HIGH,
    "Network call without timeout",
    RuleCategory.RELIABILITY,
    _OWASP_DESIGN,
)
def _check_http_timeout(ctx: LineContext) -> RuleHit | None:
    """An HTTP call with no ``timeout`` argument."""
    text = ctx.scan_text
    if _HTTP_CALL_RE.search(text) is None or "timeout" in text:
        return None
    return RuleHit(
        issue=(
            "This HTTP call has no timeout, so a slow or hung peer blocks the caller indefinitely "
            "and takes the worker down with it."
        ),
        suggested_fix="Add an explicit timeout: `requests.get(url, timeout=10)`.",
    )


@_rule(
    "reliability/subprocess-no-check",
    Severity.LOW,
    "Subprocess without check",
    RuleCategory.RELIABILITY,
    _OWASP_DESIGN,
)
def _check_subprocess_check(ctx: LineContext) -> RuleHit | None:
    """``subprocess.run``/``call`` without ``check=True``."""
    text = ctx.scan_text
    if _SUBPROCESS_NO_CHECK_RE.search(text) is None or "check" in text:
        return None
    return RuleHit(
        issue=(
            "The subprocess exit status is ignored, so a failed command looks like success and the "
            "error surfaces far from its cause."
        ),
        suggested_fix='Fail fast: `subprocess.run(cmd, check=True, timeout=30)`.',
    )


@_rule(
    "quality/open-without-context-manager",
    Severity.LOW,
    "File opened without a context manager",
    RuleCategory.QUALITY,
    _OWASP_DESIGN,
)
def _check_open_without_with(ctx: LineContext) -> RuleHit | None:
    """``open(...)`` outside a ``with`` block."""
    text = ctx.scan_text
    if _OPEN_CALL_RE.search(text) is None or _WITH_OPEN_RE.search(text) is not None:
        return None
    if re.match(r"^\s*(?:return|await|with)\b", text) is not None:
        return None
    return RuleHit(
        issue=(
            "The file handle is opened without a `with` block, so it leaks on any exception between "
            "open and close."
        ),
        suggested_fix='Use a context manager: `with open(path, encoding="utf-8") as handle:\n    data = handle.read()`',
    )


# --------------------------------------------------------------------------- #
# Quality
# --------------------------------------------------------------------------- #


_pattern_rule(
    rule_id="quality/bare-except",
    title="Bare except",
    category=RuleCategory.QUALITY,
    owasp=_OWASP_LOGGING,
    severity=Severity.MEDIUM,
    pattern=_BARE_EXCEPT_RE,
    issue=(
        "A bare `except:` swallows every exception including `KeyboardInterrupt` and `SystemExit`, "
        "so real failures vanish and the process cannot be stopped cleanly."
    ),
    suggested_fix='Catch what you expect: `except (OSError, ValueError) as exc: logger.warning("read failed: %s", exc)`.',
)

_pattern_rule(
    rule_id="quality/except-pass",
    title="Swallowed exception",
    category=RuleCategory.QUALITY,
    owasp=_OWASP_LOGGING,
    severity=Severity.MEDIUM,
    pattern=_EXCEPT_PASS_RE,
    issue=(
        "The handler swallows the exception with `pass`, so a failure leaves no trace and the "
        "caller gets a wrong result instead of an error."
    ),
    suggested_fix=(
        'Log and re-raise or return a documented fallback: `except OSError as exc:\n'
        '    logger.warning("cache miss: %s", exc)\n    return None`'
    ),
)

_pattern_rule(
    rule_id="quality/mutable-default-arg",
    title="Mutable default argument",
    category=RuleCategory.QUALITY,
    owasp=_OWASP_DESIGN,
    severity=Severity.MEDIUM,
    pattern=_MUTABLE_DEFAULT_RE,
    issue=(
        "A mutable default is created once at import time, so every call shares and mutates the "
        "same list or dict."
    ),
    suggested_fix=(
        "Default to `None` and build inside the call: "
        "`def add(item: str, bucket: list[str] | None = None) -> None:\n"
        "    bucket = [] if bucket is None else bucket`"
    ),
)


@_rule(
    "quality/missing-type-hints",
    Severity.MEDIUM,
    "Missing type hints",
    RuleCategory.QUALITY,
    _OWASP_DESIGN,
)
def _check_missing_hints(ctx: LineContext) -> RuleHit | None:
    """A ``def`` without full parameter and return annotations."""
    match = _DEF_RE.match(ctx.scan_text)
    if match is None:
        return None
    name = match.group("name")
    params = match.group("params").strip()
    if name in _DUNDER_EXEMPT or params in ("", "self", "cls"):
        return None
    if ":" in params and match.group("ret") is not None:
        return None
    return RuleHit(
        issue=(
            f"`{name}` is a public function without full annotations, so callers and the reviewer "
            "cannot tell what goes in or what comes out."
        ),
        suggested_fix=f"Annotate it: `def {name}(value: str) -> str:` — every parameter and the return type.",
    )


# --------------------------------------------------------------------------- #
# Complexity
# --------------------------------------------------------------------------- #


@_rule(
    "complexity/branch-density",
    Severity.MEDIUM,
    "Branch-heavy function",
    RuleCategory.COMPLEXITY,
    _OWASP_DESIGN,
)
def _check_branch_density(ctx: LineContext) -> RuleHit | None:
    """Count decision points in a function whose ``def`` line is part of the change."""
    match = _DEF_RE.match(ctx.scan_text)
    if match is None:
        return None
    base = ctx.indent
    branches = 0
    for _lineno, text in ctx.added[ctx.index + 1 :]:
        if not text.strip():
            continue
        indent = len(text) - len(text.lstrip())
        if indent <= base:
            break
        branches += len(_BRANCH_RE.findall(text))
    if branches < _BRANCH_BUDGET:
        return None
    return RuleHit(
        issue=(
            f"`{match.group('name')}` carries {branches} decision points, so changing it safely "
            "means holding a dozen cases in your head while each test covers one path."
        ),
        suggested_fix=(
            "Extract the branch groups into named helpers (one per rule) and call them in sequence, "
            "or replace the chain with a dispatch dict keyed on the case."
        ),
    )


@_rule(
    "complexity/too-many-params",
    Severity.MEDIUM,
    "Too many parameters",
    RuleCategory.COMPLEXITY,
    _OWASP_DESIGN,
)
def _check_many_params(ctx: LineContext) -> RuleHit | None:
    """A function taking more than :data:`_MAX_PARAMS` parameters."""
    match = _DEF_RE.match(ctx.scan_text)
    if match is None:
        return None
    params = [part for part in match.group("params").split(",") if part.strip()]
    if len(params) <= _MAX_PARAMS:
        return None
    return RuleHit(
        issue=(
            f"`{match.group('name')}` takes {len(params)} parameters, so every call site must know "
            "the order and any new flag ripples through all of them."
        ),
        suggested_fix=(
            "Group the related values into a dataclass or Pydantic model and pass one object: "
            "`def run(config: RunConfig) -> None:`."
        ),
    )


@_rule(
    "complexity/deep-nesting",
    Severity.MEDIUM,
    "Deeply nested block",
    RuleCategory.COMPLEXITY,
    _OWASP_DESIGN,
)
def _check_deep_nesting(ctx: LineContext) -> RuleHit | None:
    """A branch or loop indented past :data:`_DEEP_INDENT` spaces."""
    if ctx.indent < _DEEP_INDENT or _DEEP_BRANCH_RE.search(ctx.text) is None:
        return None
    return RuleHit(
        issue=(
            f"The block sits at {ctx.indent} spaces of indentation, so the reader is four levels "
            "deep and the happy path is off-screen."
        ),
        suggested_fix=(
            "Invert the guard and return early, or extract the inner block into a named helper so "
            "the nesting resets."
        ),
    )


# --------------------------------------------------------------------------- #
# Style
# --------------------------------------------------------------------------- #


@_rule(
    "style/long-line",
    Severity.LOW,
    "Overlong line",
    RuleCategory.STYLE,
    _OWASP_DESIGN,
)
def _check_long_line(ctx: LineContext) -> RuleHit | None:
    """A line past :data:`_LONG_LINE` characters."""
    if len(ctx.text) <= _LONG_LINE:
        return None
    return RuleHit(
        issue=(
            f"The line is {len(ctx.text)} characters, past the {_LONG_LINE}-character budget, so it "
            "wraps in review and hides the right-hand side of the expression."
        ),
        suggested_fix="Break the expression inside parentheses, or extract a named intermediate value.",
    )


@_rule(
    "style/print-statement",
    Severity.LOW,
    "print() in library code",
    RuleCategory.STYLE,
    _OWASP_LOGGING,
)
def _check_print(ctx: LineContext) -> RuleHit | None:
    """``print`` outside a test file."""
    if ctx.is_test_file or _PRINT_RE.search(ctx.scan_text) is None:
        return None
    if "logger" in ctx.scan_text or "logging" in ctx.scan_text:
        return None
    return RuleHit(
        issue=(
            "`print` writes to stdout with no level, no timestamp and no way to switch it off, so it "
            "is lost in production and noisy in tests."
        ),
        suggested_fix='Use the module logger: `logger.info("message: %s", value)`.',
    )


_pattern_rule(
    rule_id="style/todo-comment",
    title="Unresolved TODO",
    category=RuleCategory.STYLE,
    owasp=_OWASP_DESIGN,
    severity=Severity.LOW,
    pattern=_TODO_RE,
    issue="An unresolved TODO ships with the change, so the debt is invisible to whoever picks the code up next.",
    suggested_fix="Raise it as a tracked issue and link it: `# TODO(#123): retry with backoff`.",
)

_pattern_rule(
    rule_id="style/wildcard-import",
    title="Wildcard import",
    category=RuleCategory.STYLE,
    owasp=_OWASP_DESIGN,
    severity=Severity.LOW,
    pattern=_WILDCARD_IMPORT_RE,
    issue=(
        "A wildcard import dumps unknown names into the module namespace, so shadowing and "
        "unused-import warnings become impossible to trace."
    ),
    suggested_fix="Import the names you use: `from app.models import Finding, Severity`.",
)


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #

RULES_BY_ID: dict[str, Rule] = {rule.id: rule for rule in RULES}
RULE_COUNT: int = len(RULES)


def _suppressed_ids(text: str) -> tuple[bool, set[str]]:
    """Parse a ``# noqa``/``# nosec`` marker.

    Args:
        text: The source line.

    Returns:
        ``(suppress_all, rule_ids)`` — ``(True, set())`` for a bare marker,
        ``(False, ids)`` for a targeted one, ``(False, set())`` when absent.
    """
    match = _NOQA_RE.search(text)
    if match is None:
        return False, set()
    raw = match.group("ids")
    if not raw:
        return True, set()
    body = raw.lstrip(":=").strip()
    ids = {part.strip() for part in re.split(r"[,\s]+", body) if part.strip()}
    return False, ids


def review_lines(
    path: str,
    lines: Sequence[tuple[int, str]],
    *,
    min_severity: Severity | None = None,
    categories: Iterable[RuleCategory] | None = None,
) -> list[Finding]:
    """Run every rule over the given lines of one file.

    Args:
        path: File path recorded on each finding.
        lines: ``(line_number, text)`` pairs — added lines only.
        min_severity: Drop findings below this severity when set.
        categories: Restrict to these rule categories when set.

    Returns:
        Findings in severity order, deduplicated per ``(file, line, rule)``.
    """
    added = tuple(lines)
    allowed_categories = set(categories) if categories is not None else None
    floor = min_severity.rank if min_severity is not None else -1
    findings: list[Finding] = []
    seen: set[tuple[str, int, str]] = set()

    for index, (lineno, text) in enumerate(added):
        context = LineContext(path=path, lineno=lineno, text=text, added=added, index=index)
        suppress_all, suppress_ids = _suppressed_ids(text)
        if suppress_all:
            continue
        for rule in RULES:
            if rule.severity.rank < floor:
                continue
            if allowed_categories is not None and rule.category not in allowed_categories:
                continue
            if rule.id in suppress_ids:
                continue
            hit = rule.check(context)
            if hit is None:
                continue
            key = (path, lineno, rule.id)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                Finding(
                    file=path,
                    line=str(lineno),
                    severity=rule.severity,
                    issue=f"{hit.issue} (rule: {rule.id})",
                    suggested_fix=hit.suggested_fix,
                )
            )

    return sort_findings(findings)


def review_diff(
    bundle: DiffBundle,
    *,
    min_severity: Severity | None = None,
    categories: Iterable[RuleCategory] | None = None,
) -> list[Finding]:
    """Run the rule engine over every added line of a parsed diff.

    Args:
        bundle: Parsed diff.
        min_severity: Drop findings below this severity when set.
        categories: Restrict to these rule categories when set.

    Returns:
        Findings across all files, CRITICAL first.
    """
    findings: list[Finding] = []
    for file in bundle.files:
        added = [
            (line.new_lineno, line.text)
            for hunk in file.hunks
            for line in hunk.lines
            if line.kind == "added" and line.new_lineno is not None
        ]
        if not added:
            continue
        findings.extend(
            review_lines(
                file.path,
                added,
                min_severity=min_severity,
                categories=categories,
            )
        )
    return sort_findings(findings)


def rule_ids() -> list[str]:
    """Every registered rule id, sorted — used by ``GET /rules`` and tests."""
    return sorted(RULES_BY_ID)


def rule_by_id(rule_id: str) -> Rule | None:
    """Look a rule up by id, or ``None`` when it is not registered."""
    return RULES_BY_ID.get(rule_id)
