# PROGRESS

Phase log. Updated at every phase gate. Format: what was done / open questions / next.

---

## Phase 0 — Scaffolding — ✅ done (2026-10-04)

**Done**
- `docs/PLAN.md` approved; Persian-first confirmed → `DECISIONS.md` P1, PLAN §10.
- Repo structure: `backend/` (Django 5.2 + DRF + Celery, apps: `core`, `catalog`,
  `search` stubs), `frontend/` (Nuxt 3 + Tailwind, RTL/Persian defaults, pages:
  `/`, `/search`, `/chat`), `docker/`, `docs/`, `.github/workflows/ci.yaml`.
- Settings split (`base/dev/prod/test`), env-driven config, `.env.example` (no secrets).
- Health endpoints: `GET /api/v1/health/`, `GET /api/v1/health/ready/` (db + redis checks).
- OpenAPI schema served at `/api/schema/` + `/api/docs/`.
- Compose stack: pgvector/pg16 + redis + meilisearch + backend + celery worker/beat +
  frontend; auto `migrate` + `collectstatic` on backend start; Nitro `/api/**` proxy
  (same-origin, no CORS).
- Makefile: `setup run test lint fmt typecheck migrate seed reindex eval down logs`
  (+ `LOCAL=1` host mode — DECISIONS T1).
- Makefile stubs `seed_demo` / `reindex` exist as management commands (real work in
  Phase 1/3 — DECISIONS A5).

**Verified on this host** (no Docker available — DECISIONS T1; CI covers the container path)
- `pip install -r backend/requirements/dev.txt` → Django 5.2.17 ✓
- `ruff check .` + `ruff format --check .` → clean ✓
- `pytest` → **4 passed** (health, readiness, homepage, 405) ✓
- `manage.py check` / `migrate` (SQLite) / `seed_demo` / `reindex` → OK ✓
- `npm install` (754 pkgs) → `npm run typecheck` ✓ → `npm run build` (SSR) ✓
- `compose.yaml` parses (7 services), env_file optional ✓
- Not verifiable here: `docker compose up` (no Docker on host), `make` (no make on host).

**Post-gate fixes (2026-10-20)**
- Root `pytest.ini` added: pytest from repo root (make LOCAL/IDE discovery) was failing
  with `ImproperlyConfigured` (DJANGO_SETTINGS_MODULE unset). Verified 4 passed from
  both root and `backend/`. (`b7a53c2`)
- Makefile `LOCAL=1`: now prefers `.venv` over system `python`; Django/mypy targets run
  from `backend/` on the host (`PY_BE`). (`b7a53c2`)
- `prompt.txt` (original spec) committed as requested.

**Open questions**
- None blocking. Git identity not configured on this machine — commits use a per-command
  `-c user.name/-c user.email` placeholder; set `git config user.name/user.email` if you
  want your identity on future commits.

**Next**: gate review → Phase 1 (data foundation: models, migrations, seed, REST API).

---

## Phase 1 — Data foundation — ✅ done (2026-10-22)

**Done**
- **Models + migrations**: `catalog` (Brand, Category, Entity, Product, ComponentSpec),
  `compat` (CompatibilityRule), `benchmarks` (Benchmark). UUID PKs, JSONB specs
  (hot fields in `common`, rest in `extra`), GIN-ready indexes on the hot paths.
- **Compatibility engine** (`apps/compat/engine.py`): pure Python, **no LLM**. 7 rules —
  SOCKET_MATCH, RAM_TYPE_MATCH, PSU_WATTAGE, GPU_CLEARANCE, COOLER_SUPPORT,
  PSU_CONNECTORS, PREBUILT_FIT. Each returns `Finding`s with a severity and a
  Persian + English message; the verdict is `ok` / `warn` / `block`. Rules are DB
  rows (severity/params/enabled) + a Python class per rule (`Rule` protocol).
- **REST API** under `/api/v1/`: catalog entities/products/brands/categories with
  filtering + pagination, `POST /compat/check/`, `GET /benchmarks/`,
  `GET /compat/rules/` (staff). OpenAPI schema at `/api/schema/` + `/api/docs/`.
- **Seed data** (`make seed`): 15 brands, 9 categories, 26 components, 10 prebuilt
  gaming PCs, 38 benchmark rows, 7 rules. Real sockets/memory types, prices in
  tomans, Persian titles + summaries. Idempotent.
- **Inventory sync**: `InventoryAdapter` protocol, mock (seeded RNG, ±5% drift) and
  CSV implementations, Celery task `integrations.sync_inventory`, `manage.py
  sync_inventory`, Celery beat every 3h. Unknown SKUs are reported, never created.
- **Frontend**: `/catalog` page with type/brand/price/stock filters (state in the
  URL), `ProductCard` component with the "last updated" date, Persian price/date
  formatting, Nitro catch-all API proxy (`server/api/[...path].ts`).
- **Admin**: editors manage entities, products, specs, rules and benchmarks.

**Verified on this host**
- `pytest` → **104 passed** ✓ (engine 27, catalog API 21, seed 14, compat API 10,
  inventory 13, benchmarks 6, core/API surface 13)
- `ruff check` + `ruff format --check` → clean ✓
- `mypy apps` → **no issues in 59 source files** ✓
- `npm run typecheck` ✓ · `npm run build` (SSR) ✓
- `migrate` → `seed_demo` → `sync_inventory` end-to-end on SQLite ✓
- Live API: 36 products, 10 prebuilts, 13 brands, schema with 10 paths ✓
- Live SSR: `/catalog?category=prebuilt` renders all 10 prebuilts with Persian
  prices (۲۷٬۵۷۵٬۵۳۶ تومان …), stock and last-updated dates ✓
- Not verifiable here: `docker compose up` (no Docker — WSL2 feature not enabled),
  `make` (no make on this host).

**Bugs found and fixed during the phase**
- Compat engine: four rules returned `[]` instead of their findings — the engine
  reported "everything is compatible" for mismatched parts.
- Connector matching compared raw strings, so `"2x 8-pin PCIe"` did not satisfy a
  GPU asking for `8-pin` (false "missing connector" warnings).
- Per-rule `params` were merged into one global dict, letting one rule's setting
  leak into another; they now live on the rule instance.
- Seed data: 3 prebuilts paired an AM5 CPU with an LGA1700 board — the demo data
  contradicted the engine. A test now asserts every seeded prebuilt is compatible.
- Nitro `routeRules.proxy` baked the API URL at build time and `/**` did not match
  `/api/v1/...`; replaced with a runtime catch-all route.
- `prod.py` accepted the built-in dev secret key; `asgi.py`/`celery.py` always used
  dev settings; `manage.py` used dev settings in the prod container.

**Open questions**
- None blocking. Prices shown in the demo are post-`sync_inventory` (the mock ERP
  drifts them by ±5%); re-run `make seed` for the exact seeded prices.
- Git identity still unconfigured — commits use the `TechBase Dev` placeholder.

**Next**: Phase 2 (Wiki core: Wagtail page types, linking engine, Nuxt RTL design
system, SEO/sitemap, demo content).

---

## Post-Phase-1 additions (2026-10-22)

- **Admin in Persian**: `LocaleMiddleware` installed, `LANGUAGES` limited to fa/en
  (Django offered ~90 locales and followed the browser), Persian `verbose_name` on
  every model and app label. The login page reads «ورود | مدیریت وب‌گاه Django».
  Superuser `admin` / `admin` created for local development.
- **Search**: `GET /api/v1/search/` returns products + entities in one response;
  `GET /api/v1/search/autocomplete/` suggests titles (min 2 chars). The `/search`
  page renders both result sets with Persian prices. Both endpoints are shaped so
  Phase 3 can swap the SQL internals for hybrid Meilisearch + pgvector without
  changing any client.
- Tests: 104 → **116 passing**; `ruff`, `mypy`, `nuxt typecheck` clean.

**Note on search**: Phase 1 search is SQL `icontains` — it matches substrings
anywhere in the title, so "RTX" also matches "منبع تغذیه Corsair RM650x" (the
brand name contains "RT"). Fuzzy/typo-tolerant matching, Persian tokenization
(ZWNJ), diacritics and digit folding are Phase 3 work (Meilisearch + the shared
normalizer, DECISIONS D14).

---

## Phase 2 — Wiki core — ✅ done (2026-10-22)

**Done**
- **Wagtail 6.4** as the editorial CMS: `WikiPage` base + `ComponentPage`,
  `BuyerGuidePage`, `ConceptPage`, all with a StreamField body (heading /
  paragraph / list / quote / callout / spec-table / image / related-entity),
  a `review_by` date for stale-content tracking, and an optional binding to a
  catalog `Entity`. The admin lives at **/cms/**, in Persian.
- **Auto-linker** (`apps/linking/autolinker.py`): Aho-Corasick over every
  entity's names, word-boundary aware, longest-match-wins, first mention per
  section. Brand names are excluded (noise). Brand names are excluded — a brand
  is reachable through its product, not through a link.
- **Link graph**: `EntityLink` stores typed edges with their section path; a
  target without a page is a **red link** = the editorial backlog. Backlinks,
  hover cards (price, stock, key specs, page link), the red-link list and the
  orphan-page list are exposed as API. A nightly Celery job records a
  `LinkIntegrityReport`.
- **Wiki API**: `GET /api/v1/wiki/pages/` and `/pages/{slug}/` serve published
  pages only, with the body as typed blocks.
- **Demo content**: `make seed-wiki` writes 17 pages of real Persian technical
  writing (component pages, concept pages, buying guides with recommended
  products), then auto-links them — 37 links, 12 red links.
- **Frontend**: `/wiki` (index with type filter), `/wiki/{slug}/` (body with
  internal entity links that show a hover card on hover, breadcrumbs, spec
  tables, callouts, product recommendations), `/entity/{slug}/`, schema.org
  Article/Product structured data, `sitemap.xml` (17 URLs) and `robots.txt`.
- **`manage.py configure_site`**: points the Wagtail site at this backend
  (hostname + port) and roots it at the site's home page — without it the admin
  shows every page as "outside any site".

**Verified on this host**
- `pytest` → **189 passed** ✓ (linking engine 20, linking services/API 21,
  content API 14, wiki end-to-end 18, plus the 116 from earlier phases)
- `ruff check` + `format --check` → clean ✓ · `mypy apps` → no issues in 89 files ✓
- `npm run typecheck` ✓ · `npm run build` (SSR) ✓
- Live: `/wiki` lists 14 published pages; `/wiki/ryzen-7-7800x3d/` renders with
  3 internal links, a spec table and JSON-LD; the 1080p buying guide shows its
  4 recommended products with prices; hover card returns price + 4 specs;
  red-link backlog lists 6 entities that still need a page ✓
- Wagtail admin: login works, all 17 wiki pages are listed and editable ✓

**Bugs found and fixed during the phase**
- The auto-linker returned **every** overlapping match: "RTX 4060" also linked
  "4060". Fixed by dropping matches shadowed by a longer one. (The bug was
  hidden by the regex fallback until `pyahocorasick` was installed.)
- The linker's `existing` map keyed by UUID while the match loop keyed by
  string, so every re-link looked new and violated the unique constraint.
- Brand names were linked as entities ("ای‌ام‌دی" → a product page).
- Orphan pages were computed as "pages with no outgoing links" — the opposite
  of the definition. Now: pages nothing links *to*.
- The wiki section page was created under the tree root instead of the site
  root, so Wagtail treated the pages as belonging to no site.
- The Wagtail site pointed at port 80 while the backend runs on 8000.
- Seeded prebuilt SKUs were doubled (`tb-sku-tb-prebuilt-…`), and the guide's
  recommended products referenced those wrong SKUs.
- The seed set the guide's fields *after* publishing, so the published
  revision kept the empty values (the API returned 404 for the guide).
- `add_child` copies the page instance; the seed kept editing the unsaved
  original, so `review_by` and the body were lost.

**Open questions**
- None blocking. The wiki demo content is 17 pages; the spec asked for ~15, and
  the six red links are the natural next pages to write.
- Not verifiable here: `docker compose up` (no Docker — the WSL2 feature is
  still off) and `make` (no make on this host).

**Next**: Phase 3 (search: Meilisearch indexing, Persian normalizer, facets,
autocomplete, search UI).

---

## Phase 3 — Search — ✅ done (2026-10-22)

**Done**
- **Persian normaliser** (`apps/search/normalizer.py`): folds ي→ی, ك→ک,
  ZWNJ→space, Arabic-Indic and Extended-Arabic-Indic digits→Latin, Arabic
  punctuation→ASCII, drops harakat/tatweel, lowercases Latin, collapses
  whitespace. Used at **both** the index and the query side — asymmetric
  normalisation silently destroys recall, so the symmetry is pinned by tests.
- **Hybrid search** (`apps/search/service.py`): Meilisearch (lexical,
  typo-tolerant, faceted) + PostgreSQL (always available), fused with
  **Reciprocal Rank Fusion** (k=60). When Meilisearch is unreachable the
  PostgreSQL results are returned unchanged, so search keeps working.
- **Meilisearch integration** (`apps/search/meili.py`): three indexes
  (entities, products, pages), searchable/facet/sortable attributes, Persian
  separator tokens, a health check, and a `reindex` management command
  (`--stats` shows what would be indexed) plus a nightly Celery job.
- **PostgreSQL backend** (`apps/search/postgres.py`): lexical search over the
  normalised text; every query token must match; filters by type, brand and
  stock; facet counts.
- **API**: `GET /api/v1/search/` (query, kind, type, brand, in_stock,
  page_size → hits, facets, took_ms, backend), `/api/v1/search/autocomplete/`
  (word-prefix matching, min 2 chars), `/api/v1/search/facets/` (brands with
  counts, entity types, stock split).
- **Frontend**: the search page filters by kind/type/brand/stock, shows facet
  counts, suggests while typing, and reports which backend answered.

**Verified on this host**
- `pytest` → **237 passed** ✓ (normalizer 28, search 32, plus the 189 from before)
- `ruff check` + `format --check` → clean ✓ · `mypy apps` → no issues in 96 files ✓
- `npm run typecheck` ✓ · `npm run build` ✓
- Live API: "RTX" → 17 hits, "رایزن" → 11, "4060" → 5, "حافظه" → 14, "DDR5" → 6;
  facets list all 13 brands with counts; autocomplete suggests the three RTX
  cards for "RTX" ✓
- `manage.py reindex --stats` → 89 documents ready (36 entities, 36 products,
  17 pages); Meilisearch not reachable on this host (no Docker) — the
  PostgreSQL fallback answers instead ✓

**Bugs found and fixed during the phase**
- The normaliser's digit map used `ord("٠" + str(i))`, which is a two-character
  string — `ord()` raised at import time.
- An empty query matched **every** document (the PostgreSQL backend treated it
  as "no filter"), so the search page listed the whole catalog.
- Autocomplete matched only the *start* of the full title, so "RTX" suggested
  nothing even though every card's title contains "RTX" — it now matches the
  start of any word, like Meilisearch's prefix strategy.
- The facet list showed only 4 of 13 brands: `.distinct()` together with an
  `annotate()` after a `filter()` cut the queryset short.
- `useFetch` cannot type a computed `query` in Nuxt 3; the search page uses
  `useAsyncData` with an explicit watcher instead.

**Open questions**
- None blocking. A Persian *synonym* dictionary ("دی‌دی‌آر" → "DDR5") is not
  implemented — Meilisearch supports it and it belongs with the Phase 4
  evaluation set, where the golden set can measure its effect.
- Not verifiable here: the Meilisearch path itself (no Docker — the WSL2
  feature is still off). The PostgreSQL fallback and the RRF fusion are tested;
  the Meilisearch branch is exercised only by the "unavailable" path.

**Next**: Phase 4 (basic RAG: heading-based chunking, embeddings, pgvector,
hybrid retrieval, SSE chat, citations, evaluation harness + golden set).




