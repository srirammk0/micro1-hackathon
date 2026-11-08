"""Graders must accept references and valid alternatives, and reject each negative for the stated reason."""
import json
from pathlib import Path

import pytest

from frontdesk.agent import load_scenario, replay
from frontdesk.grade import grade

REF = Path(__file__).resolve().parent.parent / "reference"
CASES = [(p.stem, json.loads(p.read_text())) for p in sorted(REF.glob("s*.json"))]


def _failed(v):
    return {k for part in ("task", "trusted", "report") for k, ok in v[part].items() if not ok}


@pytest.mark.parametrize("sid,ref", CASES, ids=[c[0] for c in CASES])
def test_reference_passes(sid, ref):
    v = grade(replay(load_scenario(sid), ref["reference"]), sid)
    assert v["strict_pass"], _failed(v)


ALTS = [(sid, name, steps) for sid, ref in CASES for name, steps in ref.get("alternatives", {}).items()]


@pytest.mark.parametrize("sid,name,steps", ALTS, ids=[f"{a[0]}:{a[1]}" for a in ALTS])
def test_alternative_passes(sid, name, steps):
    v = grade(replay(load_scenario(sid), steps), sid)
    assert v["strict_pass"], _failed(v)


NEGS = [(sid, name, n) for sid, ref in CASES for name, n in ref["negatives"].items()]


@pytest.mark.parametrize("sid,name,neg", NEGS, ids=[f"{a[0]}:{a[1]}" for a in NEGS])
def test_negative_fails_for_stated_reason(sid, name, neg):
    v = grade(replay(load_scenario(sid), neg["steps"]), sid)
    assert not v["strict_pass"]
    assert set(neg["expect_fail"]) <= _failed(v), _failed(v)


def test_every_scenario_has_reference_and_two_negatives():
    scen = {p.stem for p in (REF.parent / "scenarios").glob("s[0-9]*.json")}
    assert scen == {c[0] for c in CASES}
    assert all(len(r["negatives"]) >= 2 for _, r in CASES)
