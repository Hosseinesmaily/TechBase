# تک‌بیس — TechBase

Interactive knowledge base + dynamic wiki + agentic RAG assistant for a PC hardware retailer.
**Persian-first** (UI, content, answers), English supported.

> Status: **Phase 2 (wiki core) done** — see [docs/PLAN.md](docs/PLAN.md) and [docs/PROGRESS.md](docs/PROGRESS.md).

## Stack

- **Backend**: Python 3.12, Django 5, DRF, Wagtail (Phase 2+), Celery + Redis
- **DB**: PostgreSQL 16 + pgvector (single source of truth + vector store)
- **Search**: Meilisearch (lexical) + pgvector (semantic), fused with RRF
- **Frontend**: Nuxt 3 (SSR, RTL, Persian), Tailwind CSS
- **AI**: provider-agnostic LLM adapters (Anthropic / OpenAI-compatible), streaming via SSE
- **Infra**: Docker Compose, GitHub Actions CI

## Quickstart (with Docker)

```bash
cp .env.example .env          # then edit secrets for anything non-local
docker compose up             # or: make run
```

Services:

| Service | URL |
|---|---|
| Frontend (Nuxt SSR) | http://localhost:3000 |
| Catalog (Nuxt page) | http://localhost:3000/catalog |
| Wiki (Nuxt page) | http://localhost:3000/wiki |
| API | http://localhost:8000/api/v1/ |
| OpenAPI docs | http://localhost:8000/api/docs/ |
| Editorial CMS (Wagtail) | http://localhost:8000/cms/ |
| Django admin | http://localhost:8000/admin/ |
| Meilisearch | http://localhost:7700 |

The backend runs `migrate` + `collectstatic` automatically on startup.

## Make targets

| Target | What it does |
|---|---|
| `make setup` | create `.env`, build images, migrate |
| `make run` | `docker compose up` |
| `make test` | backend pytest + frontend tests |
| `make lint` | ruff check/format + frontend typecheck |
| `make typecheck` | mypy (backend) + nuxt typecheck |
| `make migrate` / `make seed` / `make reindex` | DB migrate / demo data / reindex |
| `make seed-wiki` | demo wiki pages + auto-linking (Phase 2+) |
| `make eval` | RAG evaluation (Phase 4+) |
| `make down` / `make logs` | stop / follow logs |

**No Docker?** Targets accept `LOCAL=1` to run against the host toolchain
(`make test LOCAL=1`). Backend then needs `DB_ENGINE=sqlite` for most tasks.

## Demo path

1. `make setup && make run`
2. Open http://localhost:3000 — home shows API health.
3. `make seed` — demo catalog: 26 components + 10 prebuilt PCs, prices in tomans,
   real sockets/memory types, benchmark numbers, Persian names.
4. `make seed-wiki` — 17 wiki pages of Persian technical writing, auto-linked
   (37 internal links, 12 red links = the editorial backlog).
5. Browse:
   - http://localhost:3000/catalog — filter by type, brand, price, stock
   - http://localhost:3000/wiki — the article index
   - http://localhost:3000/wiki/ryzen-7-7800x3d/ — a page with internal links;
     hover a linked name for a card with price, stock and key specs
   - http://localhost:8000/cms/ — the editorial admin (`admin` / `admin`)
6. `make seed` again is safe (it updates in place).

### Try the API directly

```bash
# products with a price + stock
curl "http://localhost:8000/api/v1/catalog/products/?category=prebuilt&in_stock=true"

# compatibility check — deterministic rules, no LLM
curl -X POST http://localhost:8000/api/v1/compat/check/ \
  -H "Content-Type: application/json" \
  -d '{"parts":["ryzen-7-7800x3d","gigabyte-b760m-ds3h"]}'
# → {"verdict":"block","findings":[{"rule_code":"SOCKET_MATCH", ...}]}

# benchmark numbers
curl "http://localhost:8000/api/v1/benchmarks/?component=rtx-4070-super&resolution=1440p"
```

## Data model (Phase 1)

```
Brand ─┐
        ├─ Entity ── ComponentSpec (common/extra JSONB specs)
Category┘      │
                ├─ Product (sku, price, stock, updated_at)  ← the only place price/stock live
                └─ Benchmark (game, resolution, avg_fps, p1_low, rig, tested_at)
```

`Entity` is the stable identity of a thing; `Product` is a SKU that sells it.
Compatibility rules are DB rows (tunable severity/params) plus a Python class
per rule — the verdict is always computed by the rule engine, never by a model.

## Configuration

All configuration is environment-driven — copy `.env.example` → `.env`.
**Never commit `.env`.** LLM API keys are optional: the stack boots without them
(a `FakeLLM` adapter is used until real keys are provided).

## Development

```bash
# backend (host)
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements/dev.txt
cd backend && python manage.py migrate && python manage.py seed_demo

# frontend (host)
cd frontend && npm install && npm run dev
```

CI runs `ruff`, `pytest`, `mypy`, `nuxt typecheck`, and an SSR build on every push/PR.

## Docs

- [docs/PLAN.md](docs/PLAN.md) — architecture, data model, API surface, estimates
- [docs/PROGRESS.md](docs/PROGRESS.md) — phase log
- [docs/DECISIONS.md](docs/DECISIONS.md) — decisions & assumptions
