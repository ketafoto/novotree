# Novotree — Production Deployment Guide

Target: single Hetzner VPS (Ubuntu 22.04 / 24.04), systemd + Caddy.

---

## Table of Contents

1. [Server user](#1-server-user)
2. [Directory layout](#2-directory-layout)
3. [Environment file](#3-environment-file)
4. [Build the frontend](#4-build-the-frontend)
5. [systemd service](#5-systemd-service)
6. [TLS with Caddy + Let's Encrypt](#6-tls-with-caddy--lets-encrypt)
7. [First-run owner signup](#7-first-run-owner-signup)
8. [SSH hardening](#8-ssh-hardening)
9. [Keeping the app up to date](#9-keeping-the-app-up-to-date)
10. [SQLite backups](#10-sqlite-backups)

---

## 1. Server user

Run the app as a dedicated low-privilege account with no login shell:

```bash
sudo useradd \
  --system \
  --no-create-home \
  --shell /sbin/nologin \
  --comment "Novotree app" \
  novotree
```

All application files are owned by `root` (read-only to the app) except the
`datasets/` directory, which is owned by `novotree` so it can write SQLite files.

---

## 2. Directory layout

```
/opt/novotree/
  backend/          ← Python source (owned root:root, 755)
  database/
  datasets/         ← owned novotree:novotree, 700
  frontend/dist/    ← built static files served by Caddy
  venv/             ← Python virtualenv (owned root:root)
  .env              ← secrets file (owned root:novotree, 640)
```

```bash
# Clone / copy code
sudo mkdir -p /opt/novotree
sudo git clone https://github.com/yourorg/novotree.git /opt/novotree
# OR rsync from workstation:
# rsync -av --exclude node_modules --exclude venv-win --exclude venv-linux \
#   . hetzner:/opt/novotree/

# Fix ownership
sudo chown -R root:root /opt/novotree
sudo chown -R novotree:novotree /opt/novotree/datasets
sudo chmod 700 /opt/novotree/datasets

# Python virtualenv
sudo python3 -m venv /opt/novotree/venv
sudo /opt/novotree/venv/bin/pip install -r /opt/novotree/requirements.txt
```

---

## 3. Environment file

Generate a strong JWT secret before creating the file:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Create `/opt/novotree/.env` (mode 640, owner root:novotree):

```bash
sudo install -m 640 -o root -g novotree /dev/null /opt/novotree/.env
sudo nano /opt/novotree/.env
```

Minimum required content (full template in `backend/.env.public.example`):

```ini
APP_MODE=production
CORS_ORIGINS=https://tree.example.com
ENABLE_API_DOCS=false
JWT_SECRET_KEY=<64-hex-char string from command above>
JWT_EXPIRY_HOURS=8
JWT_REFRESH_DAYS=14
# SMTP — optional; omit to show set-password links in the UI instead
# SMTP_HOST=smtp.example.com
# SMTP_PORT=587
# SMTP_USER=novotree@example.com
# SMTP_PASSWORD=secret
# SMTP_FROM=Novotree <novotree@example.com>
```

For the OVC auth model (`APP_MODE` values and JWT settings) see [docs/AUTH_SCHEMA_PROPOSAL.md](docs/AUTH_SCHEMA_PROPOSAL.md).

---

## 4. Build the frontend

```bash
cd /opt/novotree/frontend
sudo npm ci
sudo npm run build          # output → frontend/dist/
```

---

## 5. systemd service

Create `/etc/systemd/system/novotree.service`:

```ini
[Unit]
Description=Novotree genealogy backend
After=network.target

[Service]
Type=simple
User=novotree
Group=novotree
WorkingDirectory=/opt/novotree
EnvironmentFile=/opt/novotree/.env
ExecStart=/opt/novotree/venv/bin/uvicorn backend.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 1
Restart=on-failure
RestartSec=5

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/novotree/datasets

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now novotree
sudo systemctl status novotree
```

---

## 6. TLS with Caddy + Let's Encrypt

Caddy obtains and renews certificates automatically.

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

Create `/etc/caddy/Caddyfile`:

```caddy
tree.example.com {
    # Serve built frontend
    root * /opt/novotree/frontend/dist
    file_server

    # Proxy API and auth to FastAPI
    handle /api/* {
        reverse_proxy 127.0.0.1:8000
    }

    # SPA fallback — let React Router handle client-side routes
    handle {
        try_files {path} /index.html
        file_server
    }

    # Security headers
    header {
        Strict-Transport-Security "max-age=63072000; includeSubDomains; preload"
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        Referrer-Policy strict-origin-when-cross-origin
    }
}
```

```bash
sudo systemctl enable --now caddy
sudo caddy reload --config /etc/caddy/Caddyfile
```

---

## 7. First-run owner signup

Once the service is running, open `https://tree.example.com/signup` in a browser
and create the first owner account. The username you choose becomes the `owner_id`
and locates the dataset under `datasets/<owner_id>/`.

If a dataset folder already exists (migrated from a previous deployment), signup
reuses it safely — `CREATE TABLE IF NOT EXISTS` means no data is overwritten.

---

## 8. SSH hardening

```bash
# Disable password auth — key-only login
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' \
    /etc/ssh/sshd_config
sudo systemctl reload ssh
```

---

## 9. Keeping the app up to date

```bash
cd /opt/novotree
sudo git pull
sudo /opt/novotree/venv/bin/pip install -r requirements.txt   # if changed
cd frontend && sudo npm ci && sudo npm run build
sudo systemctl restart novotree
```

---

## 10. SQLite backups

The `datasets/` directory contains all genealogy and auth data. A simple nightly backup:

```bash
# /etc/cron.d/novotree-backup
# Back up system auth database and all owner databases nightly at 03:00
0 3 * * * novotree \
  for db in /opt/novotree/datasets/system.sqlite \
             /opt/novotree/datasets/*/data.sqlite; do \
    sqlite3 "$db" ".backup ${db}.$(date +\%Y\%m\%d)"; \
  done && \
  find /opt/novotree/datasets -name '*.sqlite.*' -mtime +30 -delete
```

For off-server backups, include the entire `datasets/` in your preferred tool
(restic, BorgBackup, etc.).
