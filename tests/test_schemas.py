import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from omnitrix.core.events import make_event
from omnitrix.core.schemas import (EXPORTED, ApprovalRequest, MeetingRequest, Task, TaskCandidateList,
                                   inline_schema)

EXAMPLES = Path(__file__).resolve().parents[1] / "schemas" / "examples"


@pytest.mark.parametrize("name", sorted(p.stem for p in EXAMPLES.glob("*.json")))
def test_examples_match_their_format(name):
    EXPORTED[name].model_validate_json((EXAMPLES / f"{name}.json").read_text())


def test_every_exported_format_has_an_example():
    assert {p.stem for p in EXAMPLES.glob("*.json")} >= {"event", "task_candidate_list", "task", "meeting_request",
                                                          "approval_request", "board_message"}


def test_inline_schema_has_no_refs_left():
    for model in (TaskCandidateList, Task, MeetingRequest, ApprovalRequest):
        text = json.dumps(inline_schema(model))
        assert "$ref" not in text and "$defs" not in text


def test_unknown_event_types_are_rejected(clock):
    with pytest.raises(ValidationError):
        make_event("email.recieved", emitted_by="test", clock=clock)


def test_make_event_inherits_the_story_from_its_cause(clock):
    first = make_event("email.received", emitted_by="ingestion", clock=clock, correlation_id="story_mr_4",
                       idempotency_key="email.received:<abc@mehtatraders.example>")
    second = make_event("meeting_request.detected", emitted_by="librarian", clock=clock, caused_by=first,
                        subject=("meeting_request", "mr_4"), priority="high")
    assert second.correlation_id == "story_mr_4"
    assert second.caused_by == first.event_id
    assert second.idempotency_key == second.event_id
    assert second.occurred_at == clock.now()


def test_candidates_reject_extra_fields_and_bad_confidence():
    with pytest.raises(ValidationError):
        TaskCandidateList.model_validate({"tasks": [{"title": "x", "action_type": "send", "evidence_quote": "x",
                                                     "confidence": 1.5}]})
    with pytest.raises(ValidationError):
        TaskCandidateList.model_validate({"tasks": [{"title": "x", "action_type": "send", "evidence_quote": "x",
                                                     "confidence": 0.5, "priority": "high"}]})
