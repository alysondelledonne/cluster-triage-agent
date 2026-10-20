from triage.evals.runner import check_gate, load_cases, main, summarize


def test_cases_file_is_valid() -> None:
    cases = load_cases()
    assert len(cases) >= 5
    assert len({c.id for c in cases}) == len(cases)


def test_fake_suite_passes_the_gate() -> None:
    # The golden fake model must score perfectly; if not, the pipeline is broken.
    assert main(["--provider", "fake", "--gate", "--no-save"]) == 0


def test_gate_catches_a_regression() -> None:
    rows = [
        {
            "answer_ok": True,
            "tool_ok": True,
            "answered": True,
            "steps": 2,
            "latency_s": 1.0,
            "cost_usd": 0.001,
        },
        {
            "answer_ok": False,
            "tool_ok": True,
            "answered": True,
            "steps": 2,
            "latency_s": 2.0,
            "cost_usd": 0.001,
        },
    ]
    summary = summarize(rows)
    assert summary["answer_accuracy"] == 0.5
    failures = check_gate(summary, {"answer_accuracy": 0.9, "tool_accuracy": 1.0})
    assert len(failures) == 1 and failures[0].startswith("answer_accuracy")


def test_unknown_cost_is_reported_as_none() -> None:
    rows = [
        {
            "answer_ok": True,
            "tool_ok": True,
            "answered": True,
            "steps": 1,
            "latency_s": 1.0,
            "cost_usd": None,
        }
    ]
    assert summarize(rows)["cost_per_run_usd"] is None
