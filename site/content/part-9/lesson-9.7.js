/* 9.7 — Docker: the pinned environment as an image
 * One lesson per file. Do not add a second push() here.
 */
window.LESSONS = window.LESSONS || [];
window.LESSONS.push({
  "id": "9.7",
  "part": 9,
  "part_title": "Configuration and offline-first",
  "title": "Docker: the pinned environment as an image",
  "order": 907,
  "duration_min": 30,
  "concept_md": "### Two stages\n\nThe `Dockerfile` builds in one stage and runs in another. The builder installs from the lock into a virtual environment; the runtime copies that environment and nothing else. The compiler toolchain never reaches the final image.\n\n### What the runtime stage guarantees\n\nIt runs as `USER 10001:10001` — not root — and starts `uvicorn app.main:app` on port 8000. A container that runs as root turns any file-write bug into a host-write bug, which is why the non-root user is in the image rather than in a deployment note.\n\n### The compose file and the local model\n\n`docker-compose.yml` defines one service, `app`. Its comments document the LM Studio passthrough: on Desktop, `host.docker.internal` resolves and `LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1` works. On Linux it does not resolve by default, so the file shows the `host.docker.internal:host-gateway` mapping that makes the same value work.\n\n### Why the passthrough is documented rather than automated\n\nBecause it cannot be automated portably. A mapping that works on Desktop and a mapping that works on Linux are different, and guessing wrong produces a container that cannot reach a model with no error that explains why.",
  "code_examples": [
    {
      "id": "9.7-ex-0",
      "lang": "console",
      "caption": "The two stages, the user and the command",
      "code": "grep -n \"^FROM\\|^USER\\|^CMD\" Dockerfile",
      "runnable": false,
      "run_tier": "terminal",
      "why_not": "the browser runner has Python but no shell, so this command cannot run there; it needs a checkout on disk.",
      "expected_output": "22:FROM python:3.12-slim AS builder\n46:FROM python:3.12-slim AS runtime\n79:USER 10001:10001\n90:CMD [\"uvicorn\", \"app.main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]"
    }
  ],
  "quiz": [
    {
      "q": "What does the runtime stage copy?",
      "options": [
        "The built environment only",
        "The whole build context",
        "The compiler toolchain too",
        "The source, not the env"
      ],
      "answer": 0,
      "why": "The builder's virtual environment is copied and the toolchain is left behind, which keeps the image small."
    },
    {
      "q": "Why does the image set a non-root user?",
      "options": [
        "A write bug stays in the container",
        "Root is slower at startup",
        "Docker requires a numeric uid",
        "The lock installs as that same uid"
      ],
      "answer": 0,
      "why": "Running as root turns a file-write bug into a host-write bug, so the user belongs in the image."
    },
    {
      "q": "Why is the LM Studio mapping documented, not automated?",
      "options": [
        "Desktop and Linux need different maps",
        "Compose cannot set environment",
        "The mapping needs a paid Docker tier plan",
        "LM Studio refuses all containers"
      ],
      "answer": 0,
      "why": "A mapping that works on one host does not work on the other, and a wrong guess fails without explaining."
    }
  ],
  "try_it": {
    "prompt": "Print the base image, the user and the command the runtime stage uses.",
    "starter": "",
    "solution": "```console\n$ grep -n '^FROM\\|^USER\\|^CMD' Dockerfile\n```",
    "explanation": "Two `FROM` lines, one `USER`, one `CMD` — the whole runtime contract in four lines."
  },
  "exercise": {
    "prompt": "How many build stages does the Dockerfile have, and which line starts the second?",
    "hint": "Count the `FROM` instructions.",
    "solution": "```console\n$ grep -c '^FROM' Dockerfile\n2\n$ grep -n 'AS runtime' Dockerfile\n```",
    "explanation": "Two stages: a builder and a runtime, so the toolchain never reaches the final image."
  },
  "common_mistakes": [
    "Copying the whole build context into the runtime stage.",
    "Running the container as root because it is simpler.",
    "Assuming `host.docker.internal` resolves on Linux by default."
  ],
  "project_links": [
    {
      "label": "The builder stage",
      "path": "Dockerfile",
      "lines": "22"
    },
    {
      "label": "The runtime stage",
      "path": "Dockerfile",
      "lines": "46"
    },
    {
      "label": "The non-root user and the command",
      "path": "Dockerfile",
      "lines": "79-90"
    }
  ],
  "learn_more": [
    {
      "label": "Dockerfile — two stages",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/Dockerfile"
    },
    {
      "label": "docker-compose.yml — the local passthrough",
      "href": "https://github.com/Shreyashyadav0/ai-code-reviewer/blob/main/docker-compose.yml"
    }
  ],
  "glossary_terms": [
    "stage — one FROM block in a multi-stage build",
    "runtime image — the final image that ships",
    "passthrough — reaching a host service from a container"
  ]
});
