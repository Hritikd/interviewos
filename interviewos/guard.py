from __future__ import annotations

from interviewos.models import CaseRecord, Mandate
from interviewos.textutil import is_email


def evaluate_guard(
    case: CaseRecord,
    mandate: Mandate,
    *,
    sends_today: int = 0,
    for_send: bool = False,
) -> list[str]:
    """Return the reasons an outbound application must stay held. Empty means it may proceed."""
    reasons: list[str] = []
    if not mandate.saved:
        reasons.append("Save a mandate before any application goes out.")
    if mandate.daily_cap < 1:
        reasons.append("Daily cap must be at least 1.")
    if for_send and sends_today >= mandate.daily_cap:
        reasons.append("Daily send cap is already used.")

    evidence_ids = {item.id for item in case.evidence}
    if not evidence_ids:
        reasons.append("This case has no evidence.")
    if case.intro is None:
        reasons.append("There is no introduction to send.")
    else:
        missing = [item for item in case.intro.evidence_ids if item not in evidence_ids]
        if missing:
            reasons.append("Introduction cites evidence that is not on the case: " + ", ".join(missing))
        if not case.intro.evidence_ids:
            reasons.append("Introduction has no evidence ids.")

    contact = case.contact
    if contact is None or not contact.resolved:
        reasons.append("No current employee is resolved at this company.")
    elif not contact.affiliation_verified:
        reasons.append("The contact's current company does not match this opening. Re-resolve before sending.")

    recipient = (case.recipient_email or "").strip()
    allowed = (mandate.recipient_email or "").strip()
    if not is_email(recipient):
        reasons.append("Add a real recipient email. None will be guessed.")
    elif not is_email(allowed):
        reasons.append("The mandate has no allowed recipient email.")
    elif recipient.lower() != allowed.lower():
        reasons.append("That recipient is outside the saved mandate.")
    elif case.recipient_source not in {"mandate", "provider"}:
        reasons.append("The recipient email has no allowed source.")

    if case.mode == "SYNTHETIC TEST" and for_send:
        reasons.append("Synthetic cases cannot send real email.")
    return reasons
