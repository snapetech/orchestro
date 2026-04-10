from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    raw = os.environ.get("ORCHESTRO_HOME")
    base = Path(raw).expanduser() if raw else project_root() / ".orchestro"
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_path() -> Path:
    return data_dir() / "orchestro.db"
