# PLAN — TechBase: Interactive Knowledge Base + Dynamic Wiki + Agentic RAG

Status: **AWAITING APPROVAL** (Phase 0 not started)

---

## 1. Goals & Scope Recap

- Editor-controlled Persian-first wiki (Wagtail) with dense internal linking.
- Product catalog with deterministic compatibility rules (no LLM in compat decisions).
- Hybrid search (Meilisearch lexical + pgvector semantic, fused with RRF).
- Conversational Q&A assistant (Agentic RAG) with strict guardrails: prices/stock/specs
  only from tool results, citations for every wiki claim, one clarifying question max.
- Everything runs via `docker compose up` from a clean clone.

## 2. Repository Structure

```
TechBase/
├── docs/
│   ├── PLAN.md                  # this file
│   ├── PROGRESS.md              # phase-by-phase log (updated at each phase gate)
│   ├── DECISIONS.md             # ADR-lite: assumption → decision → rationale
│   ├── ARCHITECTURE.md          # diagram + module map (Phase 7)
│   └── RUNBOOKS.md              # ops runbooks (Phase 7)
├── evals/
│   └── golden_set.jsonl         # 30 FA + 10 EN retrieval/answer cases (Phase 4)
├── backend/
│   ├── manage.py
│   ├── pyproject.toml           # ruff + mypy + pytest config, deps
│   ├── requirements/            # base.txt, dev.txt, prod.txt (pip-tools style)
│   ├── config/                  # Django project
│   │   ├── settings/{base,dev,prod}.py
│   │   ├── urls.py, celery.py, asgi.py, wsgi.py
│   ├── apps/
│   │   ├── core/                # shared: TimeStampedModel, slug utils, pagination,
│   │   │                        #   structured logging, health checks
│   │   ├── catalog/             # Brand, Category, Entity, Product, ComponentSpec
│   │   ├── compat/              # CompatibilityRule engine + serializers
│   │   ├── benchmarks/          # Benchmark
│   │   ├── content/             # Wagtail page types + StreamField blocks + workflow
│   │   ├── linking/             # EntityLink, auto-linker, backlinks, hovercard, jobs
│   │   ├── search/              # Meilisearch client, Persian normalizer, hybrid API
│   │   ├── ai/                  # ContentChunk, embeddings, retrieval, tools,
│   │   │                        #   orchestrator, LLM adapters, cache, evals
│   │   ├── integrations/        # inventory/price adapter interface + mock/CSV + Celery
│   │   └── analytics/           # QueryLog, Feedback, unanswered report
│   └── tests/                   # cross-app tests (factories in each app's tests/)
├── frontend/
│   ├── nuxt.config.ts           # SSR, i18n(fa/en), RTL, sitemap/SEO
│   ├── tailwind.config.ts
│   ├── app/
│   │   ├── assets/css/main.css  # design tokens, RTL primitives
│   │   ├── components/          # ProductCard, CitationLink, HoverCard, ChatStream...
│   │   ├── composables/         # useApi, useChat (SSE), useRtl
│   │   ├── layouts/  pages/  middleware/
│   └── tests/
├── docker/
│   ├── Dockerfile.backend       # python:3.12-slim, gunicorn/uvicorn
│   ├── Dockerfile.frontend      # node:20, dev & prod stages
│   └── initdb/                  # pgvector extension bootstrap SQL
├── compose.yaml                 # postgres, redis, meilisearch, backend, celery-worker,
│                                # celery-beat, frontend
├── Makefile                     # setup run test lint migrate seed reindex eval
├── .env.example                 # NO real secrets, ever
├── .github/workflows/ci.yaml    # lint + pytest + frontend typecheck/test + build smoke
├── .editorconfig  .gitignore  .pre-commit-config.yaml
└── README.md                    # quickstart, demo path, make targets
```

## 3. Data Model (Mermaid)

```mermaid
erDiagram
    Brand ||--o{ Entity : "belongs to"
    Category ||--o{ Entity : "categorized as"
    Category ||--o{ Category : "parent"

    Entity {
        uuid id PK
        string type "cpu|gpu|ram|motherboard|psu|case|cooler|prebuilt|concept|game"
        string slug UK
        string title
        jsonb aliases "for auto-linker"
        string status "draft|red|published"   "red = no page yet"
        datetime review_by                    "stale-content tracking"
    }

    Entity ||--o| Product : "market SKU(s)"
    Entity ||--o{ ComponentSpec : "specs"
    Entity ||--o{ EntityLink : "outgoing"
    Entity ||--o{ EntityLink : "incoming (backlinks)"
    Entity ||--o{ Benchmark : "benchmarks"
    Entity ||--o{ ContentChunk : "chunks from wiki"

    Product {
        uuid id PK
        string sku UK
        string title
        decimal price
        int stock
        datetime updated_at "shown on cards as 'last updated'"
        string source "seed|mock_erp|csv"
        bool is_active
    }

    ComponentSpec {
        uuid id PK
        uuid entity_id FK
        string category
        jsonb common   "hot columns: socket, ram_type, tdp, wattage, clearance..."
        jsonb extra    "category-specific, no migration needed"
    }

    CompatibilityRule {
        uuid id PK
        string code UK "SOCKET_MATCH, RAM_TYPE_MATCH, PSU_WATTAGE, GPU_CLEARANCE, COOLER_SUPPORT"
        string category_a
        string category_b
        jsonb params    "multipliers, margins, message templates (FA/EN)"
        bool enabled
        int severity    "block|warn|info"
    }

    Benchmark {
        uuid id PK
        uuid component_id FK
        string game
        string resolution "1080p|1440p|4K"
        string preset
        int avg_fps
        int p1_low
        jsonb test_rig
        date tested_at
    }

    EntityLink {
        uuid id PK
        uuid source_id FK
        uuid target_id FK
        string link_type "mentions|compatible_with|alternative_to|benchmarked_in|part_of"
        string section_path "heading / heading > subheading"
        bool auto_created
        bool target_exists "false => red link"
        string text
        UK(source_id, target_id, section_path, link_type)
    }

    WikiPage --|| Entity : "wagtail page bound to entity (1:1 or null)"
    WikiPage {
        # Wagtail Page base: title, slug, depth, path, live, latest_revision
        string page_type "ComponentPage|BuyerGuidePage|ConceptPage"
        uuid entity_id FK "nullable for standalone guides"
        string language "fa|en"
        datetime review_by
        string workflow_state "draft|review|published"
    }

    ContentChunk {
        uuid id PK
        uuid page_id FK
        uuid entity_id FK "nullable"
        string section_path
        int heading_level
        text content
        vector embedding "pgvector, 1024-dim (bge-m3) or 384/512 (e5)"
        tsvector content_tsv "optional, PG lexical fallback"
        datetime indexed_at
    }

    QueryLog {
        uuid id PK
        text raw_query
        jsonb understood "QU JSON"
        jsonb tool_calls
        jsonb citations
        string language
        int latency_ms
        jsonb metrics "cache_hit, tokens, retrieval scores"
        datetime created_at
    }

    Feedback {
        uuid id PK
        uuid query_log_id FK
        int thumbs "-1|1"
        text comment
        datetime created_at
    }
```

Embedding dimension is a **config setting** (`AI_EMBEDDING_DIM`); migration creates the
vector column with that dim so swapping bge-m3 ↔ multilingual-e5 does not require code change
(decision logged in DECISIONS.md).

## 4. API Surface (v1)

Base: `/api/v1/` — all JSON, DRF, token/session auth (write endpoints staff-only; reads public).
OpenAPI via `drf-spectacular` at `/api/schema/` + `/api/docs/`.

| Area | Method & Path | Notes |
|---|---|---|
| catalog | `GET /catalog/entities/` | filter `type,brand,category,search`; paginate |
| | `GET /catalog/entities/{slug}/` | detail + specs + related links |
| | `GET /catalog/products/` | filter `category,brand,min_price,max_price,in_stock` |
| | `GET /catalog/products/{sku}/` | detail; includes `updated_at` |
| | `GET /catalog/brands/`, `/catalog/categories/` | facet sources |
| compat | `POST /compat/check/` | `{parts:[entity_slug...]}` → per-pair verdicts, severity, human message |
| | `GET /compat/rules/` | staff; rule introspection (transparency) |
| benchmarks | `GET /benchmarks/` | filter `component,game,resolution` |
| linking | `GET /linking/hovercard/?entity=` | title, price, stock, 3 key specs, page URL |
| | `GET /linking/backlinks/{slug}/` | precomputed |
| | `GET /linking/redlinks/` | editorial backlog (staff) |
| search | `GET /search/?q=&type=&brand=&...` | hybrid RRF; `facets`, `took_ms` |
| | `GET /search/autocomplete?q=` | prefix, min 2 chars |
| ai | `POST /ai/chat/` | SSE stream: `token`, `cards`, `citations`, `done`, `error` |
| | `POST /ai/chat/feedback/` | thumbs per message |
| | `POST /ai/compare/` | product comparison payload (Phase 5) |
| analytics | `GET /analytics/unanswered/` | staff; zero-hit queries |
| integrations | `POST /integrations/sync/` | staff; trigger mock/CSV sync |
| system | `GET /health/`, `GET /health/ready/` | liveness/readiness (DB, Redis, Meili) |

Frontend (Nuxt SSR) routes: `/`, `/search`, `/wiki/{slug}`, `/entity/{slug}`,
`/chat`, `/compare/{a}/{b}`, `/build` (Phase 7 configurator), `/sitemap.xml`, `robots.txt`.

## 5. Key Technical Decisions & Trade-offs

| # | Decision | Trade-off / Why |
|---|---|---|
| D1 | **Single Postgres = source of truth + vector store (pgvector)** | Avoids vector-DB sync bugs and extra infra in v1; HNSW index is fine at <1M chunks. Revisit if >500k chunks or multi-tenant. |
| D2 | **Meilisearch for lexical/facets/autocomplete; PG fallback if down** | Meili gives Persian-friendly tokenization + typo tolerance out of box; keeping search behind an interface allows swap to ES/Typesense later. |
| D3 | **RRF fusion (k=60) over Meili rank + pgvector distance** | Parameter-free, robust, no training needed. Reranker is an optional interface (`NullReranker` default) so v1 has no extra model dependency. |
| D4 | **Entity as the central linkable object; Product = market SKU** | Specs/benchmarks/pages attach to Entity (stable identity), price/stock to Product (volatile). One Entity may have several Products over time. |
| D5 | **ComponentSpec = hot columns in JSONB + `extra` JSONB, GIN indexes** | New category = seed data, not migration. Hot fields (socket, ram_type) get GIN + expression indexes for the rule engine. |
| D6 | **Compat engine = pure Python rule registry, no LLM, no DSL in v1** | Deterministic, testable, explainable messages. Rules are DB rows for enable/disable + params, code for logic. A generic DSL is premature. |
| D7 | **Auto-linker = Aho-Corasick over title+aliases, first mention per section only** | O(n) over page text, no LLM cost; "first mention per section" keeps density readable. Longer aliases matched first; word-boundary aware for Latin, dictionary-aware for Persian. |
| D8 | **Wagtail owns editorial HTML pages; DRF owns catalog JSON** | Two concerns, one DB. `WikiPage.entity` FK bridges them so hovercards/redlinks work across both. |
| D9 | **Chunking = heading-based (section_path preserved)** | Citation links map straight to heading anchors; better retrieval precision than fixed-token windows. Target ~500–800 tokens with overlap on long sections. |
| D10 | **Provider-agnostic LLM adapter (Protocol), route by task** | Cheap model → query understanding (strict JSON); strong model → final answer. Adapters: Anthropic, OpenAI-compatible (vLLM/Ollama). No vendor lock-in. |
| D11 | **Retrieved content treated as untrusted data** | Stripped of instruction-like lines, wrapped in delimiters, system prompt forbids following embedded instructions. Guardrail tests inject fake instructions into chunks. |
| D12 | **Semantic cache: normalized-query embedding + cosine ≥ 0.95** | Cuts cost/latency for repeated questions; stores answer + citations keyed by locale. Bypassed when `missing_info` non-empty. |
| D13 | **SSE (not WebSockets) for chat streaming** | One-directional token flow, plays well with Nuxt SSR + proxies, simpler in Docker/nginx. |
| D14 | **Persian normalization as a shared, pure function used by index *and* query** | ی/ي، ک/ك، ZWNJ→space (index-time) / ZWNJ-aware (query-time), Persian-Arabic-Indic ↔ Latin digit folding, diacritic strip. Must be symmetric or recall collapses. |
| D15 | **Mock/CSV inventory adapter behind `InventoryAdapter` Protocol** | Real ERP integration is out of scope for v1; interface + Celery beat job prove the pipeline. |
| D16 | **Tests: pytest + factory_boy for business logic; Playwright later if needed** | Spec requires tests for compat rules, linking engine, RAG tools, guardrails. No browser tests in v1 unless time allows. |
| D17 | **Windows host, Linux containers** | All commands run through Docker via Makefile so dev/CI/prod match; `make` targets use `docker compose run` to avoid host Python/Node version drift. |

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Persian search recall poor (tokenizer, ZWNJ, mixed digits) | High — core UX | Shared normalizer, golden-set retrieval eval (`make eval`) from Phase 4, Meili custom separators, per-language index settings |
| Embedding model download big (bge-m3 ~2.2GB) → slow first boot | Med | Model baked into backend image stage *or* volume-cached; config allows smaller `multilingual-e5-small` for CI/dev |
| Wagtail ↔ DRF slug conflicts / duplicate URLs | Med | Namespaced routes (`/wiki/` pages vs `/api/v1/catalog/`), slug uniqueness enforced on `Entity` |
| Auto-linker over-links (noise) or under-links | Med | First-mention-per-section rule, alias precedence, disable-list, tests with realistic Persian text |
| LLM fabricates price/stock | **Critical** | Guardrail tests: mock tools with canary values; assert canary appears verbatim & no off-tool numbers; answer built only from tool outputs |
| Prompt injection via wiki content | **Critical** | Untrusted-content wrapper, instruction stripping, tests with injected "ignore previous instructions" chunks |
| RRF weights wrong → bad rankings | Med | Golden set hit-rate metric; tune `k` and weight in Phase 4, keep in settings |
| Celery/Redis/Meili flakiness in `docker compose up` | Med | Healthchecks + `depends_on: condition: service_healthy`, readiness endpoint, retries in adapters |
| Scope creep across 8 phases | High | Phase gates: test+lint+docs+commit+STOP; anything non-blocking → DECISIONS.md |
| No real ERP data | Low | Mock/CSV adapter is explicitly in-scope; documented as placeholder |

## 7. Phase Breakdown (complexity / effort)

| Phase | Scope | Est. effort | Complexity | Deliverables |
|---|---|---|---|---|
| **0 Scaffolding** | Repo, compose (pg+pgvector, redis, meili, django, celery, nuxt), settings split, CI, lint/test, Makefile, docs | 0.5–1 day | Low-Med | `docker compose up` boots all services, empty tests pass, CI green |
| **1 Data foundation** | Models+migrations (catalog, compat, benchmarks), admin, seed (~realistic FA/EN demo data, 10 prebuilt PCs), mock sync job, REST+filters+pagination, OpenAPI | 1.5–2 days | Med | Seeded DB, `/api/v1/*` + schema, sync job runs |
| **2 Wiki core** | Wagtail page types + StreamField + workflow + `review_by`, linking engine (auto-link, backlinks, redlinks, hovercard, integrity job), Nuxt RTL design system, product cards, breadcrumbs, SEO/sitemap/JSON-LD, ~15 demo pages | 2–3 days | **High** | Browseable wiki with live hovercards & red links |
| **3 Search** | Meili indexing pipeline, Persian normalizer, facets, autocomplete, search UI | 1–1.5 days | Med | Hybrid-ready lexical search works for FA queries |
| **4 Basic RAG MVP** | Chunking+embeddings+pgvector, hybrid RRF, chat SSE endpoint + UI, citations, eval harness + golden set (30 FA + 10 EN) + `make eval` | 2–2.5 days | **High** | Cited, streaming answers; measurable hit-rate |
| **5 Agentic layer** | Query understanding, 4 tools, clarifying question, product cards in chat, comparison view, guardrail tests | 1.5–2 days | **High** | Full Agentic RAG flow with tests proving guardrails |
| **6 Hardening** | Semantic cache, rate limiting, tracing (Langfuse optional), security review, load-test script, prod compose + deploy docs | 1.5–2 days | Med-High | Prod-ready profile, security checklist |
| **7 Polish** | PC Configurator, price-alert stub, README, architecture diagram, runbooks | 1–1.5 days | Med | Ship-ready |

**Total: ~11–15 focused days.** Each phase ends with: tests green, lint clean,
docs updated, Conventional Commit, **STOP for approval**.

## 8. Phase Gate Checklist (every phase)

1. `make lint` and `make test` pass (backend + frontend).
2. `docker compose up` works from clean state; README demo path still accurate.
3. No secrets committed (`.env.example` only).
4. `docs/PROGRESS.md` updated (done / open questions / next).
5. `docs/DECISIONS.md` updated for any assumption made.
6. Commit with Conventional Commits message → report → **wait for "go"**.

## 9. Open Questions for You (non-blocking — defaults assumed unless you object)

1. **LLM keys**: v1 assumes `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` optional env vars with an
   `EchoLLM`/`FakeLLM` fallback so the stack runs with no key. OK?
2. **Default embedding**: `BAAI/bge-m3` (1024-dim) for quality vs `intfloat/multilingual-e5-small`
   (384-dim) for speed/size. Plan: bge-m3 in prod, e5-small overridable in dev/CI. OK?
3. **Auth**: reads public, staff-only writes via Django admin session/token. No public user
   accounts in v1 (feedback sent anonymously). OK?
4. ~~**Language**: Persian default UI + content; EN supported but seed content is mostly FA.~~
   **RESOLVED 2026-10-03 — approved: Persian is the product language** (see DECISIONS.md P1).
5. **Price alerts (Phase 7)**: stub only (model + UI placeholder, no scheduler). OK?

---

## 10. Approval Log

- **2026-10-03** — Plan approved with the note *"zaban farsi bashe"* → Persian-first confirmed
  (DECISIONS.md P1). **Phase 0 started.**
