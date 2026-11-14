# benchmarks/ — frozen interface (Wave 3)

Locked shapes. Agents implement against these names; do not rename or reorder fields.

## matching.py
    CATEGORY_EQUIVALENCE: dict[str, frozenset[str]]
    @dataclass(frozen=True) MatchResult:
        matched: tuple[Match, ...]
        false_positives: tuple[ExpectedFinding, ...]
        false_negatives: tuple[ExpectedFinding, ...]
        true_negatives: int
        per_category: dict[str, CategoryScore]
    @dataclass(frozen=True) Match:
        expected: ExpectedFinding; actual: Finding; overlap: int
    @dataclass(frozen=True) CategoryScore:
        tp: int; fp: int; fn: int
    def match_sample(expected: Sample, findings: Sequence[Finding]) -> MatchResult

Matching rule (locked): same file AND overlapping line ranges AND
(category equal OR in CATEGORY_EQUIVALENCE). One-to-one, greedy, largest overlap
first; ties broken by (file, expected line start, actual line start) — deterministic,
documented as a limitation.

## metrics.py
    @dataclass(frozen=True) ModeMetrics:
        precision: float; recall: float; f1: float; fpr: float
        tp: int; fp: int; fn: int; tn: int
        per_category: dict[str, CategoryScore]
        latency_p50: float; latency_p95: float
    def compute_metrics(results: Sequence[MatchResult], latencies: Sequence[float]) -> ModeMetrics

## loader.py
    @dataclass(frozen=True) ExpectedFinding:
        file: str; line_start: int; line_end: int; category: str; severity: str
    @dataclass(frozen=True) Sample:
        id: str; diff_text: str; expected: tuple[ExpectedFinding, ...]; meta: dict
    def load_dataset(root: Path) -> list[Sample]

## runner.py
    @dataclass(frozen=True) ModeResult:
        mode: str; metrics: ModeMetrics; samples: int; skipped: int; note: str
    def run_mode(mode: str, samples: Sequence[Sample], *, dataset_root: Path) -> ModeResult
    def run_all(modes: Sequence[str], *, dataset_root: Path) -> dict[str, ModeResult]

## report.py
    def write_csv(results: dict[str, ModeResult], out: Path) -> Path
    def write_summary_json(results: dict[str, ModeResult], out: Path) -> Path
    def write_summary_md(results: dict[str, ModeResult], out: Path) -> Path
    def write_chart(results: dict[str, ModeResult], out: Path) -> Path

## eval.py
    python -m benchmarks.eval --modes rules local merged --dataset benchmarks/golden --out benchmarks/out
