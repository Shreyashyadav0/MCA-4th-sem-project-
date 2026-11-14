# Track 6 — app/engine.py answer key

**1. `SARVAM_API_KEY` and `LMSTUDIO_BASE_URL` are both set and the request is
`auto`. Which provider runs, and which line decides it?**

Sarvam runs. In the `auto` branch the sarvam config is built and checked first,
and only when it is `None` is the local config consulted, so "both set" resolves to
the hosted provider; the reason string returned is `SARVAM_API_KEY is set; sarvam
selected`.
Check: `app/engine.py:230`.

**2. `REVIEW_MODE=mock` is set and the caller passes `--provider local` with
`LMSTUDIO_BASE_URL` configured. What runs, and why does the flag win?**

The local endpoint runs. The `REVIEW_MODE=mock` short-circuit sits inside the
`auto` branch only, so it never applies to an explicit request; the forced-`local`
branch then builds the config and returns `provider forced to local`. The rule is
that a flag on the command line or in a request body beats an environment default.
Check: `app/engine.py:228`, `app/engine.py:263`.

**3. `select_provider` raises in exactly one situation and degrades in every
other. Name both, and say what `review()` does with the exception.**

It raises `ValueError` only for an unknown provider *name*, and returns a mock
selection — with a reason naming the missing variable — for a forced provider whose
configuration is absent, including the `sarvam` and `local` cases. The distinction
is deliberate: no environment change makes `--provider gpt4` meaningful, while a
missing key is a state a user can fix. `review()` catches that `ValueError` and
degrades anyway, because on the API path the name arrives from a query string and
must not become a 500.
Check: `app/engine.py:276`, `app/engine.py:355`.

**4. Why does `config_for_local` require `LMSTUDIO_API_KEY` to be non-blank when LM
Studio ignores the value entirely?**

Because the OpenAI SDK insists on a credential even when the server ignores it, so
`Settings` defaults the field to the placeholder `lm-studio`; requiring it non-blank
keeps the "is this configured?" test uniform with the sarvam path and with
`_non_blank`. In practice the field is therefore always populated, and the check
only fires when a user has deliberately blanked it.
Check: `app/engine.py:146`, `app/config.py:59`.

**5. You are asked to add a fourth provider. What must change?**

`PROVIDERS` gains the name in the right precedence position, a `config_for_*`
builder is added, and `select_provider` gains an `auto` branch and a forced branch
with its own missing-variable reason. Outside this module the name has to be added
to the `--provider` choices and to the three `Literal` declarations the API
validates against, which is exactly the coupling the "one selector" design leaves
behind — precedence lives in one file, the set of legal names is published to the
surfaces.
Check: `app/engine.py:64`, `app/cli.py:92`, `app/main.py:178`.
