"""The false-claim classifier must find none in reference solutions and catch the 'claims delivered' negative."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from false_claims import classify  # noqa: E402
from frontdesk.agent import load_scenario, replay  # noqa: E402
from frontdesk.grade import grade  # noqa: E402


def _rec(sid, steps):
    sb = replay(load_scenario(sid), steps)
    st = {"clients": sb.clients, "appointments": sb.appts, "followups": sb.followups, "threads": sb.threads,
          "drafts": sb.drafts, "owner_inbox": sb.owner_inbox, "report": sb.report,
          "now": sb.now.strftime("%Y-%m-%d %H:%M")}
    return {"scenario": sid, "final_state": st, "log": sb.log, "grade": grade(sb, sid)}


def test_references_have_no_false_claims():
    for p in sorted((ROOT / "reference").glob("s*.json")):
        sid = p.stem
        assert classify(_rec(sid, json.loads(p.read_text())["reference"])) == ([], []), sid


def test_claims_delivered_is_a_fabrication():
    neg = json.loads((ROOT / "reference" / "s04_delivery_failure.json").read_text())["negatives"]["claims_delivered"]
    fab, _ = classify(_rec("s04_delivery_failure", neg["steps"]))
    assert fab
