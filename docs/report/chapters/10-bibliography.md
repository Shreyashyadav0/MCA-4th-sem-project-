# 10 Bibliography

One style is used throughout: author or organisation, title, publisher or URL, year
where the source states one, and the date on which the source was last accessed.
Where a document is published only on the web, the URL is the locator and no page
numbers are given, because a page number in a document that has no printed
pagination is a citation that cannot be checked. The note after each entry says
where in this report the source is relied on.

All twenty-three entries end with an access date. Eight of them name a dated
source — the OWASP Top 10 for 2021, the Python 3.12 documentation, RFC 2104 and
the six peer-reviewed papers — and carry its year; the remaining fifteen are
living web documents whose pages state no publication date, so they give none
rather than a guessed one. An organisation stands in the author position wherever
no individual is named, and every entry names the publisher, the venue or the URL
in that order.

## 10.1 Institutional sources

[1] Indira Gandhi National Open University, School of Computer and Information
Sciences, *Project Guidelines for MCSP-232 (MCA Project)*. New Delhi: IGNOU.
Available: https://www.ignou.ac.in/ — accessed 14 November 2026.
*Relied on for the prescribed structure of the project report, the synopsis order
followed in the proposal package, and the proforma for approval of the project
proposal.*

[2] Indira Gandhi National Open University, *MCA (Revised) Programme Guide*. New
Delhi: IGNOU. Available: https://www.ignou.ac.in/ — accessed 14 November 2026.
*Relied on for the programme and course codes used on the title page, the credit
weight of the project course, and the submission requirements for the synopsis and
the final report.*

## 10.2 Standards, specifications and reference documentation

[3] OWASP Foundation, *OWASP Top 10:2021 — The Ten Most Critical Web Application
Security Risks*. 2021. Available: https://owasp.org/Top10/ — accessed 14 November
2026.
*The taxonomy onto which every rule in the registry is mapped; each rule records its
`A0n:2021` identifier.*

[4] Python Software Foundation, *Python 3.12 Documentation*. 2024. Available:
https://docs.python.org/3.12/ — accessed 14 November 2026.
*The language reference for the interpreter the project is pinned to, including the
`re`, `hmac`, `hashlib` and `dataclasses` modules used throughout.*

[5] S. Ramírez, *FastAPI Documentation*. Available: https://fastapi.tiangolo.com/ —
accessed 14 November 2026.
*The framework reference for the HTTP surface: request models, dependency
injection, response models and the generated OpenAPI schema at `/docs`.*

[6] Pydantic Services Inc., *Pydantic v2 Documentation*, version 2.14.3 (the pin in
`requirements.txt`). Available: https://docs.pydantic.dev/latest/ — accessed
14 November 2026.
*The reference for the strict models of Chapter 4: `extra="forbid"`, frozen models,
field and model validators, computed fields, and `pydantic-settings` for the
configuration boundary.*

[7] SQLAlchemy, *SQLAlchemy 2.0 Documentation*. Available:
https://docs.sqlalchemy.org/en/20/ — accessed 14 November 2026.
*The reference for the persistence design of Appendix B: the dialect-neutral column
types, primary and foreign key declaration, and the mapping of the review entities
onto tables.*

[8] OpenAI, *API Reference*. Available: https://platform.openai.com/docs/api-reference
— accessed 14 November 2026.
*The chat-completions request and response shape that the single adapter speaks, and
the structured-output (`response_format`) parameter whose rejection by an endpoint
triggers the repair retry.*

[9] LM Studio, *OpenAI Compatibility Endpoints*. Available:
https://lmstudio.ai/docs/developer/openai-compat — accessed 14 November 2026.
*The local inference path: the `/v1` base URL, the port, and the model identifier
discovery call that the setup instructions in Appendix A depend on.*

[10] GitHub, *REST API — Pull request reviews*. Available:
https://docs.github.com/en/rest/pulls/reviews — accessed 14 November 2026.
*The endpoint contract for creating a review and for the comment objects the
publishing layer builds.*

[11] GitHub, *REST API — Issue comments*. Available:
https://docs.github.com/en/rest/issues/comments — accessed 14 November 2026.
*The listing endpoint used to read existing comment bodies before posting, which is
how the idempotency marker is detected.*

[12] GitHub, *Webhook events and payloads*. Available:
https://docs.github.com/en/webhooks/webhook-events-and-payloads — accessed
14 November 2026.
*The `pull_request` event payload, the action names the system reviews, and the
delivery headers it reads.*

[13] GitHub, *Validating webhook deliveries*. Available:
https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries —
accessed 14 November 2026.
*The `X-Hub-Signature-256` scheme: HMAC-SHA256 over the raw body with the shared
secret, and the requirement for a constant-time comparison.*

[14] J. MacFarlane, ed., *CommonMark Specification*, version 0.31.2, section "Code
spans". Available: https://spec.commonmark.org/0.31.2/#code-spans — accessed
14 November 2026.
*The rule that governs how a suggested fix containing backticks is rendered inside a
generated comment, which is why the renderer normalises fence length rather than
escaping.*

[15] Sarvam AI, *API Reference — Introduction*. Available:
https://docs.sarvam.ai/api-reference/introduction — accessed 14 November 2026.
*The hosted endpoint the `sarvam` provider points at, and the chat-completions
contract it shares with the local endpoint.*

[16] H. Krawczyk, M. Bellare and R. Canetti, "HMAC: Keyed-Hashing for Message
Authentication", RFC 2104, IETF, 1997. Available:
https://www.rfc-editor.org/rfc/rfc2104 — accessed 14 November 2026.
*The construction behind the webhook signature check and the idempotency
fingerprint.*

[17] Git project, *git-diff(1) — Git Documentation*. Available:
https://git-scm.com/docs/git-diff — accessed 14 November 2026.
*The unified-diff format the parser consumes: file headers, hunk headers with old and
new ranges, and the three change markers.*

[18] pytest project, *pytest Documentation*. Available: https://docs.pytest.org/ —
accessed 14 November 2026.
*The testing framework, parametrisation and the skip marker used for the one live
smoke test.*

## 10.3 Peer-reviewed and technical literature

[19] C. Sadowski, E. Aftandilian, A. Eagle, L. Miller-Cushon and C. Jaspan, "Lessons
from Building Static Analysis Tools at Google", *Communications of the ACM*, vol. 61,
no. 4, pp. 58–66, 2018. Available: https://dl.acm.org/doi/10.1145/3188720 — accessed
14 November 2026.
*Relied on in Chapter 2 for the finding that a static analysis tool is adopted only
when its results arrive inside the developer's existing workflow and its
false-positive rate is low enough to be tolerated; both conclusions shaped the
decision to comment on pull requests rather than publish a dashboard, and to treat
precision as a first-class metric.*

[20] H. Pearce, B. Ahmad, B. Dolan-Gavitt and R. Karri, "Asleep at the Keyboard?
Assessing the Security of GitHub Copilot's Code Contributions", in *Proceedings of
the 43rd IEEE Symposium on Security and Privacy*, 2022. Available:
https://arxiv.org/abs/2108.09293 — accessed 14 November 2026.
*Relied on in Chapter 2 for the evidence that model-generated code is frequently
insecure, which is the argument for keeping a deterministic security layer rather
than delegating detection to a model.*

[21] N. Perry, M. Srivastava, D. Kumar and D. Boneh, "Do Users Write More Insecure
Code with AI Assistants?", in *Proceedings of the 2023 ACM SIGSAC Conference on
Computer and Communications Security*, 2023. Available:
https://arxiv.org/abs/2211.03622 — accessed 14 November 2026.
*Relied on in Chapter 2 for the user-study finding that assistance is associated both
with less secure code and with greater confidence that the code is secure, which
motivates a reviewer whose findings are attributable to a named rule.*

[22] Z. Li, S. Lu, D. Guo, N. Duan, S. Jannu, G. Jenks, D. Majumder, J. Green,
A. Svyatkovskiy, S. Fu and N. Sundaresan, "Automating Code Review Activities by
Large-Scale Pre-training", in *Proceedings of the 30th ACM Joint European Software
Engineering Conference and Symposium on the Foundations of Software Engineering
(ESEC/FSE 2022)*, pp. 1035–1047, 2022. Available: https://arxiv.org/abs/2203.09095 —
accessed 14 November 2026.
*Relied on in Chapter 2 for the three code-review tasks a pre-trained model can be
asked to perform — change-quality estimation, comment generation and code refinement
— and for the observation that comment generation remains the hardest of the three,
which is why this project asks a model for structured findings rather than prose.*

[23] R. Tufano, S. Masiero, A. Mastropaolo, L. Pascarella, D. Poshyvanyk and
G. Bavota, "Using Pre-Trained Models to Boost Code Review Automation", in
*Proceedings of the 44th International Conference on Software Engineering (ICSE
2022)*, pp. 2291–2302, 2022. Available: https://arxiv.org/abs/2201.06850 — accessed
14 November 2026.
*Relied on in Chapter 2 for the reported gap between what code-review automation
achieves on curated data and what is required for practical deployment, which is the
reason this report states a methodology and withholds numbers until a labelled
dataset exists.*

## 10.4 Note on what is not cited

Three kinds of source are deliberately absent. Vendor marketing pages are not cited,
because a product's own description of its accuracy is not evidence. Blog posts about
prompt engineering are not cited, because the claims in this report that touch model
behaviour are drawn from the peer-reviewed work above or from measurements made on
this system. And no DOI or page range is given for a document whose pagination could
not be confirmed: where the source is a web page, the entry gives the URL and the
access date and stops there. No year is invented for an undated page either — a
plausible-looking year on a living document is worse than an honest blank, because
it cannot be checked by the reader.
