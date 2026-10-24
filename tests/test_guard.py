from datetime import datetime, timezone

from interviewos.guard import evaluate_guard
from interviewos.match import score_job
from interviewos.models import CaseRecord, Contact, Evidence, Intro, JobHit, Mandate, Score
from interviewos.profile import proof_lines
from interviewos.store import Store, TransitionError
from interviewos.synthetic import reresolve_stale_contact, stale_contact_case
from interviewos.textutil import classify_reply, excerpt_in_source
import pytest


def _evidence() -> Evidence:
    return Evidence(
        id="ev_1",
        entity_id="job-1",
        source="crustdata.job",
        field="job_details.title",
        excerpt="Product Manager at Northwind.",
        retrieved_at="2026-10-24T08:00:00+00:00",
        source_date="2026-10-20",
        evidence_type="job_posting",
        mode="LIVE DATA",
    )


def _case() -> CaseRecord:
    evidence = [
        _evidence(),
        Evidence(
            id="ev_2",
            entity_id="candidate",
            source="user.resume",
            field="resume_line",
            excerpt="Shipped an enterprise AI deployment program.",
            retrieved_at="2026-10-24T08:00:00+00:00",
            evidence_type="resume_proof",
            mode="LIVE DATA",
        ),
    ]
    return CaseRecord(
        id="case1",
        mode="LIVE DATA",
        state="ready",
        opportunity_type="verified_opening",
        company_name="Northwind",
        role_title="Product Manager",
        contact=Contact(
            name="Meera Shah",
            title="Talent Partner",
            company_name="Northwind",
            company_id=1,
            route="recruiter",
            resolved=True,
            affiliation_verified=True,
        ),
        evidence=evidence,
        intro=Intro(subject="Hello", body="A short note.", evidence_ids=["ev_1", "ev_2"]),
        score=Score(role_fit=35, proof=30, timing=20, contact=15),
        candidate_name="Hritik",
        recipient_email="meera@northwind.example",
        recipient_source="mandate",
        created_at="2026-10-24T08:00:00+00:00",
        updated_at="2026-10-24T08:00:00+00:00",
    )


def test_guard_blocks_missing_mandate_and_bad_evidence():
    case = _case()
    reasons = evaluate_guard(case, Mandate(saved=False, recipient_email=case.recipient_email or ""))
    assert any("mandate" in reason.lower() for reason in reasons)

    case.intro.evidence_ids.append("ev_missing")
    reasons = evaluate_guard(
        case,
        Mandate(saved=True, recipient_email="meera@northwind.example"),
    )
    assert any("ev_missing" in reason for reason in reasons)


def test_guard_blocks_stale_affiliation_and_recipient_outside_mandate():
    case = _case()
    case.contact.affiliation_verified = False
    mandate = Mandate(saved=True, recipient_email="meera@northwind.example")
    reasons = evaluate_guard(case, mandate)
    assert any("does not match" in reason for reason in reasons)

    case.contact.affiliation_verified = True
    case.recipient_email = "other@example.com"
    reasons = evaluate_guard(case, mandate)
    assert any("outside" in reason for reason in reasons)


def test_guard_allows_a_complete_case():
    reasons = evaluate_guard(
        _case(),
        Mandate(saved=True, recipient_email="meera@northwind.example"),
    )
    assert reasons == []


def test_interested_reply_without_a_time_is_not_a_meeting():
    assert classify_reply("Yes, interested.", None) == "replied"
    assert classify_reply("Yes, interested.", "Tue 4pm IST") == "meeting_confirmed"
    assert classify_reply("Please unsubscribe.", "Tue 4pm IST") == "closed"


def test_resume_proof_must_be_a_substring():
    resume = "Led the enterprise AI deployment for a banking client across three cities."
    assert proof_lines(resume) == [resume]
    assert excerpt_in_source("invented 40 percent revenue growth last year", resume) is False


def test_title_only_match_is_not_enough_when_background_is_known():
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    bank = JobHit(
        title="Product Manager- UPI & Payments",
        company_name="Canara Bank",
        description_excerpt="Own the UPI payments roadmap for retail banking customers.",
        date_added="2026-10-22T00:00:00+00:00",
    )
    fit = JobHit(
        title="Product Strategy Lead",
        company_name="Northwind",
        description_excerpt="Own GTM and enterprise deployment for an AI product.",
        date_added="2026-10-22T00:00:00+00:00",
    )
    terms = ["gtm", "deployment", "enterprise", "pre6"]
    bank_score = score_job(bank, ["Product Manager"], ["GTM at Pre6"], profile_terms=terms, now=now)
    fit_score = score_job(fit, ["Product Strategy"], ["GTM at Pre6"], profile_terms=terms, now=now)
    assert bank_score.role_fit < 35
    assert fit_score.role_fit == 35
    assert fit_score.total > bank_score.total
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    fresh = JobHit(title="Product Manager, AI", company_name="A", date_added="2026-10-20T00:00:00+00:00")
    old = JobHit(title="Account Executive", company_name="B", date_added="2026-06-01T00:00:00+00:00")
    fresh_score = score_job(fresh, ["Product Manager"], ["enterprise AI deployment for a banking client"], now=now)
    old_score = score_job(old, ["Product Manager"], ["enterprise AI deployment for a banking client"], now=now)
    assert fresh_score.total > old_score.total
    assert fresh_score.role_fit == 35


def test_case_survives_restart_and_duplicate_action_is_rejected(tmp_path):
    store = Store(tmp_path / "cases.db")
    case = _case()
    store.save(case)
    reopened = Store(tmp_path / "cases.db")
    loaded = reopened.get("case1")
    assert loaded is not None
    assert loaded.role_title == "Product Manager"
    assert reopened.record_action("send:case1", "case1", "send", "sent", "id") is True
    assert reopened.record_action("send:case1", "case1", "send", "sent", "id") is False


def test_illegal_transition_and_meeting_path(tmp_path):
    store = Store(tmp_path / "cases.db")
    case = _case()
    case.state = "replied"
    store.save(case)
    with pytest.raises(TransitionError):
        store.transition(case, "meeting_confirmed", actor="test", reason="skipped scheduling")


def test_synthetic_stale_contact_blocks_then_clears(tmp_path):
    store = Store(tmp_path / "cases.db")
    case = stale_contact_case(store)
    assert case.mode == "SYNTHETIC TEST"
    assert any("does not match" in reason for reason in case.hold_reasons)
    updated = reresolve_stale_contact(store, case.id)
    assert updated.contact is not None
    assert updated.contact.affiliation_verified is True
    assert updated.state == "ready"
    assert not any("does not match" in reason for reason in updated.hold_reasons)
