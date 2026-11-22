"""On-demand atomic simulation snapshot persistence returning RunSummary DTOs."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from hefesto.domain import RunSummary, SimulationResult
from hefesto.storage.paths import (
    StoragePaths,
    atomic_write_text,
    resolve_safe_relative_path,
    resolve_storage_paths,
    validate_safe_slug,
)


def _utc_sort_key(summary: RunSummary) -> tuple[datetime, str]:
    dt = summary.created_at_utc
    normalized = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    return (normalized, summary.run_id)


class RunStore:
    """On-demand JSON snapshot store under data/runs/ (never creates directory eagerly)."""

    def __init__(self, paths: StoragePaths | None = None) -> None:
        self.paths = resolve_storage_paths() if paths is None else paths

    @property
    def runs_dir(self) -> Path:
        return self.paths.runs_dir

    def _normalize_run_id(self, run_id: str) -> str:
        stripped = run_id.strip()
        stem = stripped.removesuffix(".json") if stripped.endswith(".json") else stripped
        return validate_safe_slug(stem, "run_id")

    def save_run(self, result: SimulationResult) -> RunSummary:
        """Persist a full SimulationResult snapshot atomically and return its RunSummary."""
        slug = validate_safe_slug(result.run_id, "run_id")
        snapshot_asset = f"{slug}.json"
        target = resolve_safe_relative_path(self.runs_dir, snapshot_asset)
        atomic_write_text(target, result.model_dump_json(indent=2) + "\n")
        return result.to_summary(snapshot_asset=snapshot_asset)

    def load_run(self, run_id: str) -> SimulationResult:
        """Load a persisted SimulationResult snapshot by run_id or snapshot filename."""
        slug = self._normalize_run_id(run_id)
        target = resolve_safe_relative_path(self.runs_dir, f"{slug}.json")
        if not target.is_file():
            raise FileNotFoundError(f"Run snapshot not found: {slug!r}")
        return SimulationResult.model_validate_json(target.read_text(encoding="utf-8"))

    def list_runs(self) -> tuple[RunSummary, ...]:
        """List saved snapshots newest-first as compact RunSummary DTOs."""
        if not self.runs_dir.is_dir():
            return ()
        resolved_dir = self.runs_dir.resolve()
        summaries: list[RunSummary] = []

        for entry in sorted(self.runs_dir.glob("*.json")):
            if not entry.is_file() or not entry.resolve().is_relative_to(resolved_dir):
                continue
            result = SimulationResult.model_validate_json(entry.read_text(encoding="utf-8"))
            summaries.append(result.to_summary(snapshot_asset=entry.name))

        summaries.sort(key=_utc_sort_key, reverse=True)
        return tuple(summaries)


__all__ = ["RunStore"]
