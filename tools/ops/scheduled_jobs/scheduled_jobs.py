#!/usr/bin/env python3
"""
Backstop runner for scheduled in-backend jobs.

The NovoTree backend runs a few periodic activities in-process (currently:
the privacy-request SLA sweep). When the backend is down - planned
maintenance or unplanned outage - those activities stall.

This script is the safety net. It is invoked periodically by systemd
(novotree-backend-monitor.timer fires novotree-backend-monitor.service every
15 min, which calls this script). On each run it:

  1. Runs UNCONDITIONAL_JOBS - jobs that must run regardless of backend health
     (currently the error-log digest, PRIVACY_DESIGN.md section 3.4). These
     self-throttle to their own cadence, so the 15-min tick mostly no-ops them.
  2. Probes the backend's /health endpoint.
  3. If the backend is healthy -> skips BACKSTOP_JOBS. The backend is doing
     that work in-process.
  4. If the backend is unreachable -> runs each BACKSTOP_JOBS entry.

Always exits 0 on job-level problems (see main()).

Backstop jobs are idempotent (DB-level claim via UPDATE ... WHERE ... IS NULL)
so a brief overlap with the in-process scheduler cannot cause double-sends.

Logs to stdout; systemd captures and routes to journalctl. Use:

    journalctl -u novotree-backend-monitor.service -f

to follow live, or:

    python3 -m tools.ops.scheduled_jobs.scheduled_jobs --force

to run all jobs unconditionally (debugging).
"""

import argparse
import logging
import sys
import urllib.error
import urllib.request

# Each job is a module exposing run() (and optionally JOB_NAME).
from tools.ops.scheduled_jobs.jobs import error_log_digest, privacy_requests_monitor

# Run on every tick, before the health gate - these report on the running
# system (error-log digest) and self-throttle to their own cadence.
#
UNCONDITIONAL_JOBS = [error_log_digest]

# Backstop jobs: run only when the backend is down (the in-process scheduler
# handles these while it is up). Idempotent at the DB layer.
#
BACKSTOP_JOBS = [privacy_requests_monitor]

HEALTH_URL = "http://127.0.0.1:8000/health"
HEALTH_TIMEOUT_SECONDS = 5


def _setup_logging() -> None:
    # Plain stdout — systemd timestamps and routes to journalctl. No file
    # handler: writing to a file from a oneshot would create permission and
    # rotation headaches the journal already solves.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )


def _backend_is_healthy() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=HEALTH_TIMEOUT_SECONDS) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False


def _run_jobs(jobs) -> int:
    log = logging.getLogger("novotree.scheduled_jobs")
    failures = 0
    for job in jobs:
        name = getattr(job, "JOB_NAME", job.__name__)
        try:
            job.run()
        except Exception:
            log.exception("%s: failed", name)
            failures += 1
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run jobs even when the backend appears healthy (debugging).",
    )
    args = parser.parse_args()

    _setup_logging()
    log = logging.getLogger("novotree.scheduled_jobs")

    # Always-run phase - independent of backend health (self-throttling jobs).
    failures = _run_jobs(UNCONDITIONAL_JOBS)

    if not args.force and _backend_is_healthy():
        log.info("backend healthy at %s - skipping backstop jobs", HEALTH_URL)
        if failures:
            log.warning("%d unconditional job(s) failed; check log above", failures)
        return 0

    log.info("backend not reachable at %s - running %d backstop job(s)",
             HEALTH_URL, len(BACKSTOP_JOBS))
    failures += _run_jobs(BACKSTOP_JOBS)
    if failures:
        log.warning("%d job(s) failed; check log above", failures)
    # Exit 0 even on job failure: systemd's "service failed" status is for
    # runner-level problems (cannot import, cannot reach DB), not for an
    # individual job that hit a transient SMTP error. The job logs its own
    # failure and the next timer tick will retry.
    return 0


if __name__ == "__main__":
    sys.exit(main())
