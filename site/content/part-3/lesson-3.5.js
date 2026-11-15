/* 3.5 — monkeypatch and tmp_path
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "3.5",
  "part": 3,
  "part_title": "Testing with pytest",
  "title": "monkeypatch and tmp_path",
  "order": 305,
  "duration_min": 25,
  "concept_md": "### Two fixtures that replace setup code\n\n`monkeypatch` changes an attribute or an environment variable for the duration of one test and puts it back afterwards. `tmp_path` gives you a fresh directory that is deleted after the test. Between them they remove most of the reason to write a setup file.\n\n```python\nmonkeypatch.setenv(\"GITHUB_TOKEN\", \"ghp_test_token_value\")\nmonkeypatch.setattr(github_client, \"_build_github_client\", lambda token: client)\n```\n\nThose two lines are the real seam this repository tests through: a fake client installed where the real one would be built, and a token in the environment so the code path believes it is configured.\n\n### `setenv` and `delenv`\n\n`setenv` sets and restores; `delenv(..., raising=False)` removes one and restores it. The `raising=False` matters: without it, deleting a variable that is not set is an error, and a test that passes on a developer's machine fails in CI.\n\n### `setattr` on a module\n\nPatching the module attribute (`github_client._build_github_client`) rather than the imported name is what makes the seam testable: the code under test looks the name up at call time.\n\n### `tmp_path` is a Path\n\nIt is a real directory, unique per test, cleaned up afterwards. Write a diff, read it back, assert on the parse — no fixture file in the repository, no cleanup code.",
  "code_examples": [
    {
      "lang": "console",
      "caption": "Collection of the API tests, where the monkeypatch seams live",
      "code": "python -m pytest -q tests/test_api.py --collect-only | tail -1",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "collection needs the checkout and pytest; the browser has neither.",
      "expected_output": "47 tests collected in 3.02s",
      "id": "3.5-ex-0"
    }
  ],
  "quiz": [
    {
      "q": "What does `monkeypatch.setenv` guarantee?",
      "options": [
        "The variable stays set for the session",
        "It is set for this test and restored afterwards",
        "It writes a .env file",
        "It fails if the variable exists"
      ],
      "answer": 1,
      "why": "The restore is the point: a test cannot leak configuration into the next one."
    },
    {
      "q": "Why `delenv(\"X\", raising=False)`?",
      "options": [
        "It is shorter",
        "Because deleting an unset variable raises unless you say otherwise",
        "It makes the test faster",
        "It sets X to None"
      ],
      "answer": 1,
      "why": "Without it, a test that passes where the variable happens to be set fails in a clean environment."
    },
    {
      "q": "What is `tmp_path`?",
      "options": [
        "A string",
        "A `Path` to a per-test directory pytest removes afterwards",
        "The system temp directory, shared",
        "A fixture you must clean up yourself"
      ],
      "answer": 1,
      "why": "Per-test and self-cleaning, which is why a test can write a file without leaving one behind."
    }
  ],
  "try_it": {
    "prompt": "Set `LMSTUDIO_BASE_URL` to a fake URL with monkeypatch and read it back. Then delete it and read it again.",
    "starter": "def test_env(monkeypatch):\n    monkeypatch.setenv(\"LMSTUDIO_BASE_URL\", \"http://127.0.0.1:9/v1\")\n    import os\n    assert os.environ[\"LMSTUDIO_BASE_URL\"].startswith(\"http://127.0.0.1\")\n",
    "solution": "def test_env(monkeypatch):\n    import os\n\n    monkeypatch.setenv(\"LMSTUDIO_BASE_URL\", \"http://127.0.0.1:9/v1\")\n    assert os.environ[\"LMSTUDIO_BASE_URL\"].startswith(\"http://127.0.0.1\")\n\n    monkeypatch.delenv(\"LMSTUDIO_BASE_URL\")\n    assert \"LMSTUDIO_BASE_URL\" not in os.environ\n",
    "explanation": "Both assertions hold inside the test, and the variable is back to its original state afterwards — which is why the next test is unaffected."
  },
  "exercise": {
    "prompt": "Set `LMSTUDIO_BASE_URL` to a fake URL and assert that the provider reports itself unavailable. Read how the real tests do it first.",
    "hint": "A URL pointing at a closed port is available as configuration and unavailable in practice.",
    "solution": "```text\ndef test_provider_unavailable(monkeypatch):\n    monkeypatch.setenv(\"LMSTUDIO_BASE_URL\", \"http://127.0.0.1:9/v1\")\n    from app import openai_compat_provider as provider\n    assert provider.provider_available() is False\n```\nA port nobody listens on is the cheapest fake endpoint there is: no server to run, no\nnetwork access, and the check fails fast.",
    "explanation": "The point is the seam, not the port: the test never opens a connection because the availability check only looks at configuration."
  },
  "common_mistakes": [
    "Patching the imported name instead of the module attribute, so the code under test still calls the real function.",
    "Leaving a file in the repository from a test instead of using `tmp_path`.",
    "Setting an environment variable with `os.environ` directly, so it leaks into every later test."
  ],
  "project_links": [
    {
      "label": "monkeypatch.setenv in a real test",
      "path": "tests/test_api.py",
      "lines": "68-80"
    },
    {
      "label": "The fake-client seam the tests install",
      "path": "tests/test_cli.py",
      "lines": "50-62"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning/PACE.md — pacing the tracks",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/PACE.md"
    }
  ],
  "glossary_terms": [
    "monkeypatch — a fixture that patches and restores attributes or env vars",
    "seam — a place where a test can substitute a fake",
    "tmp_path — a per-test directory"
  ]
});
