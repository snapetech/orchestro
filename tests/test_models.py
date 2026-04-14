from __future__ import annotations

from pathlib import Path

from orchestro.models import BackendResponse, RatingRequest, RunRequest


class TestRunRequest:
    def test_required_fields(self):
        r = RunRequest(goal="do something", backend_name="mock")
        assert r.goal == "do something"
        assert r.backend_name == "mock"

    def test_strategy_default(self):
        r = RunRequest(goal="g", backend_name="mock")
        assert r.strategy_name == "direct"

    def test_working_directory_default_is_cwd(self):
        r = RunRequest(goal="g", backend_name="mock")
        assert r.working_directory == Path.cwd()

    def test_working_directory_can_be_set(self):
        r = RunRequest(goal="g", backend_name="mock", working_directory=Path("/tmp"))
        assert r.working_directory == Path("/tmp")

    def test_optional_fields_default_none(self):
        r = RunRequest(goal="g", backend_name="mock")
        assert r.parent_run_id is None
        assert r.system_prompt is None
        assert r.prompt_context is None
        assert r.stable_prefix is None

    def test_metadata_default_empty_dict(self):
        r = RunRequest(goal="g", backend_name="mock")
        assert r.metadata == {}

    def test_metadata_not_shared_between_instances(self):
        r1 = RunRequest(goal="g1", backend_name="mock")
        r2 = RunRequest(goal="g2", backend_name="mock")
        r1.metadata["x"] = 1
        assert "x" not in r2.metadata

    def test_autonomous_default_false(self):
        r = RunRequest(goal="g", backend_name="mock")
        assert r.autonomous is False

    def test_all_fields_settable(self):
        r = RunRequest(
            goal="my goal",
            backend_name="vllm-fast",
            strategy_name="tool-loop",
            working_directory=Path("/workspace"),
            parent_run_id="parent-123",
            metadata={"domain": "coding"},
            system_prompt="Be concise.",
            prompt_context="Prior context here.",
            stable_prefix="Stable prefix.",
            autonomous=True,
        )
        assert r.goal == "my goal"
        assert r.backend_name == "vllm-fast"
        assert r.strategy_name == "tool-loop"
        assert r.working_directory == Path("/workspace")
        assert r.parent_run_id == "parent-123"
        assert r.metadata == {"domain": "coding"}
        assert r.system_prompt == "Be concise."
        assert r.prompt_context == "Prior context here."
        assert r.stable_prefix == "Stable prefix."
        assert r.autonomous is True


class TestBackendResponse:
    def test_required_output_text(self):
        r = BackendResponse(output_text="hello")
        assert r.output_text == "hello"

    def test_token_counts_default_zero(self):
        r = BackendResponse(output_text="x")
        assert r.prompt_tokens == 0
        assert r.completion_tokens == 0
        assert r.total_tokens == 0
        assert r.cache_read_tokens == 0
        assert r.cache_write_tokens == 0

    def test_metadata_default_empty(self):
        r = BackendResponse(output_text="x")
        assert r.metadata == {}

    def test_metadata_not_shared(self):
        r1 = BackendResponse(output_text="a")
        r2 = BackendResponse(output_text="b")
        r1.metadata["k"] = "v"
        assert "k" not in r2.metadata

    def test_all_fields_settable(self):
        r = BackendResponse(
            output_text="result",
            metadata={"backend": "mock"},
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cache_read_tokens=20,
            cache_write_tokens=10,
        )
        assert r.prompt_tokens == 100
        assert r.completion_tokens == 50
        assert r.total_tokens == 150
        assert r.cache_read_tokens == 20
        assert r.cache_write_tokens == 10


class TestRatingRequest:
    def test_required_fields(self):
        r = RatingRequest(target_type="run", target_id="abc", rating="good")
        assert r.target_type == "run"
        assert r.target_id == "abc"
        assert r.rating == "good"

    def test_note_defaults_none(self):
        r = RatingRequest(target_type="run", target_id="abc", rating="good")
        assert r.note is None

    def test_note_can_be_set(self):
        r = RatingRequest(target_type="run", target_id="abc", rating="bad", note="Too verbose")
        assert r.note == "Too verbose"
