"""
Backstop wrapper for the takedown SLA sweep.

The real sweep lives in backend.api._takedown_sweep.sweep_once — this file
exists so the scheduled_jobs runner can dispatch to it by import. Do not
duplicate sweep logic here.
"""

import asyncio
import logging

from backend.api._takedown_sweep import sweep_once
from database.system_db import get_system_session, init_system_db

logger = logging.getLogger("novotree.privacy")

JOB_NAME = "takedown_requests_monitor"


async def _run_async() -> dict[str, int]:
    init_system_db()
    db = get_system_session()
    try:
        return await sweep_once(db)
    finally:
        db.close()


def run() -> None:
    """Synchronous entry point invoked by scheduled_jobs.py."""
    counts = asyncio.run(_run_async())
    if any(counts.values()):
        logger.info(
            "%s: %d reminder(s), %d escalation(s), %d retention delete(s)",
            JOB_NAME,
            counts["reminders_sent"],
            counts["escalations_sent"],
            counts["retention_deleted"],
        )
    else:
        logger.info("%s: nothing to do", JOB_NAME)
