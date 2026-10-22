# SECURITY — the review and what it changed

A review of the whole stack, what was found, and what was done about it. The
findings are ordered by severity.

## The threats this system actually has

The assistant reads editor-controlled wiki content and answers questions about
prices and compatibility. The realistic risks are:

1. **A model inventing a price or a compatibility verdict.** The user pays
   for a part that does not fit, or loses money on a wrong price.
2. **A prompt injection through the wiki content** — a page that tells the
   model to ignore its instructions and state a false price.
3. **A denial of wallet** — the assistant costs money per turn, so it must be
   rate limited.
4. **Personal data in the logs** — the user's question may carry a name or a
   phone number.
5. **The ordinary web risks** — injection, CSRF, secret leakage.

## 1. Invented facts — the critical one

**Mitigation** (`apps/ai/guardrails.py`):

- Every price and stock number in the answer is checked against the values the
  tools returned. A number that is not in that list is a fabrication, and the
  answer is replaced with an explicit "I cannot confirm this".
- The digit sets are folded before the comparison, so "۳۲۹۰۰۰۰۰" and
  "32900000.00" are the same number, and the citation marker "[1]" is not
  mistaken for a price.
- A number without a price or a stock cue is left alone — a core count or a
  year is not a shop fact.
- **The compatibility verdict is never the model's.** It comes from the
  deterministic rule engine and is quoted verbatim.
- The tool *plan* is derived from the query understanding, not from the model,
  so a model cannot decide to skip the catalog lookup.

**Tests**: `apps/ai/tests/test_guardrails.py` (23) and
`apps/ai/tests/test_agentic.py` — including a canary price that must never
appear in the answer.

## 2. Prompt injection through the content

**Mitigation**:

- Retrieved content is **stripped of instruction-like lines** before it
  reaches the prompt — English and Persian patterns ("ignore all previous
  instructions", "نادیده بگیر", a `system:` role tag, a closing role tag).
- The content is wrapped in `<<<CONTEXT>>>` delimiters, and the system prompt
  says explicitly that the content is data, not instructions.
- The wiki is editor-controlled: a page can only be published by staff, and
  the content is not user input.

**Tests**: `apps/ai/tests/test_guardrails.py::TestSanitizeRetrieved` — an
injected instruction must not survive.

**Limit, stated plainly**: a line that does not look like an instruction but
reads like one would survive the filter. The defence in depth is that the
guardrail still checks the *facts* after the model has answered: a successful
injection that changes the price would still be caught.

## 3. Denial of wallet

**Mitigation** (`apps/core/throttling.py`):

- The rate limiter runs as a middleware in front of the whole API, with a
  per-minute limit per identity (the user id, or the IP address).
- The assistant has its own, much tighter scope than the read-only
  endpoints (`RATE_LIMIT_CHAT`, default 20/min against 120/min).
- Redis is the primary counter; the database is the fallback, so the limit
  holds even when Redis is down.
- The staff group is not limited.
- Over the limit, the answer is a 429 with `Retry-After`.

**Tests**: `apps/ai/tests/test_cache_and_limits.py::TestRateLimiting`.

## 4. Personal data in the logs

**Mitigation** (`apps/core/privacy.py`):

- A logging filter removes the email addresses, the phone numbers, the
  national IDs, the card numbers and the IP addresses from every log line.
- The raw question stays in the database (the editorial team can see it in
  the query log) but it never reaches a log file.

**Limit, stated plainly**: this is a safety net for the obvious shapes, not a
guarantee. A user who types an unusual identifier in a question may still put
it in the database.

## 5. The ordinary web risks

| Risk | What was done |
|---|---|
| SQL injection | Everything goes through the ORM. The raw SQL is limited to the pgvector check, which takes no user input. |
| XSS | The API returns JSON; the Nuxt app escapes by default and there is no `v-html` anywhere. The retrieved content is inserted as text, never as HTML. |
| CSRF | Django's CSRF middleware is on; the admin and the write endpoints require it. The read-only API is public and safe. |
| Secret leakage | No secret is in the repository. `.env` is ignored, `.env.example` holds placeholders, and `compose.prod.yaml` refuses to start without the real values. The production settings refuse a dev secret key. |
| Open redirect | There is no redirect endpoint. |
| Dependency risk | The pinned ranges are in `backend/requirements/*.txt`; the audit runs in CI. |
| Clickjacking | `X-Frame-Options: DENY` in the production settings. |
| HSTS / secure cookies | Enabled in the production settings. |
| SSRF | The backend fetches from Meilisearch and the LLM API, both of which are configured by the operator — the user's input never becomes a URL. |

## 6. The rate limiter and the cache

The semantic cache stores the question's embedding and the answer. A cached
answer is served only when:

- the turn ended in a good answer (the guardrails passed), and
- it was not a clarifying question, and
- the similarity is at least 0.95.

A cache hit still returns the citations of the original turn, so the answer
remains auditable.

## 7. What is not covered

- **Authentication.** There are no user accounts in v1: the reads are public
  and the writes are staff-only through the Django/Wagtail admin. If the
  product needs customer accounts, that is a Phase 7 decision.
- **The editor's own permissions.** Wagtail's groups are used as they come;
  the `register_permissions` hook adds an explicit "publish wiki pages"
  permission for the editors.
- **Content moderation.** The wiki is editor-controlled, so a page is reviewed
  by a person before it is published — but there is no automated check that a
  page does not contradict the catalog. The link-integrity job reports broken
  links, not contradictions.
