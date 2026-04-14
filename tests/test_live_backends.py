from __future__ import annotations

import os
from pathlib import Path

import pytest

from orchestro.backend_profiles import build_default_backends, is_backend_temporarily_unavailable_error
from orchestro.models import RunRequest
from orchestro.orchestrator import Orchestro


pytestmark = [pytest.mark.live]


def _selected_live_backends() -> list[str]:
    raw = os.environ.get("ORCHESTRO_LIVE_BACKENDS", "codex,kilocode,claude-code,cursor")
    return [item.strip() for item in raw.split(",") if item.strip()]


@pytest.mark.skipif(
    os.environ.get("ORCHESTRO_RUN_LIVE_BACKEND_TESTS") != "1",
    reason="set ORCHESTRO_RUN_LIVE_BACKEND_TESTS=1 to enable live backend smoke tests",
)
@pytest.mark.parametrize("backend_name", _selected_live_backends())
def test_live_backend_smoke(tmp_db, backend_name):
    backends = build_default_backends()
    if backend_name not in backends:
        pytest.skip(f"backend '{backend_name}' is not configured")

    backend = backends[backend_name]
    capabilities = backend.capabilities()
    if not capabilities.get("available", True):
        pytest.skip(f"backend '{backend_name}' is not installed or reachable in this environment")

    orch = Orchestro(db=tmp_db, backends={backend_name: backend})
    request = RunRequest(
        goal="Reply with exactly the single word PONG.",
        backend_name=backend_name,
        working_directory=Path.cwd(),
    )
    try:
        run_id = orch.run(request)
    except RuntimeError as exc:
        if is_backend_temporarily_unavailable_error(str(exc)):
            pytest.skip(str(exc))
        raise

    run = orch.db.get_run(run_id)
    assert run is not None
    assert run.status == "done"
    assert "pong" in (run.final_output or "").lower()

