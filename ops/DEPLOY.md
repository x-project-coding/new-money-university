# Deploying New Money University (new-money.42bucks.com)

The site is a branded fork of [Frappe Learning](https://github.com/frappe/lms)
running as a self-contained docker compose stack on the goclaw server, fronted
by the host nginx (same pattern as the other 42bucks vhosts). DNS is covered by
the `*.42bucks.com` wildcard record.

## Image

Built with [frappe_docker](https://github.com/frappe/frappe_docker)'s layered
Containerfile, mirroring upstream LMS's own `build.yml`:

```bash
cat > /tmp/apps.json <<'EOF'
[
  {"url": "https://github.com/frappe/payments", "branch": "version-15"},
  {"url": "https://github.com/x-project-coding/new-money-university", "branch": "main"}
]
EOF
git clone --depth 1 https://github.com/frappe/frappe_docker
cd frappe_docker
DOCKER_BUILDKIT=1 docker build \
  --build-arg FRAPPE_BRANCH=version-16 \
  --build-arg CACHE_BUST=<sha8> \
  --secret id=apps_json,src=/tmp/apps.json \
  -f images/layered/Containerfile \
  -t ghcr.io/x-project-coding/new-money-university:<sha8> \
  -t ghcr.io/x-project-coding/new-money-university:latest .
docker push ghcr.io/x-project-coding/new-money-university:<sha8>
docker push ghcr.io/x-project-coding/new-money-university:latest
```

Build from `origin/main` of this repo only (the apps.json above pins the
GitHub URL, so a local dirty tree can never leak into the image). `<sha8>` =
short SHA of this repo's main; the `:<sha8>` tags are the rollback points.

`CACHE_BUST` is mandatory on rebuilds: the bench-init layer clones this repo
at build time, so without it docker serves the cached layer and the image
silently ships the previous commit (every step reports CACHED).

## Stack

```bash
cd ops
# .env holds DB_ROOT_PASSWORD + ADMIN_PASSWORD (mode 600, gitignored;
# values recorded in ~/x-onboarding/knowledge/credentials.md on goclaw)
docker compose -p new-money -f compose.yml up -d
```

Services: mariadb 11.8, redis-cache, redis-queue, backend (gunicorn),
frontend (nginx, published on 127.0.0.1:8090), websocket (socketio),
queue-short, queue-long, scheduler. One-shot `configurator` writes
common_site_config.json; one-shot `create-site` creates the
`new-money.42bucks.com` site with payments + lms installed (skips if the
site directory already exists).

## Host nginx + TLS

```bash
sudo cp ops/nginx/new-money.42bucks.com.conf /etc/nginx/sites-enabled/new-money.42bucks.com
sudo nginx -t && sudo nginx -s reload
sudo certbot --nginx -d new-money.42bucks.com   # adds :443 + redirect in place
```

## Content + settings seeding

```bash
docker compose -p new-money -f compose.yml exec -T -e RESEND_API_KEY=<key> \
  backend bench --site new-money.42bucks.com execute lms.seed_nmu.run
```

The seeder ships inside the app (`lms/seed_nmu.py`), so it is available in
any image built from this repo. Do not pipe scripts into `bench console`:
piped IPython splits multi-line blocks at blank lines and executes the
fragments, which is how the first deploy of this site half-ran.

Idempotent. Sets Website Settings branding (app name, logo, favicon,
home page → lms, signup enabled), LMS Settings, the Resend SMTP outgoing
Email Account (smtp.resend.com:587, login `resend`, password = API key,
sender university@xsor-email.com), and creates the three example courses
(Money Foundations, Investing 101, Earning Online) plus the Investing
Basics Check quiz under instructor dean@new-money.42bucks.com.

## Platform integration (agent app + shared signup)

The university is an agent app on the 42bucks platform, "like every other
agent app": repo `x-agent-apps` → `apps/university`, served at
`https://app.42bucks.com/a/university/` (container `x-agent-apps-university-rNN`
on 127.0.0.1:3054, nginx location in the `x-app` vhost). It is registered as
`AgentAppTemplate` slug `university`, bound to the Operations Lead agent, and
installed across all its workspaces.

Signup is shared with the main app: the agent app's BFF
(`GET /api/university/launch`) reads the signed agent-app session, mints a
240s HMAC token (`NMU_SSO_SECRET`, shared with this site's
`site_config.nmu_sso_secret`), and hands the browser
`/api/method/lms.nmu_sso.login?token=...` (`lms/nmu_sso.py`), which
provisions the Website User (LMS Student) on first visit and opens the
session. All platform users land in the same course catalog. The LMS's own
signup remains enabled for direct visitors; disable it via LMS Settings +
Website Settings `disable_signup` once platform SSO should be the only door.

## Upgrades

```bash
git fetch upstream && git merge upstream/main   # pull Frappe Learning updates
# resolve, push, rebuild the image (above), then:
docker compose -p new-money -f compose.yml pull backend
docker compose -p new-money -f compose.yml up -d
docker compose -p new-money -f compose.yml exec backend \
  bench --site new-money.42bucks.com migrate
# MANDATORY after any image rollover, in this order:
docker compose -p new-money -f compose.yml exec backend \
  bench --site new-money.42bucks.com clear-cache
docker compose -p new-money -f compose.yml restart backend frontend
```

Why the last two steps: redis-cache (not recreated on rollover) still holds
the OLD image's asset manifest; fresh gunicorn workers read it, memoize it
in process memory, and render HTML referencing hashed CSS/JS bundles that no
longer exist -> guests get an unstyled, broken login page (bit us 2026-08-10).
`clear-cache` purges redis, the backend restart drops the workers' memoized
copy, and the frontend restart re-resolves the backend's DNS (its nginx pins
the upstream IP at startup, so a backend restart alone leaves it 502ing).

## Asset-only fast path (frontend-only changes)

The full layered build needs ~20GB of buildkit cache and this host's root fs
runs chronically near 100% -- a full rebuild has twice pushed it to 0 bytes
free, which threatens every other service on the box. When a change touches
only `frontend/` (Vue, CSS), build just the assets on top of the last image:

```bash
git fetch origin main:refs/remotes/origin/main   # deploy from origin/main, never the worktree
mkdir -p /tmp/nmu-ctx && git archive origin/main | tar -x -C /tmp/nmu-ctx
cp ops/Dockerfile.assets /tmp/nmu-ctx/
cd /tmp/nmu-ctx && DOCKER_BUILDKIT=1 docker build -f Dockerfile.assets \
  --build-arg BASE=ghcr.io/x-project-coding/new-money-university:<current-sha8> \
  -t ghcr.io/x-project-coding/new-money-university:<new-sha8> .
docker tag ...:<new-sha8> ...:latest && docker push both tags
```

Takes ~2 minutes and a few hundred MB. Use the full layered Containerfile
whenever python, dependencies, or the frappe version change.

**Gotcha -- nginx serves assets from its OWN copy.** `sites/assets/lms` is a
symlink to `apps/lms/lms/public`, and each container resolves it inside its own
filesystem. `apps/` is NOT in the shared `sites` volume, so assets rebuilt in
the backend container 404 until they are also copied into the frontend
container:

```bash
docker exec new-money-backend-1 tar -cf - -C /home/frappe/frappe-bench/apps/lms/lms/public frontend \
  | docker exec -i new-money-frontend-1 tar -xf - -C /home/frappe/frappe-bench/apps/lms/lms/public
```

This only matters when hot-patching a running stack; a proper image rollover
carries both containers.

## Operations

- Logs: `docker compose -p new-money -f compose.yml logs -f backend`
- Bench shell: `docker compose -p new-money -f compose.yml exec backend bash`
- Backup: `... exec backend bench --site new-money.42bucks.com backup`
  (writes into the `sites` volume under `new-money.42bucks.com/private/backups`)
- Rollback: retag `ghcr.io/x-project-coding/new-money-university:<old-sha8>`
  as `:latest`, `up -d`, and run `bench migrate` if the schema moved.
