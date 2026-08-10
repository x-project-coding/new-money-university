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

## Operations

- Logs: `docker compose -p new-money -f compose.yml logs -f backend`
- Bench shell: `docker compose -p new-money -f compose.yml exec backend bash`
- Backup: `... exec backend bench --site new-money.42bucks.com backup`
  (writes into the `sites` volume under `new-money.42bucks.com/private/backups`)
- Rollback: retag `ghcr.io/x-project-coding/new-money-university:<old-sha8>`
  as `:latest`, `up -d`, and run `bench migrate` if the schema moved.
