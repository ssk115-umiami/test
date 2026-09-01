"""Tracks whether a real DataAdapter has ever actually succeeded against
live data, separately from how well-documented its source is.

A real adapter can be carefully built from cross-checked documentation
and still be wrong (wrong path, changed format, auth requirement) until
it has actually been run. This module is the mechanism, not just a
docstring claim: `mark_verified` is called only after a real fetch+load
completes AND produces a schema-conformant, quality-passing frame, and
the record persists (one JSON file per cache_dir) so `verification_status`
can be checked later — by the orchestrator, the reporter, or a human.

Never call `mark_verified` from a synthetic adapter or from a mocked/
stubbed test of a real adapter — that would defeat the entire point.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pydantic import BaseModel

VERIFICATION_FILENAME = ".verified.json"


class VerificationRecord(BaseModel):
    source_name: str
    verified: bool
    verified_at: str | None = None
    notes: str = ""


def mark_verified(cache_dir: Path, source_name: str, notes: str = "") -> VerificationRecord:
    cache_dir.mkdir(parents=True, exist_ok=True)
    record = VerificationRecord(
        source_name=source_name,
        verified=True,
        verified_at=str(pd.Timestamp.now("UTC")),
        notes=notes,
    )
    (cache_dir / VERIFICATION_FILENAME).write_text(record.model_dump_json(indent=2))
    return record


def verification_status(cache_dir: Path, source_name: str) -> VerificationRecord:
    path = cache_dir / VERIFICATION_FILENAME
    if not path.exists():
        return VerificationRecord(
            source_name=source_name,
            verified=False,
            notes="no successful real fetch+load has been recorded from this environment yet",
        )
    return VerificationRecord.model_validate_json(path.read_text())
