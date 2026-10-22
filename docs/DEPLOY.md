# DEPLOY — bringing TechBase to production

This is the production path. The development path is the README.

## 1. What you need

- Docker Engine 24+ and the Compose plugin (v2).
- A domain with TLS terminated in front of the stack (a reverse proxy, a load
  balancer, or a managed container platform).
- The secrets listed below. **None of them belong in the repository.**

## 2. The environment

```bash
cp .env.example .env
```

Then fill in, at minimum:

| Variable | Why |
|---|---|
| `DJANGO_SECRET_KEY` | The Django signing key. Generate one: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `DJANGO_ALLOWED_HOSTS` | The hostnames the backend answers on, comma separated |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | The public origin of the site, e.g. `https://techbase.example` |
| `DB_PASSWORD` | The database password |
| `MEILI_MASTER_KEY` | The Meilisearch key — it must be long and random |
| `REDIS_PASSWORD` | The Redis password (the compose file passes it through) |
| `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` | Without one the assistant runs on the `FakeLLM` adapter: it answers from the retrieved context, but it does not reason. |
| `NUXT_PUBLIC_SITE_URL` | The public URL, used for the sitemap, the canonical links and the structured data |
| `EMBEDDING_PROVIDER` | `bge-m3` for real semantic search (see below) |

`compose.prod.yaml` refuses to start when a required variable is missing —
the `:?` syntax in the file makes it a hard error, not a default.

## 3. The embedding model

The default `EMBEDDING_PROVIDER=hash` is a **baseline**, not a semantic model.
For real semantic retrieval, install `sentence-transformers` in the backend
image and set the provider to `bge-m3`:

```dockerfile
# docker/Dockerfile.backend, in the prod stage
RUN pip install -r requirements/prod.txt sentence-transformers
```

The model is downloaded on first use (~2.2 GB) and then cached in the image or
on a volume. Mount a volume at `/root/.cache/huggingface` to avoid downloading
it on every container start.

## 4. Start

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

The backend runs `migrate`, `configure_site` and `collectstatic` on start, so
a fresh database comes up ready.

Load the demo data (optional, for a staging environment):

```bash
docker compose -f compose.yaml -f compose.prod.yaml exec backend \
  python manage.py seed_demo && \
  python manage.py seed_wiki && \
  python manage.py index_content
```

## 5. The reverse proxy

The stack serves HTTP. Put TLS in front of it. The two things that matter:

- **SSE must not be buffered.** The chat streams its answer; a proxy that
  buffers the response makes the whole feature look broken. For nginx:

  ```nginx
  location /api/v1/ai/chat/ {
      proxy_pass http://backend:8000;
      proxy_http_version 1.1;
      proxy_set_header Connection '';
      proxy_buffering off;
      proxy_read_timeout 120s;
  }
  ```

- **The uploads and the static files** are served by the frontend container
  (Nitro) and by Django (the media volume). Point both at the right service.

## 6. The scheduled jobs

`celery-beat` runs the schedule in `config/settings/base.py`:

| Job | How often | What it does |
|---|---|---|
| `integrations.sync_inventory` | every 3 hours | refreshes the price and the stock from the inventory adapter |
| `linking.check_integrity` | daily | the red-link and orphan-page audit |
| `search.reindex` | daily | rebuilds the Meilisearch indexes |

## 7. The backups

The database is the only state that cannot be rebuilt from the code:

```bash
docker compose -f compose.yaml -f compose.prod.yaml exec db \
  pg_dump -U techbase techbase | gzip > backup-$(date +%F).sql.gz
```

The Meilisearch index and the chunk embeddings can be rebuilt with
`manage.py reindex` and `manage.py index_content`.

## 8. What to watch

- `GET /api/v1/health/` — liveness.
- `GET /api/v1/health/ready/` — readiness (the database and Redis).
- The `X-Trace-Id` header on every response; the same id appears in the logs.
- The `X-RateLimit-Remaining` header: a client that keeps hitting zero is
  either a scraper or a loop.
- The query log (`QueryLog`) for the unanswered questions — the editorial
  backlog.

## 9. Rolling back

```bash
docker compose -f compose.yaml -f compose.prod.yaml down
docker compose -f compose.yaml -f compose.prod.yaml up -d --build <previous-tag>
```

The database is not migrated down automatically. Take a dump before a
migration and restore it if the new one has to be undone.
