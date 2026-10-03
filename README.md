# تک‌بیس — TechBase

Interactive knowledge base + dynamic wiki + agentic RAG assistant for a PC hardware retailer.
**Persian-first** (UI, content, answers), English supported.

> Status: **Phase 0 (scaffolding)** — see [docs/PLAN.md](docs/PLAN.md) and [docs/PROGRESS.md](docs/PROGRESS.md).

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
| API | http://localhost:8000/api/v1/ |
| OpenAPI docs | http://localhost:8000/api/docs/ |
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
| `make migrate` / `make seed` / `make reindex` | DB migrate / demo data / reindex |
| `make eval` | RAG evaluation (Phase 4+) |
| `make down` / `make logs` | stop / follow logs |

**No Docker?** Targets accept `LOCAL=1` to run against the host toolchain
(`make test LOCAL=1`). Backend then needs `DB_ENGINE=sqlite` for most tasks.

## Demo path

1. `make setup && make run`
2. Open http://localhost:3000 — home shows API health.
3. `make seed` — demo catalog data (Phase 1).
4. Browse wiki + search + assistant (Phases 2–5).

## Configuration

All configuration is environment-driven — copy `.env.example` → `.env`.
**Never commit `.env`.** LLM API keys are optional: the stack boots without them
(a `FakeLLM` adapter is used until real keys are provided).

## Development

```bash
# backend (host)
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements/dev.txt
cd backend && python manage.py test

# frontend (host)
cd frontend && npm install && npm run dev
```

CI runs `ruff`, `pytest`, `nuxt typecheck`, and an SSR build on every push/PR.

## Docs

- [docs/PLAN.md](docs/PLAN.md) — architecture, data model, API surface, estimates
- [docs/PROGRESS.md](docs/PROGRESS.md) — phase log
- [docs/DECISIONS.md](docs/DECISIONS.md) — decisions & assumptions
