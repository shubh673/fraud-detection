# Deploying to AWS EC2 (Docker)

Step-by-step guide to run the Card & Payment Fraud Detection dashboard live on an
AWS EC2 instance using Docker.

---

## What "live" means here

There is **no always-on backend**. The Python pipeline is a **batch job** that
produces JSON, and the dashboard is a **static React site** that reads it. So the
deployment is:

```
Docker build:  run pipeline (train + detectors + prepare data)  ->  build React app
Docker run:    nginx serves the built static site on port 80
```

The provided `Dockerfile` does all of this in one multi-stage build. The heavy model
(~330 MB) and datasets live only inside the build stages; the final served image is
just nginx + the built static files.

**Files used for deployment** (already in the repo):
- `Dockerfile` — 3-stage build (pipeline → frontend → nginx)
- `deploy/nginx.conf` — static serving + SPA fallback for React Router routes
- `docker-compose.yml` — one-command build & run
- `.dockerignore` — keeps the build context small

---

## Prerequisites

- An **AWS account** and an **EC2 key pair** (for SSH).
- Your code pushed to **GitHub** (recommended) — the `.gitignore` already keeps the
  repo small (~87 MB) and excludes the files that break pushes. Alternatively you can
  `scp` the project up.

---

## Step 1 — Launch an EC2 instance

In the AWS Console → **EC2 → Launch instance**:

| Setting | Recommended value | Notes |
|---|---|---|
| **Name** | `fraud-dashboard` | |
| **AMI** | Ubuntu Server 24.04 LTS | Amazon Linux 2023 also fine (install cmds differ) |
| **Instance type** | **t3.medium** (2 vCPU / 4 GB) | Training the Random Forest in-container needs RAM. t3.small (2 GB) works only if you add swap (Step 3b). |
| **Key pair** | select/create one | download the `.pem` |
| **Storage** | **20 GB gp3** | build intermediates need room |

**Security group — inbound rules:**

| Type | Port | Source | Why |
|---|---|---|---|
| SSH | 22 | **My IP** | admin access |
| HTTP | 80 | Anywhere `0.0.0.0/0` | public dashboard |
| HTTPS | 443 | Anywhere | only if you add a domain + TLS (Step 7) |

Launch the instance and note its **Public IPv4 address**.

---

## Step 2 — Connect via SSH

From your machine (adjust key path / IP):

```bash
chmod 400 fraud-key.pem            # first time (Git Bash / macOS / Linux)
ssh -i fraud-key.pem ubuntu@<EC2_PUBLIC_IP>
```
(For Amazon Linux the user is `ec2-user` instead of `ubuntu`.)

---

## Step 3 — Install Docker & Git

**Ubuntu 24.04:**
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER        # run docker without sudo
```
Then **log out and back in** (so the group change applies):
```bash
exit
ssh -i fraud-key.pem ubuntu@<EC2_PUBLIC_IP>
docker --version && docker compose version
```

**Amazon Linux 2023 (alternative):**
```bash
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
# docker compose plugin:
sudo mkdir -p /usr/libexec/docker/cli-plugins
sudo curl -sSL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/libexec/docker/cli-plugins/docker-compose
sudo chmod +x /usr/libexec/docker/cli-plugins/docker-compose
# then log out/in
```

### Step 3b — (t3.small only) add swap so the build doesn't OOM
Skip this on t3.medium.
```bash
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## Step 4 — Get the code onto the instance

**Option A — clone from GitHub (recommended):**
```bash
git clone https://github.com/<your-username>/<your-repo>.git fraud_detection
cd fraud_detection
```

**Option B — copy from your machine (run locally, not on EC2):**
```bash
# excludes the heavy regenerated folders
rsync -av --exclude venv --exclude 'frontend/node_modules' --exclude outputs \
  -e "ssh -i fraud-key.pem" ./ ubuntu@<EC2_PUBLIC_IP>:~/fraud_detection/
```

> Make sure the 5 required datasets are present under
> `fraud_detection_enriched_dataset_pack/` (they are kept by `.gitignore`). The build
> regenerates the model, outputs and dashboard data — you do **not** need to copy those.

---

## Step 5 — Build and run

```bash
cd ~/fraud_detection
docker compose up -d --build
```

This will (first build ~3–6 min):
1. install Python deps and run `train_step1_model.py`, `client_requirement_pipeline.py`,
   `prepare_dashboard_data.py`;
2. `npm ci` + `npm run build` the React app (bundling the generated JSON);
3. start nginx serving on port 80.

Check it's up:
```bash
docker compose ps
docker compose logs -f        # Ctrl-C to stop following
curl -I http://localhost      # expect HTTP/1.1 200 OK
```

---

## Step 6 — Open the dashboard

In your browser:

### http://&lt;EC2_PUBLIC_IP&gt;/

You should see the Executive Overview. Deep links (e.g. `/queue`, `/bin-attack`) work
because nginx falls back to `index.html`.

---

## Step 7 — (Optional) Custom domain + HTTPS

1. Point a DNS **A record** (e.g. `fraud.example.com`) at the EC2 public IP.
2. Easiest TLS is to swap nginx for **Caddy** (automatic Let's Encrypt). Create
   `Caddyfile`:
   ```
   fraud.example.com {
       root * /usr/share/nginx/html
       try_files {path} /index.html
       file_server
       encode gzip
   }
   ```
   and run a `caddy` container mounting the built `dist/`. Ensure port 443 is open in the
   security group. (For a POC demo, the plain `http://<IP>/` from Step 6 is usually enough.)

---

## Updating / redeploying

After you push changes (or edit `config/merchant_blacklist.csv`, tune thresholds, etc.):

```bash
cd ~/fraud_detection
git pull                       # if using GitHub
docker compose up -d --build   # rebuilds + restarts
```

The rebuild re-runs the whole pipeline, so the dashboard always reflects the latest data.

---

## Cost & teardown

- **t3.medium** ≈ $0.0416/hr (~$30/mo if left on) + ~$2/mo for 20 GB EBS. **Stop** the
  instance when not demoing to avoid compute charges (EBS still bills a little).
- **Fully remove:** EC2 → Instances → select → **Terminate**. Also delete the EBS volume
  if it wasn't set to delete-on-termination, and the key pair/security group if unused.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `docker: permission denied` | You skipped the re-login after `usermod -aG docker`. Log out/in, or use `sudo docker ...`. |
| Build killed / OOM during `train_step1_model.py` | Use t3.medium, or add swap (Step 3b). |
| Browser can't reach the site | Security group missing inbound port 80; or you're using `https://` — use `http://`. |
| `502` / blank page | `docker compose logs` — check the build finished; confirm container is running (`docker compose ps`). |
| Deep link (e.g. `/queue`) 404s | Ensure `deploy/nginx.conf` is in the image (it provides the SPA fallback). |
| Disk full during build | Grow EBS to 20–30 GB, or `docker system prune -af` to clear old layers. |

---

## Appendix — optional live scoring API (not included)

The dashboard is static and does not call a backend. If you later want a **live**
real-time scoring endpoint (calling `score_transaction()` over HTTP), add a small
FastAPI/Flask service that imports `src/score_authorisation.py`, containerise it as a
second service in `docker-compose.yml`, and have the frontend POST to it. That is a
follow-on enhancement beyond the current POC scope.
