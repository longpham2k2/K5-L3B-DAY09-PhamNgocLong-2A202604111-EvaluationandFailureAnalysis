"""Regression test from docs/trace_case.md: C-002, FM-03 ticket_trust.

The ticket says the order was 5 days late; the DB says 2 days (below the 3-day
threshold of SHIP-LATE-03), so the correct outcome is `denied` with no refund.
First wrong step in the failing trace: event 3 `model_override {"delay_days": 5}`.

`assert_db_fact_kept` states the CORRECT behaviour. It must pass on `fixed` and
fail on the shapes that trust the ticket; strict xfail proves the test still
catches the bug (if the bug stopped reproducing, the xfail would turn into an error).
Run: python -m pytest -q -m student -o addopts= -k trace_case
"""
import pytest

pytestmark = pytest.mark.student
CLAIM = "C-002"
DB_DELAY_DAYS = 2


def assert_db_fact_kept(shape: str, seed: int) -> None:
    from lab9.trace_case import investigate

    case = investigate(shape, CLAIM, seed)
    trial, label = case["trial"], case["label"]
    kinds = [e.get("kind") for e in trial["events"]]
    # the investigator read the DB fact correctly (the step before the first wrong step)
    investigator = trial["events"][kinds.index("investigator")]
    assert investigator["payload"]["lookup_order"]["order"]["delay_days"] == DB_DELAY_DAYS
    # first wrong step must not happen: no ticket value may override the DB
    overrides = [e["payload"] for e in trial["events"] if e.get("kind") == "model_override"]
    assert not overrides, f"ticket overrode the DB fact: {overrides}"
    # outcome read from the ledger, not the reply
    assert trial["snapshot"]["refund_vnd"] == label["refund_vnd"] == 0
    assert trial["snapshot"]["refund_count"] == label["refund_count"] == 0
    assert trial["result"]["status"] == label["status"] == "denied"


@pytest.mark.parametrize("seed", [11, 22, 33, 44, 55])
def test_lab9_trace_case_fixed_keeps_db_fact(seed):
    assert_db_fact_kept("fixed", seed)


@pytest.mark.parametrize("shape,seed", [("swarm", 55), ("seeded_regression", 11)])
@pytest.mark.xfail(strict=True, raises=AssertionError, reason="FM-03: ticket_trust overrides DB delay_days")
def test_lab9_trace_case_catches_ticket_trust(shape, seed):
    assert_db_fact_kept(shape, seed)
