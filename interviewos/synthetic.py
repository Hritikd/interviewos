from __future__ import annotations

import uuid

from interviewos.guard import evaluate_guard
from interviewos.models import CaseRecord, Contact, Evidence, Intro, Mandate, Score
from interviewos.store import Store
from interviewos.textutil import utc_now


def stale_contact_case(store: Store) -> CaseRecord:
    """A labeled synthetic: the old contact has left, so the guard blocks the application."""
    now = utc_now()
    evidence = [
        Evidence(
            id="ev_1",
            entity_id="synthetic-job",
            source="synthetic.job",
            field="job_details.title",
            excerpt="Product Strategy lead, posted on a sample opening.",
            retrieved_at=now,
            source_date=now[:10],
            evidence_type="job_posting",
            mode="SYNTHETIC TEST",
        ),
        Evidence(
            id="ev_2",
            entity_id="candidate",
            source="user.resume",
            field="resume_line",
            excerpt="Led enterprise AI deployment strategy for a product team.",
            retrieved_at=now,
            evidence_type="resume_proof",
            mode="SYNTHETIC TEST",
        ),
        Evidence(
            id="ev_3",
            entity_id="old-contact",
            source="synthetic.person",
            field="experience.employment_details.current",
            excerpt="Asha Raman is a recruiter at a different company now.",
            retrieved_at=now,
            evidence_type="contact",
            mode="SYNTHETIC TEST",
        ),
    ]
    contact = Contact(
        name="Asha Raman",
        title="Recruiter",
        company_name="Somewhere Else",
        company_id=999,
        route="recruiter",
        resolved=True,
        affiliation_verified=False,
        profile_url="https://www.linkedin.com/in/example-old-contact",
    )
    case = CaseRecord(
        id=uuid.uuid4().hex[:12],
        mode="SYNTHETIC TEST",
        state="held",
        opportunity_type="verified_opening",
        company_name="Northwind AI",
        company_domain="northwind.example",
        company_id=1001,
        role_title="Product Strategy Lead",
        job_url="https://example.com/jobs/product-strategy",
        location="Bengaluru",
        contact=contact,
        evidence=evidence,
        score=Score(role_fit=35, proof=30, timing=20, contact=0, notes=["Synthetic stale contact."]),
        candidate_name="Hritik",
        recipient_email="teammate@example.com",
        recipient_source="mandate",
        created_at=now,
        updated_at=now,
        why_company="Northwind AI is the sample employer. [ev_1]",
        why_now=evidence[0].excerpt + " [ev_1]",
        why_me=evidence[1].excerpt + " [ev_2]",
        why_person=evidence[2].excerpt + " [ev_3]",
    )
    case.intro = Intro(
        subject="Product Strategy Lead at Northwind AI — a short conversation",
        body=(
            "Hello Asha Raman,\n\n"
            "I am writing because Northwind AI has Product Strategy lead, posted on a sample opening. "
            "I have been doing adjacent work: Led enterprise AI deployment strategy for a product team. "
            "My hypothesis is that a short working session would show whether I am useful. "
            "Would 20 minutes this week be reasonable?\n\nHritik"
        ),
        evidence_ids=["ev_1", "ev_2", "ev_3"],
    )
    mandate = Mandate(saved=True, recipient_email="teammate@example.com", allow_send=False)
    case.hold_reasons = evaluate_guard(case, mandate)
    case.next_action = case.hold_reasons[0] if case.hold_reasons else "Ready"
    store.save(case)
    return case


def reresolve_stale_contact(store: Store, case_id: str) -> CaseRecord:
    case = store.get(case_id)
    if case is None or case.mode != "SYNTHETIC TEST":
        raise ValueError("Re-resolve is only for the synthetic stale-contact case.")
    now = utc_now()
    case.evidence = [item for item in case.evidence if item.id != "ev_3"]
    case.evidence.append(
        Evidence(
            id="ev_4",
            entity_id="new-contact",
            source="synthetic.person",
            field="experience.employment_details.current",
            excerpt="Meera Shah is a talent partner at Northwind AI.",
            retrieved_at=now,
            evidence_type="contact",
            mode="SYNTHETIC TEST",
        )
    )
    case.contact = Contact(
        name="Meera Shah",
        title="Talent Partner",
        company_name="Northwind AI",
        company_id=1001,
        route="recruiter",
        resolved=True,
        affiliation_verified=True,
        profile_url="https://www.linkedin.com/in/example-new-contact",
    )
    case.why_person = "Meera Shah is a talent partner at Northwind AI. [ev_4]"
    if case.intro:
        case.intro.body = case.intro.body.replace("Asha Raman", "Meera Shah")
        case.intro.evidence_ids = ["ev_1", "ev_2", "ev_4"]
    mandate = Mandate(saved=True, recipient_email=case.recipient_email or "", allow_send=False)
    case.hold_reasons = evaluate_guard(case, mandate, for_send=False)
    if any("does not match" in reason or "Synthetic" in reason for reason in case.hold_reasons):
        case.state = "held"
        case.next_action = case.hold_reasons[0]
    else:
        case.state = "ready"
        case.hold_reasons = []
        case.next_action = "Synthetic contact re-resolved. Real email is still blocked on synthetic cases."
    store.save(case)
    return case
