# DECISIONS — assumption → decision → rationale

Append-only ADR-lite log. Newest entries at the bottom of each section.

## Product / Language

| # | Assumption / Question | Decision | Rationale |
|---|---|---|---|
| P1 | Which language is primary? | **Persian (fa) is the product language**: UI default, seed content, chat answers, rule messages. English (en) supported as secondary locale. | User approval given 2026-10-03: "approval … zaban farsi bashe". |
| P2 | Public user accounts needed in v1? | No. Reads public, writes staff-only, feedback anonymous. | Not in scope; avoids auth surface area. |
| P3 | LLM API keys in dev? | Keys optional (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY` empty by default). A `FakeLLM` adapter keeps the stack runnable with zero keys. | `docker compose up` must work from a clean clone. |

## Platform / Tooling

| # | Question | Decision | Rationale |
|---|---|---|---|
| T1 | Host has no Docker (Windows dev box); spec requires `docker compose up`. | Compose is the primary path (CI + prod + spec DoD). Makefile targets accept `LOCAL=1` to run the same commands on the host interpreter for machines without Docker. | Keeps DoD intact while still allowing verification on this host. |
| T2 | Host Python is 3.13, container is 3.12 (spec). | Pin container/CI to Python 3.12; code targets 3.12+ and is verified locally on 3.13. | No 3.12 interpreter on host; Django 5.2 supports both. |
| T3 | Dependency pinning style. | Floor + major ceiling ranges in `requirements/*.txt` (e.g. `Django>=5.2,<5.3`), no lockfile in v1. | Boring, avoids bit-rot of exact pins; strict lock can come in Phase 6. |
| T4 | DB for local tests without Docker. | `DB_ENGINE=postgres` (default) or `DB_ENGINE=sqlite`. pytest uses `config.settings.test` which defaults to in-memory SQLite; set `TEST_DB_ENGINE=postgres` to exercise pgvector tests later. | Lets lint/tests run on hosts without Postgres; pgvector-specific tests stay tagged. |

## Architecture

| # | Question | Decision | Rationale |
|---|---|---|---|
| A1 | Install Wagtail in Phase 0? | **Defer to Phase 2.** Phase 0 ships DRF + spectacular only. | Keeps `migrate` trivial at the scaffolding gate; Wagtail adds many migrations & settings. |
| A2 | Where do Wagtail pages live vs the frontend? | Wagtail serves the editorial backend (`/cms/` admin); the Nuxt SSR app renders all public pages via DRF. | Spec fixes a separate Nuxt frontend; avoids running two SSR stacks. |
| A3 | SSE transport for chat (Phase 4). | Django `StreamingHttpResponse` behind gunicorn/uvicorn; Nuxt uses `fetch` + `ReadableStream`. | No new dependency; works in Docker/nginx. |
| A4 | Meilisearch client library. | Official `meilisearch` Python client, wrapped behind `search/backends.py` interface. | Swap-able later; official client is maintained. |
| A5 | Empty app stubs for `seed_demo` / `reindex`. | Create `apps/catalog` + `apps/search` in Phase 0 with management-command stubs that exit 0 and say which phase implements them. | Makefile contract (`make seed`, `make reindex`) holds from day one. |
| A6 | Structured logging. | stdlib `logging` + JSON formatter when `LOG_FORMAT=json`, plain console otherwise. | Zero new deps for the common dev case. |
