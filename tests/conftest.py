from __future__ import annotations

import pytest
from pathlib import Path

from orchestro.backend_profiles import clear_backend_cooldowns
from orchestro.db import OrchestroDB


@pytest.fixture()
def tmp_db(tmp_path: Path) -> OrchestroDB:
    return OrchestroDB(tmp_path / "test.db")


@pytest.fixture(autouse=True)
def clear_backend_cooldowns_fixture():
    clear_backend_cooldowns()
    yield
    clear_backend_cooldowns()
