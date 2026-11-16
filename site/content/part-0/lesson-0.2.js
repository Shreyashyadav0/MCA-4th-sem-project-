/* 0.2 — How to use this site
 * Generated as a JSON-compatible object literal so the validator can parse it.
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "0.2",
  "part": 0,
  "part_title": "Orientation",
  "title": "How to use this site",
  "order": 2,
  "duration_min": 10,
  "concept_md": "### The shape of the site\n\nEvery page carries the same left sidebar: thirteen parts, each collapsible, each showing how many of its lessons exist and how many you have done. A tick means done. Parts that are dimmed have no lessons yet — they are planned, not locked, and the sidebar says so rather than hiding them.\n\n### Three ways to see code\n\n| Button | What it does | When it appears |\n|---|---|---|\n| **Run** | executes the snippet in this page | `browser` and `browser-pkg` examples |\n| **Copy code** | puts the snippet on your clipboard | every example |\n| **Run in terminal** | the panel that shows the command and what it prints | `terminal` examples, and any example when the runtime cannot load |\n\nThe tiers are honest. An example that needs a shell, a network socket or a package the browser does not have is marked `terminal`: it shows the command and its expected output instead of a Run button, because a button that cannot work teaches the wrong thing.\n\n### Finding things\n\nOn the parts page, press `/` to jump to the search box. It searches lesson titles and concept text — not code, so a hit means \"this lesson explains it\". Escape clears the box.\n\n### Progress and theme\n\n**Mark done** at the foot of each lesson writes to your browser's `localStorage`; nothing leaves your machine and there is no account. The same store remembers light or dark. Both survive a reload.\n\n### Where the answers are\n\nEvery lesson ends with **In the repository** — real paths and line ranges — and **Glossary**. The exercise and quiz answers are behind a disclosure so you can try first.\n\nThis site is a learning aid. For what the code does, `HANDOFF.md` is the ledger: if another document disagrees with it, the ledger wins. `docs/learning/` is the curriculum this site follows, and it is not always in step with the code — one of its pages still quotes an older test count, which is why every number here is checked against the suite instead.",
  "code_examples": [
    {
      "id": "0.2-ex-0",
      "lang": "console",
      "caption": "What a literal grep looks like — the site's search does something narrower",
      "code": "grep -rl \"f-string\" site/content/part-1/",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "it reads files from the repository on disk; a browser page has no shell and no checkout.",
      "expected_output": "site/content/part-1/lesson-1.1.js"
    }
  ],
  "quiz": [
    {
      "q": "You open an example and find no Run button. What does that tell you?",
      "options": [
        "The example is marked terminal: it needs something a browser does not have",
        "The page failed to render and should be reloaded once",
        "Your browser is too old to run WebAssembly in a page",
        "The example was written before the runner existed at all, so it cannot run"
      ],
      "answer": 0,
      "why": "The tier is declared in the lesson data; a terminal example shows its command and expected output instead of a Run button."
    },
    {
      "q": "What does the search box index?",
      "options": [
        "The contents of docs/learning/",
        "Every line of code in the repository",
        "Lesson titles and concept text",
        "The git history"
      ],
      "answer": 2,
      "why": "Code is deliberately excluded, so a hit means the lesson explains the term rather than the word appearing in a snippet."
    },
    {
      "q": "Where is your progress stored?",
      "options": [
        "In the repository",
        "On a server",
        "In the lesson file, beside the example it belongs to",
        "In this browser's localStorage"
      ],
      "answer": 3,
      "why": "Progress lives in this browser only: two keys, one per concern, so a later wave can change the progress format without losing the theme choice."
    }
  ],
  "try_it": {
    "prompt": "Press `/` and search for `provider`. Then search for `zzzz`. Read the two results screens and note the difference: one lists lessons, the other explains the empty state instead of leaving a blank box.",
    "starter": "# The two keys this site writes, and the shape of the progress value.\nPROGRESS_KEY = \"ai-reviewer-learning-progress-v1\"\nTHEME_KEY = \"ai-reviewer-learning-theme-v1\"\nprint({\"version\": 1, \"done\": {\"0.2\": True}})\n",
    "solution": "```text\n`provider` matches thirty lessons — 0.1, 0.4, 1.1, 1.3 and 1.12 — because each one names the provider or its precedence somewhere in its concept text. `zzzz` matches nothing, and the page says so and suggests browsing the parts instead of showing an empty list.\n```",
    "explanation": "Search runs entirely in the page over `window.LESSONS`, so it works with the network off. That is also why it can only see what the page has loaded."
  },
  "exercise": {
    "prompt": "Mark this lesson done, reload the page, and confirm the tick and the part count are still there. Then name the storage key the site used.",
    "hint": "Your browser's developer tools show localStorage per origin; on file:// it is under the page's own origin.",
    "solution": "```text\nThe tick survives because progress is stored under `ai-reviewer-learning-progress-v1`, as `{\"version\": 1, \"done\": {\"0.2\": true}}`. The theme uses a separate key, `ai-reviewer-learning-theme-v1`.\n```",
    "explanation": "Two keys, both versioned: a later wave can change the format without crashing on data written by an older one."
  },
  "common_mistakes": [
    "Looking for a Run button on a terminal example and concluding the site is broken. The panel underneath says why it cannot run here.",
    "Expecting search to find code. It indexes titles and concept text only, so a term that appears only inside a snippet will not match.",
    "Assuming progress syncs between browsers. It is localStorage: same browser, same machine, or nothing."
  ],
  "project_links": [
    {
      "label": "How the site is laid out, and what degrades offline",
      "path": "site/README.md",
      "lines": "1-187"
    },
    {
      "label": "The curriculum this site follows",
      "path": "docs/learning/README.md",
      "lines": "1-21"
    }
  ],
  "learn_more": [
    {
      "label": "docs/learning — the seven-track curriculum",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docs/learning/README.md"
    }
  ],
  "glossary_terms": [
    "tier — browser, browser-pkg or terminal; what an example needs in order to run",
    "localStorage — the browser's per-origin key/value store; where progress and theme live",
    "terminal panel — the fallback that shows a command and its expected output"
  ]
});
