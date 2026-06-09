"""
systemd-unit definitions for novotree-backend-monitor.{service,timer}.

The backend-monitor pair is a *backstop* for the in-process scheduler that lives
inside the novotree backend. It exists so SLA-driven privacy work
(privacy-request reminders, escalations) does not stall when the backend is down
for maintenance or an outage, AND so unconditional jobs (the section 3.4 error-log
digest) run on a timer regardless of backend health.

  novotree-backend-monitor.timer    - fires every 15 minutes.
  novotree-backend-monitor.service  - oneshot; runs scheduled_jobs.py which runs
                                      the unconditional jobs, then probes
                                      http://127.0.0.1:8000/health and either
                                      exits (backend healthy) or dispatches the
                                      backstop jobs.

Idempotency at the data layer (DB-level claim on `privacy_requests` rows) means
a brief overlap with the in-process scheduler cannot double-send mail.
"""

from __future__ import annotations

from pathlib import Path

SERVICE_NAME = "novotree-backend-monitor.service"
TIMER_NAME = "novotree-backend-monitor.timer"

# Surfaced by install()/update() callers so the warning text is one source of
# truth. Printed at the end of a setup/update run.
#
IMPORTANCE_WARNING = (
    "PRIVACY: novotree-backend-monitor.timer is the backstop that runs SLA-driven\n"
    "  privacy work (privacy-request reminders, escalations) while the backend is\n"
    "  down. If the timer is not enabled, in-flight privacy requests will silently\n"
    "  miss their 14-day reminder and 30-day escalation deadlines during any\n"
    "  backend outage — a regulatory risk. Verify with:\n"
    "    systemctl list-timers novotree-backend-monitor.timer\n"
)


def _service_unit(service_user: str, repo_dir: Path, env_file: Path) -> str:
    return f"""\
[Unit]
Description=Backstop runner for novotree scheduled jobs (privacy SLA sweep, etc.)
After=network.target
# Cheap belt-and-suspenders: idempotency lives in the job DB, but tagging the
# unit's relationship to the backend documents intent.
Documentation=https://github.com/ketafoto/novotree/blob/main/docs/PRIVACY_DESIGN.md

[Service]
Type=oneshot
User={service_user}
WorkingDirectory={repo_dir}
EnvironmentFile={env_file}
ExecStart={repo_dir}/.venv/bin/python -m tools.ops.scheduled_jobs.scheduled_jobs

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths={repo_dir}/datasets
"""


def _timer_unit() -> str:
    return """\
[Unit]
Description=Periodic trigger for novotree-backend-monitor.service

[Timer]
# First fire 5 min after boot to give the backend a chance to come up
# (the monitor will then no-op if the backend health probe succeeds).
OnBootSec=5min
# Then every 15 min thereafter. Picked to be short enough that an outage
# starting just after a tick still gets a sweep within the same hour, and
# long enough that the no-op path costs ~ms of CPU per day.
OnUnitActiveSec=15min
Unit=novotree-backend-monitor.service

[Install]
WantedBy=timers.target
"""


def install_backend_monitor(ctx) -> None:
    """Write the backend-monitor unit files and enable the timer. Idempotent.

    `ctx` is a contract.DeployContext - we use its generic toolkit
    (write_systemd_unit / reload_systemd / enable_service) so this app wiring
    needs no deployer internals. Called by both install() and update() so a
    change to either unit file lands on the next deploy without manual steps.
    """
    ctx.write_systemd_unit(
        SERVICE_NAME,
        _service_unit(ctx.service_user, ctx.repo_dir, ctx.env_file_path),
    )
    ctx.write_systemd_unit(TIMER_NAME, _timer_unit())
    ctx.reload_systemd()
    ctx.enable_service(TIMER_NAME, now=True)
