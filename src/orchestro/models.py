from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RunRequest:
    goal: str
    backend_name: str
    strategy_name: str = "direct"
    working_directory: Path = field(default_factory=Path.cwd)
    parent_run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BackendResponse:
    output_text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RatingRequest:
    target_type: str
    target_id: str
    rating: str
    note: str | None = None
