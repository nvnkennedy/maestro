"""Executor helper logic unit tests (no DB required)."""

from backend.services.test_executor import TestExecutor as ExecutorImpl


def test_placeholder_substitution():
    outputs = {1: "hello-world", 2: "second"}
    params = {
        "message": "got: {{steps.1.output}}",
        "nested": {"value": "{{steps.2.output}}"},
        "list": ["{{steps.1.output}}", 42],
        "untouched": 7,
    }
    result = ExecutorImpl._substitute_placeholders(params, outputs)
    assert result["message"] == "got: hello-world"
    assert result["nested"]["value"] == "second"
    assert result["list"] == ["hello-world", 42]
    assert result["untouched"] == 7


def test_condition_matched_jumps():
    outputs = {1: "ERROR: something broke"}
    condition = {"source_step": 1, "contains": "ERROR", "skip_to": 5}
    assert ExecutorImpl._evaluate_condition(condition, outputs) == 5


def test_condition_not_matched_else_branch():
    outputs = {1: "all good"}
    condition = {
        "source_step": 1,
        "contains": "ERROR",
        "skip_to": 5,
        "else_skip_to": 9,
    }
    assert ExecutorImpl._evaluate_condition(condition, outputs) == 9


def test_condition_no_jump():
    outputs = {1: "all good"}
    condition = {"source_step": 1, "contains": "ERROR", "skip_to": 5}
    assert ExecutorImpl._evaluate_condition(condition, outputs) is None


def test_index_for_step_number():
    steps = [{"step_number": 1}, {"step_number": 3}, {"step_number": 7}]
    assert ExecutorImpl._index_for_step_number(steps, 3) == 1
    assert ExecutorImpl._index_for_step_number(steps, 99) is None

