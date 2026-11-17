# تک‌بیس — TechBase

Interactive knowledge base + dynamic wiki + agentic RAG assistant for a PC hardware retailer.
**Persian-first** (UI, content, answers), English supported.

> Status: **Phase 5 (agentic layer) done** — see [docs/PLAN.md](docs/PLAN.md) and [docs/PROGRESS.md](docs/PROGRESS.md).

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
| Assistant (Nuxt page) | http://localhost:3000/chat |
| API | http://localhost:8000/api/v1/ |
| OpenAPI docs | http://localhost:8000/api/docs/ |
| Editorial CMS (Wagtail) | http://localhost:8000/cms/ |
| Admin entry point | http://localhost:3000/adminpanel (server-side redirect to the admin login) |
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
| `make index-content` | chunk + embed the wiki for the assistant (Phase 4+) |
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
7. `make reindex` — build the Meilisearch indexes (needs the search container;
   without it the search falls back to PostgreSQL and still works).
8. `make index-content` — chunk and embed the wiki pages for the assistant.
9. Ask the assistant at http://localhost:3000/chat — the answer carries
   product cards and citations that link to the exact section it came from.
   It asks a clarifying question only when the request actually needs one: a named
   part, a price or a stock question is answered directly, while a broad build (or an
   unintelligible message) gets one targeted question.
10. Try the configurator at http://localhost:3000/configurator — every card is badged by
    the deterministic rule engine against the parts already chosen (compatible / warning /
    incompatible with the reason / "not enough information yet"), and a choice is never
    removed silently when it conflicts.
11. The wiki index (http://localhost:3000/wiki) keeps the filter **and** the page number in
    the URL, so a filtered or paginated view can be shared and reloaded.
12. The admin entry point is http://localhost:3000/adminpanel — it redirects to the existing
    Django admin login. Authentication and the staff check stay on the server; the route
    only knows *where* the login is published (`NUXT_ADMIN_BASE_URL`).

### Evaluate the assistant

```bash
make eval        # the golden set: 30 Persian + 10 English questions
```

Reports the retrieval hit-rate, the answer quality, the citation rate and
the guardrail pass rate, per language, and lists the failures.

### How the assistant is kept honest

| Rule | How it is enforced |
|---|---|
| A price or a stock count is **never** from the model's memory | Every number in a price/stock sentence is checked against the tool results; a mismatch replaces the answer |
| Compatibility is **never** decided by a model | The verdict comes from the deterministic rule engine and is quoted verbatim |
| Every wiki claim carries a citation | An answer without a citation marker is rejected |
| Retrieved content is data, not instructions | Instruction-like lines are stripped before the content reaches the prompt |
| When the data is insufficient, it says so | No tool output → an explicit "not enough information" answer |

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

## Support tickets, images and the staff panel (2026-10-29 round)

- **Support tickets** — a signed-in customer opens one from `/account` and reads the answer
  there; the team answers in `/admin-panel` or in the Django admin
  (`/admin/support/ticket/`). A ticket is reachable only by its owner and the staff: a
  guessed id is a 404, and the queryset — not a hidden button — is what enforces it.
  API: `GET|POST /api/v1/support/tickets/`, `GET|PATCH /api/v1/support/tickets/<id>/`,
  `POST /api/v1/support/tickets/<id>/messages/`.
- **Images** — an article's picture is `WikiPage.hero_image`, a product's is `Product.image`;
  both are chosen and uploaded with Wagtail's own image chooser (`/cms/`), so replacing and
  removing them works the same way. The panel can upload too:
  `POST /api/v1/admin/images/` (multipart `file`, optional `page` id or `sku`). Limits: 5 MB,
  JPEG/PNG/WebP, and the file's **content** is verified with Pillow — an extension is never
  trusted. Django serves media in development and the Nuxt origin proxies `/media/**`.
- **The staff panel** (`/admin-panel`) is the same-origin workspace for the wiki and the
  tickets: it refuses a non-staff visitor with a clear message, and the API refuses the
  request itself (`is_staff`). Hiding a page was never the control.
- **The assistant** answers a greeting like a person (no tool run, no question), keeps the
  conversation's context (a budget given earlier is not asked for again), and explains a
  definition question from the wiki before it shows products.
- **Wiki demo content** — the 32 seeded articles are **development content** written to
  exercise linking, search and the assistant; they are not verified store publications.

## One command to run it on Windows (no Docker)

```powershell
.\run-site.ps1                # check the tools, migrate, seed, start both servers, open the browser
.\run-site.ps1 -SkipSeed     # only migrate and start (keeps the current data as it is)
.\run-site.ps1 -NoBrowser    # do not open the browser
.\run-site.ps1 -Stop         # stop whatever listens on 8000 and 3000
```

If PowerShell refuses to run the script (*"running scripts is disabled"*), use:

```powershell
powershell -ExecutionPolicy Bypass -File .\run-site.ps1
```

What it needs: `.venv` with `backend/requirements/dev.txt` installed, and Node.js 20 with
`npm install` already done in `frontend/` (the script runs `npm install` itself when
`node_modules` is missing). It creates a Docker-less `.env` (SQLite, no Redis/Meilisearch)
when there is none, and it opens each server in its own window so the logs stay readable.
The script writes **no password**: create the manager account once with
`cd backend; ..\.venv\Scripts\python.exe manage.py createsuperuser`.
## Navigation and sign-in (2026-10-31)

- **A double click on a catalog card's main area opens the part's wiki article**
  (`/wiki/<slug>/`). The address comes from the entity↔page binding in the database, so a
  product without a *published* article simply has no link — never a dead one. Buttons
  inside the card sit outside the double-click area. Because a double click is not a phone
  gesture, the card also carries a real "مقالهٔ ویکی این قطعه" link for mobile and keyboard.
- **The sign-in form sends a manager to `/admin-panel`** and a customer to `/account`: the
  redirect reads the server's `is_staff` from `/api/v1/accounts/me/`, never the typed name.
  The management APIs keep answering **403** to a non-staff session — the redirect is
  convenience, the 403 is the control. The demo `admin` account was created without an
  email; to sign in with a real address, set one on that account first.
- **The configurator badges every option of every step** from the same deterministic
  engine: green only when a rule actually compared the part (`checked_rules > 0`), red for
  a block, neutral for "not enough information". A conflicting choice is listed with its
  reason and is never removed silently.
- **A "not determined" card names what is missing.** When no rule can compare a candidate
  yet (a graphics card before a case or PSU is chosen, for instance), the API returns the
  reason and the card shows it — neutral is never dressed up as compatible. The cooler has
  its own rule now (air-cooler height and AIO radiator against the case).
- **In the panel, clicking a ticket opens the conversation; clicking it again closes only
  the conversation.** That toggle sends no request and never changes the ticket's status —
  closing the *ticket* stays a separate «بستن تیکت» button (and a reply reopens it).
- **Every part has a wiki article.** `make seed-wiki` writes the hand-made pages and then
  generates one from the catalog data for any published part that has no page, so the
  product ↔ wiki link is complete (the orphan/red-link audit reports zero).
- **Warranty is Persian and dynamic**: the card prints «گارانتی ۶۰ ماهه» from the product's
  own `warranty_months` — no English `60m warranty`, no hard-coded number.
- **`manage.py image_audit`** lists the products and pages that still have no image. Images
  are added through the panel (or Wagtail's chooser); a model-accurate photo is never
  replaced with another model's picture.

## Frame-rate chart on the compare page (2026-11-05)

`/compare` draws the measured frame rates as bars (one block per game +
resolution, one bar per compared product) above the exact-numbers table. Every
bar shares one scale, so a longer bar always means more frames, and the solid
core inside each bar is the 1% low. A part with no measured frame rate (a cooler,
a case, a PSU) shows a short «no benchmark» note instead of an empty chart — a
comparison is never dressed up as data that does not exist.

## Images without clicking through dozens of dialogs (2026-11-05)

`make placeholders` writes one named placeholder image per slot, so the site has no
empty frames while the real photos are collected:

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py placeholder_images      # a named tile per empty slot
#  <- replace those files with the real, model-matched photos (same name)
..\.venv\Scripts\python.exe manage.py import_images --dry-run # preview the matching
..\.venv\Scripts\python.exe manage.py import_images --force   # attach / replace
```

The name says what the photo is: `entity-<slug>.jpg` -> that part's products *and*
its wiki page; `product-<sku>.jpg` -> the product; `page-<slug>.jpg` -> the page.
(A bare `<sku>` / `<entity-slug>` / `<page-slug>` works too, auto-detected.) JPEG/
PNG/WebP, at most 5 MB, the content checked with Pillow. A file whose name matches
nothing is reported, never attached to the wrong product. `image_audit --names`
lists what is still missing. The panel (`/admin-panel`) and the Wagtail chooser
still work — this is just the batch path (`make image-audit` / `make
import-images`).

