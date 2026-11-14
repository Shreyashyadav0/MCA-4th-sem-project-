#!/usr/bin/env python3
"""The machine gate for the learning site.

Every wave runs this before it reports. Standard library only, because the site
has no build step and this script is a development tool, never something the
browser loads.

What it checks
--------------
 1. assets/manifest.js declares an ordered list of lesson paths.
 2. Each listed file exists and pushes exactly one object literal.
 3. The object matches the frozen schema: every key present, no unknown key,
    correct types, `expected_output` present exactly when `runnable` is false,
    and `try_it` / `exercise` carrying all four keys.
 4. `id` is "<part>.<n>", `order` is part*100 + n, ids and orders unique.
 5. `part_title` matches the PARTS array in assets/contracts.js.
 6. Every `project_links` path exists in the repository, and a `lines` range
    sits inside the file.
 7. No `concept_md` contains a raw HTML tag.
 8. Every file under content/ is listed in the manifest exactly once.
 9. index.html and lesson.html load the manifest's paths, in manifest order,
    after manifest.js — so the three lists cannot drift apart.
10. Each page carries exactly the ids the DOM contract names: none missing, and
    no extra id that would let a later wave invent a parallel hook.

Exit status is 0 with a one-line summary, or 1 with one line per failure.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
REPO = SITE.parent

MANIFEST = SITE / "assets" / "manifest.js"
CONTRACTS = SITE / "assets" / "contracts.js"
CONTENT = SITE / "content"
PAGES = ("index.html", "lesson.html")

# The frozen DOM contract: these ids, and only these, on each page.
REQUIRED_IDS = {
    "index.html": ["parts-list", "search-input", "search-results", "theme-toggle", "progress-total"],
    "lesson.html": [
        "lesson-title", "lesson-meta", "lesson-concept", "lesson-examples", "lesson-tryit",
        "lesson-exercise", "lesson-mistakes", "lesson-links", "lesson-glossary",
        "mark-done", "prev-link", "next-link", "lesson-nav",
    ],
}

LESSON_KEYS = {
    "id": str,
    "part": int,
    "part_title": str,
    "title": str,
    "order": int,
    "duration_min": int,
    "concept_md": str,
    "code_examples": list,
    "try_it": dict,
    "exercise": dict,
    "common_mistakes": list,
    "project_links": list,
    "learn_more": list,
    "glossary_terms": list,
}

EXAMPLE_KEYS = {"lang", "caption", "code", "runnable", "expected_output"}
# The two practice blocks are deliberately not identical: "try it" offers a
# starter file, "exercise" offers a hint. That asymmetry is in the frozen schema.
TRY_IT_KEYS = {"prompt", "starter", "solution", "explanation"}
EXERCISE_KEYS = {"prompt", "hint", "solution", "explanation"}
LINK_KEYS = {"label", "path", "lines"}
LEARN_KEYS = {"label", "href"}

RAW_HTML = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(\s[^<>]*)?/?>")
FENCED_CODE = re.compile(r"^```[^\n]*\n[\s\S]*?^```[^\n]*$", re.MULTILINE)
PART_ENTRY = re.compile(
    r"\{\s*n:\s*(\d+)\s*,\s*title:\s*\"([^\"]+)\"\s*,\s*lessons:\s*(\d+)\s*\}"
)
ID_PATTERN = re.compile(r"^(0|[1-9]\d*)\.([1-9]\d*)$")
LINES_PATTERN = re.compile(r"^(\d+)(?:\s*-\s*(\d+))?$")
PUSH_CALL = "window.LESSONS.push("


class Report:
    """Collects one line per failure, so a wave sees every problem at once."""

    def __init__(self) -> None:
        self.failures: list[str] = []

    def fail(self, where: str, message: str) -> None:
        self.failures.append(f"{where}: {message}")

    def expect(self, condition: bool, where: str, message: str) -> bool:
        if not condition:
            self.fail(where, message)
        return condition


def read_text(path: Path, report: Report) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        report.fail(relative(path), "cannot be decoded as UTF-8")
        return ""
    except OSError as error:
        report.fail(relative(path), f"cannot be read ({error})")
        return ""


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def parse_manifest(text: str, report: Report) -> list[str]:
    match = re.search(r"\[(?:\s*\"[^\"]*\"\s*,?)*\s*\]", text)
    if not match:
        report.fail("assets/manifest.js", "no array of lesson paths found")
        return []
    try:
        paths = json.loads(match.group(0))
    except json.JSONDecodeError as error:
        report.fail("assets/manifest.js", f"path array is not valid JSON ({error.msg})")
        return []
    return [str(item) for item in paths]


def parse_parts(text: str, report: Report) -> dict[int, dict[str, object]]:
    parts: dict[int, dict[str, object]] = {}
    for number, title, lessons in PART_ENTRY.findall(text):
        parts[int(number)] = {"title": title, "lessons": int(lessons)}
    if not parts:
        report.fail("assets/contracts.js", "no PARTS entries found")
    return parts


def code_mask(text: str) -> list[bool]:
    """True where a character is code, False inside a string or a comment.

    Needed because a lesson may quote the authoring pattern in its own prose,
    and the one real push() call has to be found without being fooled by it.
    """
    mask = [True] * len(text)
    i = 0
    length = len(text)
    while i < length:
        char = text[i]
        if char == '"':
            j = i + 1
            while j < length:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    j += 1
                    break
                j += 1
            for k in range(i, min(j, length)):
                mask[k] = False
            i = j
        elif char == "/" and text[i + 1 : i + 2] == "*":
            end = text.find("*/", i + 2)
            end = length if end == -1 else end + 2
            for k in range(i, end):
                mask[k] = False
            i = end
        elif char == "/" and text[i + 1 : i + 2] == "/":
            end = text.find("\n", i)
            end = length if end == -1 else end
            for k in range(i, end):
                mask[k] = False
            i = end
        else:
            i += 1
    return mask


def extract_object(text: str, where: str, report: Report) -> dict | None:
    """Pull the single object literal out of a lesson file.

    Brace matching skips string literals so a brace inside a caption cannot
    unbalance the scan. The literal must be JSON-compatible, which is the one
    authoring rule the content files carry.
    """
    if "window.LESSONS = window.LESSONS || [];" not in text:
        report.fail(where, "missing the 'window.LESSONS = window.LESSONS || [];' initialiser")
        return None

    mask = code_mask(text)
    calls = [
        index
        for index in range(len(text))
        if mask[index] and text.startswith(PUSH_CALL, index)
    ]
    if not calls:
        report.fail(where, f"no {PUSH_CALL} call found")
        return None
    if len(calls) > 1:
        report.fail(where, f"expected exactly one {PUSH_CALL} call, found {len(calls)}")
        return None

    start = calls[0] + len(PUSH_CALL)
    while start < len(text) and text[start] in " \t\r\n":
        start += 1
    if start >= len(text) or text[start] != "{":
        report.fail(where, "the pushed value is not an object literal")
        return None

    depth = 0
    in_string = False
    escaped = False
    end = -1
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end == -1:
        report.fail(where, "unbalanced braces in the pushed object")
        return None

    literal = text[start:end]
    try:
        parsed = json.loads(literal)
    except json.JSONDecodeError as error:
        report.fail(
            where,
            f"pushed object is not JSON-compatible ({error.msg} at line {error.lineno}, col {error.colno})",
        )
        return None
    if not isinstance(parsed, dict):
        report.fail(where, "the pushed value is not an object")
        return None
    return parsed


def check_type(value: object, expected: type) -> bool:
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, expected)


def check_schema(lesson: dict, where: str, report: Report) -> None:
    missing = sorted(set(LESSON_KEYS) - set(lesson))
    unknown = sorted(set(lesson) - set(LESSON_KEYS))
    for key in missing:
        report.fail(where, f"missing required key '{key}'")
    for key in unknown:
        report.fail(where, f"unknown key '{key}' — the schema is frozen")

    for key, expected in LESSON_KEYS.items():
        if key in lesson and not check_type(lesson[key], expected):
            report.fail(where, f"'{key}' must be {expected.__name__}")

    for key in ("id", "part_title", "title", "concept_md"):
        value = lesson.get(key)
        if isinstance(value, str) and not value.strip():
            report.fail(where, f"'{key}' is empty")

    examples = lesson.get("code_examples")
    if isinstance(examples, list):
        if not examples:
            report.fail(where, "code_examples is empty; a lesson needs at least one example")
        for index, example in enumerate(examples):
            label = f"{where} code_examples[{index}]"
            if not isinstance(example, dict):
                report.fail(label, "is not an object")
                continue
            for key in sorted(EXAMPLE_KEYS - {"expected_output"} - set(example)):
                report.fail(label, f"missing required key '{key}'")
            for key in sorted(set(example) - EXAMPLE_KEYS):
                report.fail(label, f"unknown key '{key}'")
            for key in ("lang", "caption", "code"):
                value = example.get(key)
                if isinstance(value, str) and not value.strip():
                    report.fail(label, f"'{key}' is empty")
                elif key in example and not isinstance(value, str):
                    report.fail(label, f"'{key}' must be str")
            runnable = example.get("runnable")
            if not isinstance(runnable, bool):
                report.fail(label, "'runnable' must be bool")
                continue
            has_output = "expected_output" in example
            if runnable and has_output:
                report.fail(
                    label,
                    "expected_output must be absent when runnable is true — a runnable "
                    "example's output is produced, not asserted",
                )
            if not runnable and not has_output:
                report.fail(label, "expected_output is required when runnable is false")
            if has_output and not isinstance(example["expected_output"], str):
                report.fail(label, "'expected_output' must be str")
            if has_output and isinstance(example["expected_output"], str) and not example["expected_output"].strip():
                report.fail(label, "'expected_output' is empty")
            if runnable and example.get("lang") != "python":
                report.fail(label, "only python examples may be runnable in the browser")

    for key, expected_keys in (("try_it", TRY_IT_KEYS), ("exercise", EXERCISE_KEYS)):
        block = lesson.get(key)
        if not isinstance(block, dict):
            continue
        label = f"{where} {key}"
        for missing_key in sorted(expected_keys - set(block)):
            report.fail(label, f"missing required key '{missing_key}'")
        for unknown_key in sorted(set(block) - expected_keys):
            report.fail(label, f"unknown key '{unknown_key}'")
        for sub_key, value in block.items():
            if not isinstance(value, str):
                report.fail(label, f"'{sub_key}' must be str")
        if isinstance(block.get("prompt"), str) and not block["prompt"].strip():
            report.fail(label, "'prompt' is empty")

    mistakes = lesson.get("common_mistakes")
    if isinstance(mistakes, list):
        if not mistakes:
            report.fail(where, "common_mistakes is empty")
        for index, item in enumerate(mistakes):
            if not isinstance(item, str) or not item.strip():
                report.fail(f"{where} common_mistakes[{index}]", "must be a non-empty string")

    glossary = lesson.get("glossary_terms")
    if isinstance(glossary, list):
        if not glossary:
            report.fail(where, "glossary_terms is empty")
        for index, item in enumerate(glossary):
            if not isinstance(item, str) or not item.strip():
                report.fail(f"{where} glossary_terms[{index}]", "must be a non-empty string")

    links = lesson.get("project_links")
    if isinstance(links, list):
        if not links:
            report.fail(where, "project_links is empty; every lesson points at code")
        for index, link in enumerate(links):
            label = f"{where} project_links[{index}]"
            if not isinstance(link, dict):
                report.fail(label, "is not an object")
                continue
            for key in sorted(LINK_KEYS - set(link)):
                report.fail(label, f"missing required key '{key}'")
            for key in sorted(set(link) - LINK_KEYS):
                report.fail(label, f"unknown key '{key}'")
            for key in ("label", "path", "lines"):
                if key in link and not isinstance(link[key], str):
                    report.fail(label, f"'{key}' must be str")
            if isinstance(link.get("path"), str) and not link["path"].strip():
                report.fail(label, "'path' is empty")
            if isinstance(link.get("label"), str) and not link["label"].strip():
                report.fail(label, "'label' is empty")

    learn = lesson.get("learn_more")
    if isinstance(learn, list):
        for index, link in enumerate(learn):
            label = f"{where} learn_more[{index}]"
            if not isinstance(link, dict):
                report.fail(label, "is not an object")
                continue
            for key in sorted(LEARN_KEYS - set(link)):
                report.fail(label, f"missing required key '{key}'")
            for key in sorted(set(link) - LEARN_KEYS):
                report.fail(label, f"unknown key '{key}'")
            for key in ("label", "href"):
                if key in link and (not isinstance(link[key], str) or not link[key].strip()):
                    report.fail(label, f"'{key}' must be a non-empty string")


def check_project_links(lesson: dict, where: str, report: Report) -> None:
    for link in lesson.get("project_links") or []:
        if not isinstance(link, dict):
            continue
        raw_path = link.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            continue
        target = REPO / raw_path
        try:
            target.resolve().relative_to(REPO.resolve())
        except ValueError:
            report.fail(where, f"project_links path escapes the repository: {raw_path}")
            continue
        if not target.is_file():
            report.fail(where, f"project_links path does not exist in the repo: {raw_path}")
            continue
        lines = link.get("lines")
        if not isinstance(lines, str) or not lines.strip():
            continue
        match = LINES_PATTERN.match(lines.strip())
        if not match:
            report.fail(where, f"project_links lines '{lines}' is not 'N' or 'N-M'")
            continue
        first = int(match.group(1))
        last = int(match.group(2) or first)
        total = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
        if first < 1 or last < first:
            report.fail(where, f"project_links lines '{lines}' is not an ascending range")
        elif last > total:
            report.fail(
                where,
                f"project_links lines '{lines}' runs past the end of {raw_path} ({total} lines)",
            )


def check_pages(paths: list[str], report: Report) -> None:
    expected = paths
    for page in PAGES:
        target = SITE / page
        text = read_text(target, report)
        if not text:
            continue
        found_ids = re.findall(r'\bid="([^"]+)"', text)
        wanted = REQUIRED_IDS.get(page, [])
        for missing in [name for name in wanted if name not in found_ids]:
            report.fail(page, f"missing contract id '#{missing}'")
        for extra in [name for name in found_ids if name not in wanted]:
            report.fail(page, f"unexpected id '#{extra}' — the DOM contract names exactly {len(wanted)}")
        listed = re.findall(r'<script\s+src="(content/[^"]+)"\s*>\s*</script>', text)
        if listed != expected:
            report.fail(
                page,
                f"lesson script tags do not match the manifest "
                f"(page: {listed or 'none'}; manifest: {expected or 'none'})",
            )
        if 'src="assets/manifest.js"' not in text:
            report.fail(page, "does not load assets/manifest.js")
        else:
            order = [
                re.search(r'src="assets/([a-z-]+\.js)"', tag).group(1)
                for tag in re.findall(r'<script\s+src="assets/[a-z-]+\.js"\s*>\s*</script>', text)
            ]
            wanted = ["contracts.js", "progress.js", "app.js", "search.js", "pyodide-loader.js", "manifest.js"]
            if order != wanted:
                report.fail(page, f"script order is {order}, expected {wanted}")


def main() -> int:
    report = Report()

    manifest_text = read_text(MANIFEST, report)
    contracts_text = read_text(CONTRACTS, report)
    paths = parse_manifest(manifest_text, report) if manifest_text else []
    parts = parse_parts(contracts_text, report) if contracts_text else {}

    if len(set(paths)) != len(paths):
        seen: set[str] = set()
        for path in paths:
            if path in seen:
                report.fail("assets/manifest.js", f"duplicate entry: {path}")
            seen.add(path)

    lessons: list[dict] = []
    lesson_where: dict[int, str] = {}
    for relative in paths:
        target = SITE / relative
        if not target.is_file():
            report.fail("assets/manifest.js", f"listed file does not exist: {relative}")
            continue
        text = read_text(target, report)
        if not text:
            continue
        lesson = extract_object(text, relative, report)
        if lesson is None:
            continue
        check_schema(lesson, relative, report)
        check_project_links(lesson, relative, report)

        concept = lesson.get("concept_md")
        if isinstance(concept, str):
            hits = RAW_HTML.findall(FENCED_CODE.sub(" ", concept))
            if hits:
                report.fail(relative, f"concept_md contains raw HTML: {', '.join(sorted(set(hits))[:4])}")

        lessons.append(lesson)
        lesson_where[id(lesson)] = relative

    seen_ids: dict[str, str] = {}
    seen_orders: dict[int, str] = {}
    covered_parts: set[int] = set()

    for lesson in lessons:
        where = lesson_where.get(id(lesson), "lesson")
        identifier = lesson.get("id")
        part = lesson.get("part")
        order = lesson.get("order")

        if not isinstance(identifier, str) or not ID_PATTERN.match(identifier):
            report.fail(where, f"id '{identifier}' is not '<part>.<n>'")
        else:
            id_part, id_number = (int(group) for group in ID_PATTERN.match(identifier).groups())
            if isinstance(part, int) and id_part != part:
                report.fail(where, f"id '{identifier}' disagrees with part {part}")
            if isinstance(part, int) and isinstance(order, int):
                expected_order = part * 100 + id_number
                if order != expected_order:
                    report.fail(where, f"order {order} is not part*100 + n ({expected_order})")
            if identifier in seen_ids:
                report.fail(where, f"duplicate id '{identifier}' (also in {seen_ids[identifier]})")
            else:
                seen_ids[identifier] = where

        if isinstance(order, int):
            if order in seen_orders:
                report.fail(where, f"duplicate order {order} (also in {seen_orders[order]})")
            else:
                seen_orders[order] = where

        if isinstance(part, int):
            covered_parts.add(part)
            known = parts.get(part)
            if known is None:
                report.fail(where, f"part {part} is not in CONTRACTS.PARTS")
            elif lesson.get("part_title") != known["title"]:
                report.fail(
                    where,
                    f"part_title '{lesson.get('part_title')}' does not match PARTS[{part}] "
                    f"('{known['title']}')",
                )

    on_disk = sorted(
        str(path.relative_to(SITE)).replace("\\", "/") for path in CONTENT.rglob("*") if path.is_file()
    ) if CONTENT.is_dir() else []
    for found in on_disk:
        if found not in paths:
            report.fail("assets/manifest.js", f"content file is not listed: {found}")

    check_pages(paths, report)

    if report.failures:
        for line in report.failures:
            print(f"FAIL {line}")
        print(f"FAIL {len(report.failures)} problem(s) in {len(paths)} manifest entr(ies)")
        return 1

    print(
        "OK lessons={lessons} parts_covered={parts_covered} manifest_entries={entries} "
        "ids={ids}".format(
            lessons=len(lessons),
            parts_covered=len(covered_parts),
            entries=len(paths),
            ids=",".join(lesson["id"] for lesson in lessons),
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
