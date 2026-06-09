"""
novotree app install - the app side of the deployer/app deployment split.

The novospace *deployer* (vm-setup.py / vm-update.py) clones the repos, installs
system packages, the service user, and Caddy, then hands a `DeployContext`
(the generic toolkit) to `install(ctx)` / `update(ctx)` here. This module does
ALL of novotree's own VM wiring through that toolkit - env file, venv, frontend
build, systemd unit, journald retention, backup cron, backend-monitor backstop -
and returns an `AppManifest` (routes + static dir) the deployer uses to wire
Caddy.

App-specific facts (the app name, the journal namespace, the datasets layout,
the retention knob names, the backup preserve-env list) live HERE and never
cross up the contract. The deployer never reads them - it only calls generic
capability methods on `ctx` and reads `routes` / `static_dirs` off the returned
manifest. (`APP_NAME` is the one fact the deployer reads, to derive the generic
/etc/<app_name>.env path - see APP_NAME below.)

IMPORTS: stdlib + the contract leaf ONLY. This must NOT import the backend
(backend.config runs load_settings() at import time and needs env vars that do
not exist at install time). The app-layer constants below are deliberately a
separate copy of the deployment-relevant values, decoupled from runtime imports.
The contract leaf lives in novospace; the deployer injects its path onto
sys.path before importing this module (see vm-setup.py).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from deploy import contract

from . import backend_monitor

# Re-export backend_monitor.IMPORTANCE_WARNING as part of this module's public
# surface so the deployer reads the whole installer API (APP_NAME / install /
# update / IMPORTANCE_WARNING) from the single module it loads - it never has to
# reach into backend_monitor directly.
#
IMPORTANCE_WARNING = backend_monitor.IMPORTANCE_WARNING

__all__ = ["APP_NAME", "install", "update", "IMPORTANCE_WARNING"]

# -- App-owned deployment facts (never cross up the contract) ---------------

# The app's name. Single source of truth for everything the deployment derives
# from it: the systemd service/unit name, the journal namespace, and the env-file
# basename. The deployer owns the env-file *location* convention (/etc, root:root
# 600) but reads APP_NAME to build the path /etc/<app_name>.env - so the basename
# 'novotree' lives here, not hardcoded deployer-side.
#
APP_NAME = "novotree"

# journald namespace novotree.service logs into (PRIVACY_DESIGN.md section 3.3). The app
# is the AUTHORITY for this name: it builds the LogNamespace= directive and the
# journald@<ns>.conf path from it, and publishes it into the env file as
# JOURNAL_NAMESPACE so consumers that read the journal (the section 3.4 error-log digest
# job) use it without re-hardcoding. The deployer NEVER reads this value.
#
JOURNAL_NAMESPACE = APP_NAME

# systemd service name; matches the app name + namespace so the digest job's
# SERVICE_UNIT derivation (journalctl -u <ns>) lines up.
#
SERVICE_NAME = APP_NAME  # "novotree" -> novotree.service

# Default owner id - must match DEFAULT_OWNER_ID in backend auth / owner_info.
# Pre-creating datasets/<owner>/ here (instead of letting the app create it at
# runtime) avoids a race with the ownership pass.
#
DEFAULT_OWNER_ID = "aktiniya"

# Backend retention knobs read from the env file to size the journald window
# (PRIVACY_DESIGN.md section 3.3). Access + error logs share one journald stream, so a
# single window is sized to max() of the two and both are documented as minimums.
#
ACCESS_LOG_DAYS_ENV_VAR = "ACCESS_LOG_RETENTION_DAYS"
ACCESS_LOG_DAYS_DEFAULT = 14
ERROR_LOG_DAYS_ENV_VAR = "ERROR_LOG_RETENTION_DAYS"
ERROR_LOG_DAYS_DEFAULT = 30

# Env vars the backup cron must forward across the `sudo -u <service_user>`
# boundary. `sudo --preserve-env=` drops everything else, so every var the backup
# script needs is listed explicitly. All are read by both the backend and
# vm-backup.py from the env file; the cron sources that file before the sudo drop
# and forwards these through. (BACKUP_RETENTION_DAYS = retention window; SMTP_* +
# PRIVACY_CONTACT_EMAIL = creds + ops mailbox for vm-backup.py notify_ops(),
# PRIVACY_DESIGN.md section 3.4.)
#
BACKUP_CRON_PRESERVE_ENV_VARS = [
    "BACKUP_RETENTION_DAYS",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_FROM",
    "PRIVACY_CONTACT_EMAIL",
]

BACKUP_CRON_SCHEDULE = "0 3 * * *"        # daily at 03:00
BACKUP_CRON_USER = "root"                 # reads root:root 600 env file
BACKUP_LOG = "/var/log/novotree-backup.log"

# Backend listens here; Caddy reverse-proxies the API routes to it.
#
BACKEND_PORT = 8000

# Auth secret the operator must set by hand after a first install (it is not
# generated automatically - a fresh random value per deployment is the point).
# Surfaced to the operator via the manifest's post_install_notes; see
# _post_install_notes().
#
JWT_SECRET_ENV_VAR = "JWT_SECRET_KEY"

# Caddy sub-path the SPA is served under. VITE_BASE_PATH must match so asset URLs
# resolve under it; VITE_NOVOTREE_APP_MODE=public enables authentication.
#
FRONTEND_URL_PREFIX = "/novotree/"
VITE_APP_MODE = "public"


def _print_step(title: str) -> None:
    print(f"\n--- novotree: {title} ---")


# -- Shared sub-steps (used by BOTH install and update so they cannot drift) --


def _build_frontend(ctx: contract.DeployContext) -> Path:
    """npm install + build the frontend; return the built `dist` dir.

    Restores executable bits on node_modules/.bin (a prior chmod 644 ownership
    pass may have stripped them) before building. VITE_BASE_PATH embeds the
    serve sub-path into every asset URL; VITE_NOVOTREE_APP_MODE must be the
    non-'admin' value to enforce authentication.
    """
    frontend_dir = ctx.repo_dir / "frontend"
    ctx.run("npm", "install", "--silent", cwd=str(frontend_dir))
    ctx.run("bash", "-c", f"chmod +x {frontend_dir}/node_modules/.bin/* 2>/dev/null || true")
    ctx.run(
        "npm", "run", "build", cwd=str(frontend_dir),
        env={**os.environ, "VITE_BASE_PATH": FRONTEND_URL_PREFIX,
             "VITE_NOVOTREE_APP_MODE": VITE_APP_MODE},
    )
    return frontend_dir / "dist"


def _install_python_deps(ctx: contract.DeployContext) -> None:
    """pip install requirements into the venv (venv owned by admin_user)."""
    ctx.run(
        str(ctx.repo_dir / ".venv/bin/pip"), "install", "--quiet",
        "-r", str(ctx.repo_dir / "requirements.txt"),
    )


def _refresh_units_and_restart(ctx: contract.DeployContext) -> None:
    """Restart the backend service and refresh the backend-monitor units.

    Shared tail of both install() and update(): once code + units are in
    place, (re)start novotree and (re)install the monitor backstop.
    """
    ctx.reload_systemd()
    ctx.restart_service(SERVICE_NAME)
    backend_monitor.install_backend_monitor(ctx)


# -- Individual install-only steps ----------------------------------------


def _write_env_file(ctx: contract.DeployContext) -> None:
    """Step 6 - render the env file from the in-repo schema and write it.

    SECURITY-CRITICAL: VITE_NOVOTREE_APP_MODE=public in this file enables auth.
    The schema is the app's (.env.public.example); the deployer writes the
    rendered result to env_file_path as root:root 600 via ctx.write_env_file().
    """
    env_example = ctx.repo_dir / "backend/.env.public.example"
    if not env_example.is_file():
        sys.exit(
            "\n!!! SECURITY ABORT: "
            f"{env_example} not found.\n"
            " This file sets VITE_NOVOTREE_APP_MODE=public, which enforces auth.\n"
            " Without it, ANYONE can access novotree without logging in.\n"
            " Ensure novotree.git is up to date and re-run setup.\n"
        )
    content = env_example.read_text()
    content = re.sub(r"^CORS_ORIGINS=.*", f"CORS_ORIGINS={ctx.cors_origins}",
                     content, flags=re.MULTILINE)
    if ctx.is_dev:
        # Uncomment COOKIE_SECURE=false so cookies work over plain HTTP on a dev VM.
        content = re.sub(r"^#\s*COOKIE_SECURE=false", "COOKIE_SECURE=false",
                         content, flags=re.MULTILINE)
    ctx.write_env_file(content)
    print(f"  Env file written: {ctx.env_file_path} (root:root 600)")
    print(f"  CORS_ORIGINS set to: {ctx.cors_origins}")


def _setup_datasets_tree(ctx: contract.DeployContext) -> None:
    """Step 7 (app part) - pre-create datasets/<owner>/media with correct owner.

    Owner = admin_user (can git-pull media in); group = service_user (the app
    process creates/writes sqlite + media). dirs=770, files=660, no world access.
    Pre-creating here (rather than at app runtime) avoids a race with the
    deployer's code-dir ownership pass.
    """
    datasets_dir = ctx.repo_dir / "datasets"
    media_dir = datasets_dir / DEFAULT_OWNER_ID / "media"
    ctx.run("sudo", "mkdir", "-p", str(media_dir))
    ctx.run("sudo", "chown", "-R", f"{ctx.admin_user}:{ctx.service_user}", str(datasets_dir))
    ctx.run("sudo", "find", str(datasets_dir), "-type", "d", "-exec", "chmod", "770", "{}", ";")
    ctx.run("sudo", "find", str(datasets_dir), "-type", "f", "-exec", "chmod", "660", "{}", ";")


def _setup_venv(ctx: contract.DeployContext) -> None:
    """Step 8 - create the venv and install deps. venv owned by admin_user;
    novospace executes uvicorn from it but cannot modify it."""
    venv_dir = ctx.repo_dir / ".venv"
    ctx.run("python3", "-m", "venv", str(venv_dir))
    # Restore executable bits a previous chmod 644 pass may have clobbered.
    venv_bins = [f for f in (venv_dir / "bin").iterdir() if not f.is_symlink()]
    if venv_bins:
        ctx.run("chmod", "+x", *venv_bins)
    _install_python_deps(ctx)


def _setup_backup_dir(ctx: contract.DeployContext) -> None:
    """Step 10 - create the backups dir owned by the service user, mode 700."""
    backup_base = Path("/srv/backups") / SERVICE_NAME
    ctx.run("sudo", "mkdir", "-p", str(backup_base))
    ctx.run("sudo", "chown", f"{ctx.service_user}:{ctx.service_user}", str(backup_base))
    ctx.run("sudo", "chmod", "700", str(backup_base))


def _write_service_unit(ctx: contract.DeployContext) -> None:
    """Step 12 (unit) - write novotree.service with the app's LogNamespace=.

    The unit body, including the journal namespace, is built HERE; the deployer
    only writes the file via ctx.write_systemd_unit() and never sees the ns.
    """
    datasets_dir = ctx.repo_dir / "datasets"
    unit = f"""\
[Unit]
Description=novotree API backend
After=network.target

[Service]
User={ctx.service_user}
WorkingDirectory={ctx.repo_dir}
ExecStart={ctx.repo_dir}/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port {BACKEND_PORT}
Restart=always

# Environment loaded from {ctx.env_file_path} (root:root 600).
# Source: {ctx.repo_dir}/backend/.env.public.example
# Edit {ctx.env_file_path} to change settings; then: systemctl restart {SERVICE_NAME}
EnvironmentFile={ctx.env_file_path}

# Route this service's stdout/stderr into a dedicated journal namespace so log
# retention (journald@{JOURNAL_NAMESPACE}.conf) is scoped to novotree only.
# Read its logs with: journalctl --namespace {JOURNAL_NAMESPACE} -u {SERVICE_NAME}
LogNamespace={JOURNAL_NAMESPACE}

# Process hardening - restrict what the service process can access
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths={datasets_dir}

[Install]
WantedBy=multi-user.target
"""
    ctx.write_systemd_unit(f"{SERVICE_NAME}.service", unit)


def _write_journald_retention(ctx: contract.DeployContext) -> None:
    """Step 12 (retention) - size the journald window from the env-file knobs.

    Access + error logs share one journald stream, so a single window covers
    both; size it to max(ACCESS, ERROR) from the env file (the same values the
    backend reads) and document both as minimums. Written before the service
    starts so the policy is in force from first boot.
    """
    log_days = max(
        ctx.read_env_int(ACCESS_LOG_DAYS_ENV_VAR, ACCESS_LOG_DAYS_DEFAULT),
        ctx.read_env_int(ERROR_LOG_DAYS_ENV_VAR, ERROR_LOG_DAYS_DEFAULT),
    )
    journald_conf = f"""\
# Retention for the '{JOURNAL_NAMESPACE}' journal namespace ({SERVICE_NAME}.service).
# Managed by novotree install() - see PRIVACY_DESIGN.md section 3.3.
#
# Access logs and error logs are one stream, so this single window applies to
# both and is sized to max({ACCESS_LOG_DAYS_ENV_VAR}, {ERROR_LOG_DAYS_ENV_VAR})
# from {ctx.env_file_path}. The backend documents the per-category figures as minimums.
[Journal]
MaxRetentionSec={log_days}day
"""
    ctx.write_journald_conf(JOURNAL_NAMESPACE, journald_conf)
    # Apply the namespace policy. The namespaced journal is socket-activated the
    # first time the service logs, reading this conf then; on a re-run it may
    # already be up, so restart it to pick up a changed window. Non-fatal on a
    # first run (the instance may not exist yet - socket activation handles it).
    #
    subprocess.run(
        ["sudo", "systemctl", "restart", f"systemd-journald@{JOURNAL_NAMESPACE}.service"],
        check=False,
    )


def _register_backup_cron(ctx: contract.DeployContext) -> None:
    """Backup cron - runs in root's crontab so it can read the root:root 600 env
    file, sources it, then drops to the service user for the backup, forwarding
    BACKUP_CRON_PRESERVE_ENV_VARS across the sudo boundary. --require-env makes a
    missing var an error (logged + ops-notified) rather than a silent default.
    """
    env_file = ctx.env_file_path
    preserve = ",".join(BACKUP_CRON_PRESERVE_ENV_VARS)
    backup_cmd = (
        f'[ -f {env_file} ] || echo "[$(date \'+\\%Y-\\%m-\\%d \\%H:\\%M:\\%S\')] '
        f'ERROR: {env_file} missing — backup retention falls back to default"; '
        f"set -a; [ -f {env_file} ] && . {env_file}; set +a; "
        f"sudo -u {ctx.service_user} --preserve-env={preserve} "
        f"python3 {ctx.backup_script_path} --require-env"
        f" >> {BACKUP_LOG} 2>&1"
    )
    ctx.register_cron(BACKUP_CRON_USER, BACKUP_CRON_SCHEDULE, backup_cmd)


# -- App manifest (the only thing that crosses up to the deployer) ----------


def _post_install_notes(ctx: contract.DeployContext) -> list[str]:
    """Operator action items to print after a first install (post_install_notes).

    This is app knowledge - which secret novotree needs, why, and how to set it -
    so it lives here, not in the deployer. The deployer prints these verbatim.
    Empty on update(): these are one-time first-install actions.
    """
    return [f"""\
[ACTION REQUIRED] Set {JWT_SECRET_ENV_VAR} in {ctx.env_file_path}
  Why:  Novotree signs login tokens with this secret. Without it all
        authentication fails and nobody can log in.
  How:  1. Generate a secret key:
              python3 -c "import secrets; print(secrets.token_hex(32))"
        2. Edit the env file:
              sudo nano {ctx.env_file_path}
        3. Paste the generated value after:  {JWT_SECRET_ENV_VAR}=
        4. Restart the service to apply:
              sudo systemctl restart {SERVICE_NAME}"""]


def _manifest(ctx: contract.DeployContext, post_install_notes: list[str]) -> contract.AppManifest:
    """Routes + static dir the deployer wires into Caddy, plus any operator
    notes. Generic shapes only. `post_install_notes` is empty on update()."""
    return contract.AppManifest(
        routes=[
            # GEDCOM import - allow up to 2 GB (large family archives with media).
            contract.Route("/api/import/", BACKEND_PORT, strip_prefix="/api", max_body_size="2GB"),
            # novotree API - strip /api before forwarding to uvicorn.
            contract.Route("/api/", BACKEND_PORT, strip_prefix="/api"),
        ],
        static_dirs=[
            contract.StaticDir(FRONTEND_URL_PREFIX, source_dir=ctx.repo_dir / "frontend/dist",
                               spa_fallback=f"{FRONTEND_URL_PREFIX}index.html"),
        ],
        post_install_notes=post_install_notes,
    )


# -- The two seam entry points the deployer calls ---------------------------


def install(ctx: contract.DeployContext) -> contract.AppManifest:
    """Full first-time wiring of novotree on the VM (app steps 6-13 + cron)."""
    _print_step("env file")
    _write_env_file(ctx)
    _print_step("datasets tree")
    _setup_datasets_tree(ctx)
    _print_step("Python venv")
    _setup_venv(ctx)
    _print_step("frontend build")
    _build_frontend(ctx)
    _print_step("backup dir")
    _setup_backup_dir(ctx)
    _print_step("systemd service + journald retention")
    _write_service_unit(ctx)
    _write_journald_retention(ctx)
    ctx.reload_systemd()
    ctx.enable_service(SERVICE_NAME)
    ctx.restart_service(SERVICE_NAME)
    _verify_service_active(ctx)
    _print_step("backend-monitor backstop")
    backend_monitor.install_backend_monitor(ctx)
    _print_step("backup cron")
    _register_backup_cron(ctx)
    return _manifest(ctx, _post_install_notes(ctx))


def update(ctx: contract.DeployContext) -> contract.AppManifest:
    """Re-deploy after a code pull: rebuild + reinstall deps + restart + refresh
    units. Shares _build_frontend / _install_python_deps / _refresh_units_and_restart
    with install() so setup and update cannot drift. The deployer copies the
    returned static dir into its web root afterwards (same as on install)."""
    _print_step("frontend build")
    _build_frontend(ctx)
    _print_step("Python deps")
    _install_python_deps(ctx)
    _print_step("restart + refresh units")
    _refresh_units_and_restart(ctx)
    # No post_install_notes on update: those are one-time first-install actions.
    return _manifest(ctx, post_install_notes=[])


def _verify_service_active(ctx: contract.DeployContext) -> None:
    """Confirm the service actually started - systemctl restart returns 0 even
    if the process dies immediately after launch (e.g. bad WorkingDirectory)."""
    result = subprocess.run(
        ["sudo", "systemctl", "is-active", SERVICE_NAME],
        capture_output=True, text=True,
    )
    if result.stdout.strip() != "active":
        print(f"\n  ERROR: {SERVICE_NAME} service failed to start. Journal output:")
        subprocess.run(
            ["sudo", "journalctl", "--namespace", JOURNAL_NAMESPACE,
             "-u", SERVICE_NAME, "-n", "30", "--no-pager"],
        )
        sys.exit(1)
