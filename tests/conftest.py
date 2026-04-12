from __future__ import annotations

import pytest
from pathlib import Path

from orchestro.db import OrchestroDB


@pytest.fixture()
def tmp_db(tmp_path: Path) -> OrchestroDB:
    return OrchestroDB(tmp_path / "test.db")
