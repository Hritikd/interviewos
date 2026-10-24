from __future__ import annotations

from interviewos.models import CaseRecord, Contact, Evidence, Intro
from interviewos.textutil import utc_now


class EvidenceBook:
    def __init__(self, mode: str):
        self.mode = mode
        self.items: list[Evidence] = []

    def add(
        self,
        *,
        entity_id: str,
        source: str,
        field: str,
        excerpt: str,
        evidence_type: str,
        source_date: str | None = None,
    ) -> Evidence:
        excerpt = " ".join(excerpt.split())
        if not excerpt:
            raise ValueError("Evidence excerpt cannot be empty.")
        item = Evidence(
            id=f"ev_{len(self.items) + 1}",
            entity_id=entity_id,
            source=source,
            field=field,
            excerpt=excerpt[:400],
            retrieved_at=utc_now(),
            source_date=source_date,
            evidence_type=evidence_type,
            mode=self.mode,  # type: ignore[arg-type]
        )
        self.items.append(item)
        return item


def write_intro(case_name: str, role: str, company: str, evidence: list[Evidence], contact: Contact | None) -> Intro:
    """Build the note only from stored excerpts. The model is not asked to invent a line."""
    by_type = {item.evidence_type: item for item in evidence}
    opening = by_type.get("job_posting")
    proof = by_type.get("resume_proof") or by_type.get("profile_title")
    person = by_type.get("contact")
    ids: list[str] = []

    if opening:
        ids.append(opening.id)
    proof_line = proof.excerpt if proof else "the work described on my profile"
    if proof:
        ids.append(proof.id)
    who = contact.name if contact and contact.name else "the hiring team"
    if person:
        ids.append(person.id)

    name = case_name or "I"
    subject = f"{role} at {company} — a short conversation"
    proof_sentence = f"The closest work I can point to is: {proof_line}."
    body = (
        f"Hello {who},\n\n"
        f"I am writing about the {role} opening at {company}. "
        f"{proof_sentence}\n\n"
        f"Would a 20-minute conversation this week, or a pointer to the right person, be reasonable?\n\n"
        f"{name}"
    )
    return Intro(subject=subject, body=body, evidence_ids=ids)


def why_lines(evidence: list[Evidence], contact: Contact | None, company: str, role: str) -> dict[str, str]:
    def line(kind: str, fallback: str) -> str:
        match = next((item for item in evidence if item.evidence_type == kind), None)
        if match is None:
            return fallback
        return f"{match.excerpt} [{match.id}]"

    return {
        "why_company": line("company", f"{company} is the employer on the posting."),
        "why_now": line("job_posting", f"The {role} posting is the timing evidence."),
        "why_me": line("resume_proof", line("profile_title", "No candidate proof is attached yet.")),
        "why_person": line(
            "contact",
            "No current employee is resolved yet."
            if contact is None or not contact.resolved
            else f"{contact.name}, {contact.title}.",
        ),
    }
