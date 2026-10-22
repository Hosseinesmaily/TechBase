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

