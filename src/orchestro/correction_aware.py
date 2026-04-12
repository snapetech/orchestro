from __future__ import annotations

from orchestro.db import OrchestroDB


def should_elevate_approval(
    tool_name: str,
    tool_args: str,
    run_id: str,
    db: OrchestroDB,
) -> tuple[bool, str]:
    """Check if a retrieved correction suggests extra caution for this tool call."""
    events = db.list_events(run_id)
    retrieval_event = None
    for event in events:
        if event.get("event_type") == "retrieval_built":
            retrieval_event = event
            break
    if retrieval_event is None:
        return False, ""

    payload = retrieval_event.get("payload", {})
    correction_count = payload.get("correction_count", 0)
    if correction_count == 0:
        return False, ""

    corrections = db.list_corrections(limit=20)
    for correction in corrections:
        context_lower = (correction.context or "").lower()
        wrong_lower = (correction.wrong_answer or "").lower()
        if tool_name.lower() in context_lower or tool_name.lower() in wrong_lower:
            return True, f"Relevant correction: {(correction.context or '')[:100]}"
        key_args = [a for a in tool_args.split() if len(a) > 3]
        for arg in key_args[:3]:
            if arg.lower() in context_lower:
                return True, f"Correction mentions '{arg}': {(correction.context or '')[:100]}"

    return False, ""
