# Host Nginx Configuration for the Fraud Detection Dashboard (ART)

> **This file documents changes the server owner must make to the HOST nginx
> config for `ai.arttechgroup.com` (the `listen 7777 ssl` server block). These
> changes are NOT applied automatically.**
>
> **IMPORTANT**: This is a separate, self-contained project. It does NOT share
> ports or upstreams with any other app in that server block. Do NOT modify or
> remove existing upstreams/locations — they belong to other projects.

## Architecture

```
browser ──TLS :7777──► host nginx ──/fraud-detection/──► dashboard container (nginx :8080)
                                     127.0.0.1:4779
```

The dashboard is a **static-only** React SPA — no backend, no database. The host
nginx passes **all** `/fraud-detection/` traffic straight through to the
dashboard container on port **4779**; the container's own nginx serves the
prebuilt SPA (and its JSON data) under the `/fraud-detection/` path. No `rewrite`
is needed — this is the same pass-through pattern as `/scheme-compliance-art/`,
`/paci/`, `/chargeback/`, `/kyc-kyb-onboarding/` and `/ai-agents/`.

Port assignment: **4779** (4773 — my original default — is already used by
`chargeback_backend`; 4779 is the first free port after `ai_agents_frontend` on
4778).

Public URL: `https://ai.arttechgroup.com:7777/fraud-detection/`

---

## 1. Add the upstream

In the upstream block at the top of the file (e.g. right after
`ai_agents_frontend`):

```nginx
upstream fraud_detection_dashboard {
    server 127.0.0.1:4779;
}
```

## 2. Add the trailing-slash redirect

In the group of `location = /<app>` redirects inside the `server` block (next to
`location = /ai-agents { ... }`):

```nginx
location = /fraud-detection {
    return 301 /fraud-detection/;
}
```

## 3. Add the location block

In the `server` block, alongside the other frontend apps (e.g. after the
`# ==================== AI AGENTS PORTAL ====================` block):

```nginx
# ==================== FRAUD DETECTION DASHBOARD ====================
location /fraud-detection/ {
    proxy_pass http://fraud_detection_dashboard;
    proxy_http_version 1.1;
    proxy_set_header Upgrade           $http_upgrade;
    proxy_set_header Connection        'upgrade';
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_cache_bypass $http_upgrade;
    client_max_body_size 50M;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}
```

> **No `rewrite` line.** The container nginx expects the full `/fraud-detection/...`
> path (it serves the SPA and JSON under that prefix), so proxy the path through
> unchanged. Adding a `rewrite ^/fraud-detection/(.*) /$1 break;` here would break
> asset and data URLs — do not add one.

---

## Then reload

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## What NOT to change

Every existing upstream and `location` in the `:7777` server block belongs to a
different project and must be left untouched — in particular `chargeback_backend`
on **4773**. This project only *adds* the three items above (upstream on 4779,
redirect, and `/fraud-detection/` location). If 4779 is ever taken, pick another
free port and update it in `docker-compose.prod.yml`, `deploy.sh` (`PORT=`) and
the upstream above so all three stay in sync.

---

## Verification

After reloading nginx and starting the container (`./deploy.sh`):

```bash
# On the host — container answers directly on loopback:
curl -s http://127.0.0.1:4779/healthz                 # -> ok
curl -s http://127.0.0.1:4779/fraud-detection/        # -> HTML

# Through the public entrypoint:
curl -k https://ai.arttechgroup.com:7777/fraud-detection/
curl -k https://ai.arttechgroup.com:7777/fraud-detection/data/dashboard_summary.json

# Confirm a neighbouring app still works (must be unaffected):
curl -k https://ai.arttechgroup.com:7777/ai-agents/
```
