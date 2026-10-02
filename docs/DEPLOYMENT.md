# Deployment

The Render blueprint runs the API and dashboard as separate services with a managed
PostgreSQL database. Both services use the same generated `EVALFORGE_ACCESS_KEY` and
`EVALFORGE_ENVIRONMENT=production`. The API requires a bearer key for application
routes, and the dashboard requires visitors to sign in with that key before it
requests data. Health checks remain public and do not return dataset contents.

The shared key is intended for a small, trusted team. Everyone with the key has
full access to documents, configuration, and model execution. Use an identity-aware
proxy and a suitable authorization layer when individual accounts or tenant
isolation are required. Send browser and external API traffic over HTTPS.

## Render

1. Push the reviewed code to your repository and create a Render Blueprint from
   `render.yaml`. Review the paid database and web-service plans before creating
   resources; deployment incurs the provider's current charges.
2. Wait for both web services to become healthy. The API initializes tables and the
   PostgreSQL `vector` extension on startup. If extension creation fails, check that
   the chosen PostgreSQL plan supports pgvector and that the database user may
   create the extension. The blueprint uses PostgreSQL 16 and restricts database
   access to Render's private network.
3. Retrieve `EVALFORGE_ACCESS_KEY` from the `evalforge-shared` environment group in
   Render's settings and enter it in the dashboard sign-in form. Do not include
   the key in URLs, source control, or screenshots. Rotate it by changing the group
   value and redeploying both services; existing dashboard sessions must sign in
   again with the new key.
4. The production database starts empty. Import your own JSON dataset in the
   dashboard and create a local model configuration to run without model secrets.
   For an optional demonstration, run `evalforge seed` once in the API service's
   Render shell. Restarts do not automatically add demonstration data.
5. Configure external model credentials in the API service's secret environment
   settings only. Configuration authors are trusted maintainers: they can choose
   provider URLs and environment-variable names, and the server sends the selected
   credential to that provider. Only grant the shared key to people trusted with
   server credentials. The dashboard does not need model credentials or direct
   database access.

The API's `/health` checks its database connection. The dashboard's
`/_stcore/health` checks its process. After deployment, verify all of the following:

- Both health endpoints respond successfully over the provider's HTTPS URLs.
- An unauthenticated request to `/api/v1/documents` returns HTTP 401.
- Dashboard visitors see a sign-in form before any dataset or experiments.
- With the key, import a small dataset, create a local configuration, run an
  experiment, and inspect its report.
- Restart the API service and confirm the dataset and experiment still exist.

Database data is stored in managed PostgreSQL, not in service containers. Before
upgrades, arrange backups and verify restoration using the provider's supported
tools. Application rollback uses the previous service deployment; table creation
is automatic, but schema migrations and downgrade handling are not implemented.

## Local Docker Compose

```bash
docker compose up --build --wait
```

Visit <http://localhost:8501>; the API is at <http://localhost:8000>. This local
workflow uses development mode, seeded demonstration data, and the bundled
development database password. Published ports bind to loopback only. Keep this
configuration local; use the authenticated production blueprint for hosting.

Compose waits for PostgreSQL and API health before starting dependent services.
The PostgreSQL named volume preserves data across restarts and `docker compose
down`. Running `docker compose down --volumes` deletes that local data.

## Standalone image

```bash
docker build -t evalforge:local .
docker run --rm -p 127.0.0.1:8000:8000 \
  --mount type=volume,source=evalforge-data,target=/data \
  evalforge:local
```

The image runs as an unprivileged user and defaults to SQLite at
`/data/evalforge.db`. Mount `/data` to retain standalone data. PostgreSQL deployments
override `EVALFORGE_DATABASE_URL`, as the Render and Compose definitions do. The
standalone example is a local development API; production mode also requires an
access key. Streamlit usage telemetry is disabled in the image.
