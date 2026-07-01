# Deploying the Fraud Detection Dashboard

Serves the dashboard publicly at
**https://ai.arttechgroup.com:7777/fraud-detection/**.

This is a **static-only** app: a single container runs the Python pipeline at
**build time**, bundles the resulting JSON into the React SPA, and serves it with
nginx. There is **no backend and no database** at runtime.

```
Docker image build
   ├─ Stage 1  python pipeline   → outputs/*.json  + frontend/public/data/*.json
   ├─ Stage 2  npm run build     → dist/ (SPA with /fraud-detection/ base, data bundled)
   └─ Stage 3  nginx :8080       → serves the SPA under /fraud-detection/
                                     │
browser ──TLS :7777──► host nginx ──/fraud-detection/──► 127.0.0.1:4779 ──┘
```

> This runs on the Linux server. From a Windows checkout, push to git and pull on
> the server (or copy the repo over), then run the steps below **on the server**.

---

## 1. Deploy the container

```bash
./deploy.sh            # pull latest, build, start, health-check
./deploy.sh --no-pull  # build & start the current checkout (no git pull)
```

Or manually:

```bash
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

The build runs the full pipeline (train model → detectors → dashboard data), so
the first build takes a few minutes. When it finishes, the dashboard is reachable
locally at **http://127.0.0.1:4779/fraud-detection/** and the health endpoint at
**http://127.0.0.1:4779/healthz** returns `ok`.

---

## 2. Configure the host nginx (one time)

The container binds to loopback **4779** only. The public entrypoint is the host
nginx on `:7777`, which must be told to proxy `/fraud-detection/` to that port.

See **[NGINX-DEPLOY-GUIDE.md](NGINX-DEPLOY-GUIDE.md)** for the exact upstream,
redirect, and location blocks to add, then:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

After that the dashboard is live at
**https://ai.arttechgroup.com:7777/fraud-detection/**.

---

## Local test (optional)

`docker-compose.yml` serves the same image on port 80 for a quick local check:

```bash
docker compose up -d --build
# open http://localhost/fraud-detection/
```

---

## Common operations

```bash
docker compose -f docker-compose.prod.yml logs -f dashboard   # tail logs
docker compose -f docker-compose.prod.yml ps                  # container status
docker compose -f docker-compose.prod.yml restart dashboard   # restart
docker compose -f docker-compose.prod.yml down                # stop & remove
```

## Notes

- **TLS** is terminated by the host nginx on `:7777`; the container speaks plain
  HTTP on loopback. No certs are mounted into the container.
- **Refreshing the data**: the dashboard JSON is baked into the image at build
  time. To publish new pipeline results, rebuild and redeploy (`./deploy.sh`).
- **Port**: 4779 is this project's loopback port. If it clashes on the host,
  change it in `docker-compose.prod.yml`, `deploy.sh` (`PORT`), and the nginx
  upstream in NGINX-DEPLOY-GUIDE.md so all three stay in sync.
- **Base path**: the SPA is built with Vite `base=/fraud-detection/`; the router
  basename and JSON loader derive from it, so everything is served under that
  prefix. Local `npm run dev` still runs at `/` (http://localhost:5174/).
