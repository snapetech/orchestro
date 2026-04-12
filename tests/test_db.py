from __future__ import annotations

from orchestro.db import OrchestroDB


def test_create_run_get_run_roundtrip(tmp_db: OrchestroDB):
    tmp_db.create_run(
        run_id="run-1",
        goal="say hello",
        backend_name="mock",
        strategy_name="direct",
        working_directory="/tmp",
    )
    run = tmp_db.get_run("run-1")
    assert run is not None
    assert run.id == "run-1"
    assert run.goal == "say hello"
    assert run.status == "running"
    assert run.backend_name == "mock"
    assert run.strategy_name == "direct"


def test_complete_run_updates_status(tmp_db: OrchestroDB):
    tmp_db.create_run(
        run_id="run-2",
        goal="complete me",
        backend_name="mock",
        strategy_name="direct",
        working_directory="/tmp",
    )
    tmp_db.complete_run(run_id="run-2", final_output="done!")
    run = tmp_db.get_run("run-2")
    assert run is not None
    assert run.status == "done"
    assert run.final_output == "done!"
    assert run.completed_at is not None


def test_fail_run_updates_status_and_error(tmp_db: OrchestroDB):
    tmp_db.create_run(
        run_id="run-3",
        goal="fail me",
        backend_name="mock",
        strategy_name="direct",
        working_directory="/tmp",
    )
    tmp_db.fail_run(
        run_id="run-3",
        error_message="something broke",
        failure_category="tool_crash",
        recovery_attempts=2,
    )
    run = tmp_db.get_run("run-3")
    assert run is not None
    assert run.status == "failed"
    assert run.error_message == "something broke"
    assert run.failure_category == "tool_crash"
    assert run.recovery_attempts == 2


def test_add_rating_and_list(tmp_db: OrchestroDB):
    tmp_db.create_run(
        run_id="run-r",
        goal="rate me",
        backend_name="mock",
        strategy_name="direct",
        working_directory="/tmp",
    )
    tmp_db.complete_run(run_id="run-r", final_output="output")
    tmp_db.add_rating(
        rating_id="rat-1",
        target_type="run",
        target_id="run-r",
        rating="thumbs_up",
        note="good job",
    )
    interactions = tmp_db.list_interactions(limit=10)
    rated = [i for i in interactions if i.rating == "thumbs_up"]
    assert len(rated) == 1
    assert rated[0].run_id == "run-r"


def test_add_interaction_and_fts_search(tmp_db: OrchestroDB):
    tmp_db.create_run(
        run_id="run-fts",
        goal="explain quantum entanglement",
        backend_name="mock",
        strategy_name="direct",
        working_directory="/tmp",
    )
    tmp_db.complete_run(run_id="run-fts", final_output="particles are correlated")
    hits = tmp_db.search(query="quantum", kind="interactions", limit=5)
    assert len(hits) >= 1
    assert any("quantum" in h.title.lower() or "quantum" in h.snippet.lower() for h in hits)


def test_add_fact_and_list_facts(tmp_db: OrchestroDB):
    tmp_db.add_fact(
        fact_id="fact-1",
        fact_key="preferred_language",
        fact_value="Python",
        source="user",
    )
    tmp_db.add_fact(
        fact_id="fact-2",
        fact_key="editor",
        fact_value="neovim",
        source="user",
    )
    facts = tmp_db.list_facts(limit=10)
    assert len(facts) == 2
    keys = {f.fact_key for f in facts}
    assert "preferred_language" in keys
    assert "editor" in keys

    filtered = tmp_db.list_facts(limit=10, key="language")
    assert len(filtered) == 1
    assert filtered[0].fact_value == "Python"


def test_add_correction_and_list_corrections(tmp_db: OrchestroDB):
    tmp_db.add_correction(
        correction_id="corr-1",
        context="user asked about Python version",
        wrong_answer="Python 2 is latest",
        right_answer="Python 3 is latest",
        domain="coding",
        severity="normal",
        source_run_id=None,
    )
    corrections = tmp_db.list_corrections(limit=10)
    assert len(corrections) == 1
    assert corrections[0].wrong_answer == "Python 2 is latest"
    assert corrections[0].right_answer == "Python 3 is latest"
    assert corrections[0].domain == "coding"


def test_create_plan_get_plan_list_plan_steps(tmp_db: OrchestroDB):
    tmp_db.create_plan(
        plan_id="plan-1",
        goal="build a widget",
        backend_name="mock",
        strategy_name="direct",
        working_directory="/tmp",
        domain=None,
        steps=[
            ("design", "sketch the widget"),
            ("implement", "write the code"),
            ("test", None),
        ],
    )
    plan = tmp_db.get_plan("plan-1")
    assert plan is not None
    assert plan.goal == "build a widget"
    assert plan.status == "draft"
    assert plan.current_step_no == 1

    steps = tmp_db.list_plan_steps("plan-1")
    assert len(steps) == 3
    assert steps[0].title == "design"
    assert steps[0].details == "sketch the widget"
    assert steps[1].title == "implement"
    assert steps[2].title == "test"
    assert steps[2].details is None


def test_update_run_token_usage_accumulates(tmp_db: OrchestroDB):
    tmp_db.create_run(
        run_id="run-tok",
        goal="token test",
        backend_name="mock",
        strategy_name="direct",
        working_directory="/tmp",
    )
    tmp_db.update_run_token_usage(
        run_id="run-tok",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
    )
    tmp_db.update_run_token_usage(
        run_id="run-tok",
        prompt_tokens=200,
        completion_tokens=80,
        total_tokens=280,
    )
    run = tmp_db.get_run("run-tok")
    assert run is not None
    assert run.prompt_tokens == 300
    assert run.completion_tokens == 130
    assert run.total_tokens == 430
