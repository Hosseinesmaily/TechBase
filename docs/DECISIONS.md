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
| A7 | Entity identity vs market SKU. | `Entity` = the thing (Ryzen 7 7800X3D, DDR5); `Product` = a SKU that sells it. Specs/benchmarks/pages attach to the Entity, price & stock to the Product. | Spec's D4. Prices change hourly, identity does not. |
| A8 | Where do component specs live? | `ComponentSpec.common` (JSONB, indexed) for rule-relevant fields (socket, memory_type, tdp, wattage, length) + `ComponentSpec.extra` (JSONB) for everything else. | Spec's D5: a new component category is seed data, not a migration. |
| A9 | Currency for prices. | `Product.currency = "IRT"` (تومان), prices as `Decimal(14,2)`. | The retailer prices in tomans; a currency field keeps the door open for IRR/USD without a migration. |
| A10 | Persian title on entities. | `Entity.title` = canonical latin name (used for matching/slugs), `Entity.title_fa` = Persian display name, `aliases` = extra names for the auto-linker. | Keeps slug/URLs clean while the UI and the assistant speak Persian. |
| A11 | How are compatibility rules stored? | `CompatibilityRule` rows hold code/severity/params/enabled; the *logic* is a Python class per rule in `apps/compat/engine.py` (a `Rule` protocol + registry). | Spec's D6. Data is tunable without a deploy; logic stays unit-testable and explainable. |
| A12 | Where do per-rule tunables live? | On the rule instance (`rule.params`), not in the shared context — the DB row overrides the class default. | A global merged params dict let one rule's setting leak into another. |
| A13 | Connector matching for the PSU rule. | Normalise connector strings to *kinds* (`8-pin`, `12vhpwr`, …) so `"2x 8-pin PCIe"` satisfies a GPU asking for `8-pin`, and `12vhpwr` ≡ `12V-2x6`. | Plain string comparison reported false "missing connector" warnings. |
| A14 | Frontend → API transport. | Same-origin: a Nitro catch-all route `server/api/[...path].ts` proxies `/api/**` to Django at request time (`API_INTERNAL_BASE` read from the environment). | No CORS. A `routeRules.proxy` string was baked at build time and `/**` did not match the nested `/api/v1/...` paths. |
| A15 | Are the seeded prebuilts validated? | Yes — a test asserts every seeded prebuilt passes the compatibility engine, and that known-bad pairings are blocked. | The demo data is the assistant's evidence; a self-contradicting demo would make the product look broken. |
| A16 | Inventory source. | `InventoryAdapter` Protocol with a `MockInventoryAdapter` (seeded RNG, ±5% price drift) and a `CSVInventoryAdapter`; a Celery task applies records. Unknown SKUs are reported, never created. | Spec's D15. The catalog stays editor-controlled. |
| A17 | Admin language. | `LocaleMiddleware` + `LANGUAGES = [fa, en]` + Persian `verbose_name` on every model and app label. | Django's default offers ~90 locales and the UI followed the browser, so the editorial tool was English. Persian-first is a product requirement, not only a front-end one. |
| A18 | Search endpoint shape. | `GET /api/v1/search/` returns `{query, total, products: {count, results}, entities: {count, results}}` in one response; `/autocomplete/` returns `{query, suggestions: [{text, slug}]}`. | One request renders the whole results page; the shape is fixed now so Phase 3's hybrid backend is a drop-in replacement. |
| A19 | Wagtail version and admin mount. | Wagtail 6.4, editorial admin at `/cms/`, public pages at `/wiki/` (served by Wagtail for the canonical URLs) while Nuxt renders the actual site. | Wagtail 6.4 is the last line before the 7.x API changes; the admin and the public site are separate concerns (DECISIONS A2). |
| A20 | How a page is "published". | `first_published_at is not None` — **not** Wagtail's `live` flag, which is True for a freshly created page that was never published. | The `live` flag alone listed drafts as public content. |
| A21 | Auto-linker matching. | Aho-Corasick over title + Persian title + aliases; word-boundary aware; **longest match wins** (a shorter name inside a longer one is dropped); first mention per section. Brand names are excluded. | "RTX 4060" also matched "4060" → two links for one mention. Brand names appear in nearly every paragraph, so linking them is noise. |
| A22 | What counts as an orphan page. | A published page that **nothing links to** (its bound entity has no inbound links), not a page with no outgoing links. | The first implementation had it backwards. |
| A23 | The wiki section's place in the tree. | Under the **site root** (the page the Wagtail site is rooted at), not under the tree root. `manage.py configure_site` sets hostname, port and root page. | Under the tree root, Wagtail treats the pages as belonging to no site: the admin shows "Exploring" and the public URLs 404. |
| A24 | Where the guide's recommended products are written. | Before `save_revision().publish()` for the scalar fields, and again after for the many-to-many. | Setting them after publishing left the published revision with the old, empty values — the guide 404'd in the API. |
| A25 | Normalisation at index time vs query time. | The **same** function at both ends; `normalize_for_index` and `normalize_for_query` are named separately but are deliberately identical. | If the two differ, a document indexed as "می‌شود" is not found by a query for "می شود" and recall collapses without any error. |
| A26 | Search when Meilisearch is down. | Fall back to the PostgreSQL backend and report `backend: "postgres"` in the response. | A search that fails because a container is slow is worse than a less forgiving one. The response says which backend answered, so the degradation is visible. |
| A27 | Fusion method. | Reciprocal Rank Fusion (k=60) over the Meilisearch and PostgreSQL rankings. | Parameter-free and needs no score calibration between two different scales. |
| A28 | Autocomplete matching. | The prefix may match the start of a name **or of any word in it**. | Meilisearch's "prefix" strategy works this way; matching only the title's start meant "RTX" suggested nothing. |
| A29 | Empty query. | Returns no hits (a browse, not a search). | The PostgreSQL backend treated an empty filter as "no filter" and returned the whole catalog. |
| A30 | Embedding provider by default. | `hash` — a deterministic, dependency-free local fallback. `bge-m3`/`e5` are opt-in (they need `sentence-transformers` and a model download). | The whole RAG pipeline — chunking, retrieval, the guardrails, the evaluation harness, the chat endpoint — must be runnable and testable with no model download. |
| A31 | What the retrieval searches in. | The chunk's text **plus** the page slug, the entity's latin names and aliases, and the spec values. | The prose is Persian; an English question could never match it, and a value like "AM5" lives in the specs table, not in a sentence. |
| A32 | Lexical matching. | An **OR** over the query's tokens, scored by coverage, with a stopword list in both languages and a floor for a single weak match. | Requiring every token made natural questions match nothing. |
| A33 | What counts as a fabrication. | A number in a sentence that mentions a price or a stock count, when that number is not in the tool results. Numbers without such a cue (a core count, a year, a resolution) are left alone. | The guardrail must catch a made-up price without flagging every number in the answer. |
| A34 | Citation markers in the number check. | `[1]` is removed before the numbers are extracted. | It is a reference, not a price — treating it as one rejected every cited answer. |
| A35 | Persian output on the console. | `apps/core/console.py` replaces what the terminal cannot encode. | Windows' console defaults to cp1252 and the management commands crashed with a UnicodeEncodeError. |
| A36 | What the evaluation measures. | The pipeline — retrieval, citations, guardrails — against a **scripted** model, not a model's wording. | The number has to be comparable between runs; a real model is measured by the same harness once a key is configured. |
| A37 | How the query is understood. | The model returns strict JSON, and the heuristics (regex + stopwords, Persian-digit aware) are the fallback without a model *and* the safety net when the JSON is unusable. | The stack has to work with no API key, and a malformed model response must not break the turn. |
| A38 | Who decides which tools run. | The **plan is derived from the understanding**, not from the model. | The tools are deterministic; letting the model choose them would make the price and the compatibility verdict model-dependent — exactly what the spec forbids. |
| A39 | When to ask a clarifying question. | When the budget or the use case is missing — and then exactly **one** question, and the turn stops (no tool runs). | The spec allows one question. Running the tools anyway would answer the wrong question. |
| A40 | Where the compatibility verdict comes from. | Always the rule engine, quoted verbatim by the assistant. | A model-invented verdict would be a compatibility decision made by a language model. |
