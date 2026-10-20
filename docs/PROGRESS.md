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
